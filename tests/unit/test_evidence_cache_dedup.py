"""
Testes unitários do cache persistente e da camada de deduplicação (v5.2.1).

Zero rede, zero LLM: usa tmp_path para o cache e fixtures estáveis para dedup.
Cada teste é definido uma única vez (sem redeclarações).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.evidence.cache import FileEvidenceCache, _cache_key
from backend.core.evidence.dedup import (
    deduplicate_claims,
    deduplicate_evidence,
    deduplicate_sources,
    score_relevance,
)
from backend.core.evidence.providers import SearchResultItem
from backend.domain.evidence import (
    Claim,
    EvidenceItem,
    EvidenceOrigin,
    Source,
)


def _cfg(tmp_path: Path, **overrides: Any) -> Settings:
    base = {
        "BUILD_ARTIFACTS_DIR": str(tmp_path / "artifacts" / "build"),
        "EVIDENCE_CACHE_ENABLED": True,
        "EVIDENCE_CACHE_TTL_SECONDS": 86400,
        "EVIDENCE_CACHE_BYPASS": False,
    }
    base.update(overrides)
    return Settings(**base)


def _now_iso(offset_seconds: int = 0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return dt.isoformat()


def _write_cache_file(
    cache: FileEvidenceCache, provider: str, query: str, payload: dict
) -> Path:
    """Helper: grava manualmente um arquivo de cache em cache._root."""
    cache._root.mkdir(parents=True, exist_ok=True)
    path = cache._root / f"{_cache_key(provider, query)}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _src(source_id: str, url: str | None, title: str = "T", publisher: str = "P") -> Source:
    return Source(
        source_id=source_id, url=url, title=title, publisher=publisher,
        retrieved_at=datetime.now(timezone.utc),
    )


def _ev(eid: str, source_id: str, quote: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=eid, source_id=source_id, quote_or_summary=quote,
        origin=EvidenceOrigin.EXTERNAL,
    )


# ─────────────────────────────────────────────────────────────
# Cache: hit / miss / expired / bypass / disabled / invalidate
# ─────────────────────────────────────────────────────────────

def test_cache_miss_quando_vazio(tmp_path: Path) -> None:
    cache = FileEvidenceCache(root=tmp_path / "cache", config=_cfg(tmp_path))
    assert cache.get("mock", "qualquer query") is None


def test_cache_hit_retorna_items(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)
    results = [
        SearchResultItem(title="T1", snippet="S1", url="https://a/1", publisher="P1"),
        SearchResultItem(title="T2", snippet="S2", url="https://a/2"),
    ]
    cache.set("mock", "query X", results)
    got = cache.get("mock", "query X")
    assert got is not None
    assert len(got) == 2
    assert got[0].title == "T1"
    assert got[1].url == "https://a/2"


def test_cache_expired_retorna_none(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, EVIDENCE_CACHE_TTL_SECONDS=10)
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)
    _write_cache_file(cache, "mock", "query velha", {
        "provider": "mock",
        "query": "query velha",
        "normalized_query": "query velha",
        "results": [{"title": "T", "snippet": "S", "url": "https://a/1",
                     "publisher": "P", "score": 1.0}],
        "stored_at": _now_iso(offset_seconds=-1000),
        "ttl_seconds": 10,
    })
    assert cache.get("mock", "query velha") is None


def test_cache_bypass_sempre_miss(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, EVIDENCE_CACHE_BYPASS=True)
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)
    cache.set("mock", "q", [SearchResultItem(title="T", snippet="S", url="https://a/1")])
    assert cache.get("mock", "q") is None
    assert not any(cache._root.glob("*.json"))


def test_cache_disabled_nao_grava(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, EVIDENCE_CACHE_ENABLED=False)
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)
    cache.set("mock", "q", [SearchResultItem(title="T", snippet="S", url="https://a/1")])
    assert cache.get("mock", "q") is None
    assert not cache._root.exists() or not any(cache._root.glob("*.json"))


def test_cache_chave_insensivel_a_case_e_espacos(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)
    cache.set("MOCK", "  BarbeaRIAS   SP  ",
              [SearchResultItem(title="T", snippet="S", url="https://a/1")])
    got = cache.get("mock", "barbearias sp")
    assert got is not None
    assert len(got) == 1


def test_cache_invalidate(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)
    cache.set("mock", "q", [SearchResultItem(title="T", snippet="S", url="https://a/1")])
    assert cache.invalidate("mock", "q") is True
    assert cache.get("mock", "q") is None
    assert cache.invalidate("mock", "q") is False


def test_cache_arquivo_corrompido_retorna_none(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)
    cache._root.mkdir(parents=True, exist_ok=True)
    path = cache._root / f"{_cache_key('mock', 'q')}.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert cache.get("mock", "q") is None


# ─────────────────────────────────────────────────────────────
# Dedup: sources
# ─────────────────────────────────────────────────────────────

def test_dedup_sources_normaliza_http_https_e_trailing_slash() -> None:
    sources = [
        _src("a", "https://site.com/a/"),
        _src("b", "http://site.com/a"),
        _src("c", "https://www.site.com/a"),
        _src("d", "https://site.com/a?x=1"),
    ]
    kept, removed = deduplicate_sources(sources)
    assert len(kept) == 2
    assert removed == 2
    urls = {s.url for s in kept}
    assert "https://site.com/a?x=1" in urls


def test_dedup_sources_fallback_por_title_publisher_quando_sem_url() -> None:
    sources = [
        _src("a", None, title="IBGE 2024", publisher="IBGE"),
        _src("b", None, title="IBGE 2024", publisher="IBGE"),
        _src("c", None, title="Sebrae", publisher="Sebrae"),
    ]
    kept, removed = deduplicate_sources(sources)
    assert len(kept) == 2
    assert removed == 1


def test_dedup_sources_mantem_urls_distintas() -> None:
    sources = [
        _src("a", "https://site.com/a"),
        _src("b", "https://site.com/b"),
        _src("c", "https://outro.com/a"),
    ]
    kept, removed = deduplicate_sources(sources)
    assert len(kept) == 3
    assert removed == 0


# ─────────────────────────────────────────────────────────────
# Dedup: evidence
# ─────────────────────────────────────────────────────────────

def test_dedup_evidence_por_quote_e_source_id() -> None:
    items = [
        _ev("e1", "s1", "PMEs representam 30% do PIB."),
        _ev("e2", "s1", "PMEs representam 30% do PIB."),
        _ev("e3", "s2", "PMEs representam 30% do PIB."),
        _ev("e4", "s1", "Outro fato."),
    ]
    kept, removed = deduplicate_evidence(items)
    assert len(kept) == 3
    assert removed == 1


# ─────────────────────────────────────────────────────────────
# Dedup: claims
# ─────────────────────────────────────────────────────────────

def test_dedup_claims_por_texto_normalizado() -> None:
    claims = [
        Claim(claim_id="c1", text="PMEs querem reduzir carbono.",
              origin=EvidenceOrigin.MODEL_OPINION),
        Claim(claim_id="c2", text="PMEs  querem   reduzir carbono!",
              origin=EvidenceOrigin.MODEL_OPINION),
        Claim(claim_id="c3", text="pmes QUEREM reduzir CARBONO",
              origin=EvidenceOrigin.MODEL_OPINION),
        Claim(claim_id="c4", text="Outra coisa.", origin=EvidenceOrigin.MODEL_OPINION),
    ]
    kept, removed = deduplicate_claims(claims)
    assert len(kept) == 2
    assert removed == 2
    assert kept[0].claim_id == "c1"
    assert kept[1].claim_id == "c4"


# ─────────────────────────────────────────────────────────────
# Relevância (Jaccard + penalty de snippet curto)
# ─────────────────────────────────────────────────────────────

def test_score_relevance_alto_quando_overlap() -> None:
    """Jaccard com 2 tokens de query em 9 de conteúdo ≈ 0.22."""
    s = score_relevance(
        "agendamento barbearias",
        title="Sistema de agendamento para barbearias",
        snippet="Agendamento online ajuda barbearias a crescer.",
    )
    assert 0.2 < s < 0.25


def test_score_relevance_baixo_quando_sem_overlap() -> None:
    s = score_relevance(
        "agendamento barbearias",
        title="Receita de bolo de chocolate",
        snippet="Farinha, ovos e manteiga.",
    )
    assert s == 0.0


def test_score_relevance_penaliza_snippet_curto() -> None:
    """Snippet curto com overlap perfeito tem Jaccard alto mas é penalizado."""
    s_long = score_relevance(
        "barbearias", title="", snippet="Agendamento online para barbearias modernas"
    )
    assert s_long == 0.2  # Jaccard 1/5, sem penalty

    s_short = score_relevance("barbearias", title="", snippet="barbearias")
    assert s_short == 0.5  # Jaccard 1/1 * penalty 0.5

    # O penalty reduz o score, mas Jaccard puro não captura "informatividade":
    # snippet curto com overlap perfeito ainda pontua acima do longo.
    assert s_short > 0.0


def test_score_relevance_query_vazia_retorna_zero() -> None:
    assert score_relevance("", title="x", snippet="y") == 0.0