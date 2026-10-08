"""
Testes unitários do EvidenceService (v5.2.1).

Cobre: MockProvider (fixtures + geração), HttpProvider (sucesso/timeout/erro
via MockTransport), fail-open, to_evidence com e sem URL (regra rígida) +
dedup, bind_claims, build_graph. Cache isolado em tmp_path (zero rede/repo).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.core.config import Settings
from backend.core.evidence.cache import FileEvidenceCache
from backend.core.evidence.providers import (
    HttpSearchProvider,
    MockSearchProvider,
    SearchProviderError,
    SearchResultItem,
)
from backend.core.evidence.service import EvidenceService, SearchQuery
from backend.domain.evidence import Claim, EvidenceOrigin


def _cfg(**overrides: Any) -> Settings:
    base = {
        "EVIDENCE_ENABLED": True,
        "EVIDENCE_PROVIDER": "mock",
        "EVIDENCE_MAX_QUERIES_PER_MISSION": 3,
        "EVIDENCE_MAX_RESULTS_PER_QUERY": 5,
        "EVIDENCE_TIMEOUT_SECONDS": 1.0,
        "EVIDENCE_FAIL_OPEN": True,
    }
    base.update(overrides)
    return Settings(**base)


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    """Injeta MockTransport em httpx.Client sem tocar no provider."""
    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)


class FailingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, max_results: int = 5) -> list[SearchResultItem]:
        self.calls += 1
        raise SearchProviderError("simulated failure")


# ─────────────────────────────────────────────────────────────
# MockSearchProvider
# ─────────────────────────────────────────────────────────────

def test_mock_provider_com_fixture() -> None:
    provider = MockSearchProvider()
    provider.add_fixture("pmes brasil", [
        SearchResultItem(title="PMEs crescem", snippet="Dados IBGE", url="https://a/x"),
        SearchResultItem(title="Crédito PME", snippet="BNDES", url="https://b/y"),
    ])
    out = provider.search("pmes brasil", max_results=5)
    assert len(out) == 2
    assert out[0].url == "https://a/x"


def test_mock_provider_deterministico_sem_fixture() -> None:
    provider = MockSearchProvider()
    a = provider.search("qualquer coisa", max_results=3)
    b = provider.search("qualquer coisa", max_results=3)
    assert len(a) == 3
    assert a == b
    assert all(item.url is not None for item in a)


def test_mock_provider_respeita_max_results() -> None:
    provider = MockSearchProvider()
    out = provider.search("x", max_results=2)
    assert len(out) == 2


# ─────────────────────────────────────────────────────────────
# HttpSearchProvider (MockTransport)
# ─────────────────────────────────────────────────────────────

def test_http_provider_parse_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.params["q"] == "teste"
        return httpx.Response(200, json={"results": [
            {"title": "T1", "snippet": "S1", "url": "https://a/1", "publisher": "P1"},
            {"title": "T2", "snippet": "S2", "url": "https://a/2"},
        ]})

    _patch_client(monkeypatch, handler)
    provider = HttpSearchProvider(endpoint="https://api.example/search")
    results = provider.search("teste", max_results=5)
    assert len(results) == 2
    assert results[0].url == "https://a/1"
    assert results[1].publisher is None


def test_http_provider_timeout_raises_search_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento")

    _patch_client(monkeypatch, handler)
    provider = HttpSearchProvider(
        endpoint="https://api.example/search", timeout_seconds=0.1
    )
    with pytest.raises(SearchProviderError, match="timeout"):
        provider.search("x", max_results=2)


def test_http_provider_http_error_raises_search_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    _patch_client(monkeypatch, handler)
    provider = HttpSearchProvider(endpoint="https://api.example/search")
    with pytest.raises(SearchProviderError, match="HTTP 500"):
        provider.search("x")


def test_http_provider_requires_endpoint() -> None:
    with pytest.raises(ValueError):
        HttpSearchProvider(endpoint="")


# ─────────────────────────────────────────────────────────────
# EvidenceService — plan_queries
# ─────────────────────────────────────────────────────────────

def test_plan_queries_discover() -> None:
    svc = EvidenceService(config=_cfg())
    qs = svc.plan_queries("discover", {
        "theme": "agendamento", "audience": "barbearias", "geography": "Brasil"
    })
    assert len(qs) >= 1
    assert any("agendamento" in q.query for q in qs)
    assert any("barbearias" in q.query for q in qs)


def test_plan_queries_validate() -> None:
    svc = EvidenceService(config=_cfg())
    qs = svc.plan_queries("validate", {
        "problem": "reduzir pegada de carbono", "audience": "PMEs"
    })
    assert any("carbono" in q.query for q in qs)
    assert any("concorrentes" in q.query for q in qs)


def test_plan_queries_disabled_retorna_vazio() -> None:
    svc = EvidenceService(config=_cfg(EVIDENCE_ENABLED=False))
    assert svc.plan_queries("discover", {"theme": "x"}) == []


def test_plan_queries_respeita_cap() -> None:
    svc = EvidenceService(config=_cfg(EVIDENCE_MAX_QUERIES_PER_MISSION=1))
    qs = svc.plan_queries("validate", {"problem": "x", "audience": "y"})
    assert len(qs) <= 1


# ─────────────────────────────────────────────────────────────
# EvidenceService — search (fail-open + cache isolado)
# ─────────────────────────────────────────────────────────────

def test_search_fail_open_returns_empty_and_records_warning(tmp_path: Path) -> None:
    cache = FileEvidenceCache(root=tmp_path / "cache", config=_cfg())
    svc = EvidenceService(
        config=_cfg(EVIDENCE_FAIL_OPEN=True), provider=FailingProvider(), cache=cache
    )
    out = svc.search([SearchQuery(query="x", max_results=3)])
    assert out == []
    assert any("provider falhou" in w for w in svc.warnings)


def test_search_fail_closed_raises(tmp_path: Path) -> None:
    cache = FileEvidenceCache(root=tmp_path / "cache", config=_cfg())
    svc = EvidenceService(
        config=_cfg(EVIDENCE_FAIL_OPEN=False), provider=FailingProvider(), cache=cache
    )
    with pytest.raises(SearchProviderError, match="simulated failure"):
        svc.search([SearchQuery(query="x", max_results=3)])


def test_search_collects_from_mock_provider(tmp_path: Path) -> None:
    mock = MockSearchProvider()
    mock.add_fixture("q1", [SearchResultItem(title="T", snippet="S", url="https://x/1")])
    cache = FileEvidenceCache(root=tmp_path / "cache", config=_cfg())
    svc = EvidenceService(config=_cfg(), provider=mock, cache=cache)
    out = svc.search([SearchQuery(query="q1", max_results=3)])
    assert len(out) == 1
    assert out[0].url == "https://x/1"
    # 2ª chamada deve vir do cache (provider não é consultado de novo)
    mock.add_fixture("q1", [])  # se bater no provider, retornaria vazio
    out2 = svc.search([SearchQuery(query="q1", max_results=3)])
    assert len(out2) == 1  # veio do cache


# ─────────────────────────────────────────────────────────────
# EvidenceService — to_evidence (regra rígida + dedup)
# ─────────────────────────────────────────────────────────────

def test_to_evidence_com_url() -> None:
    svc = EvidenceService(config=_cfg())
    results = [
        SearchResultItem(title="T1", snippet="S1", url="https://a/1", publisher="P1"),
        SearchResultItem(title="T2", snippet="S2", url="https://a/2"),
    ]
    sources, items = svc.to_evidence(results)
    assert len(sources) == 2
    assert len(items) == 2
    assert sources[0].url == "https://a/1"
    assert all(s.url is not None for s in sources)


def test_to_evidence_sem_url_cria_source_com_url_none() -> None:
    svc = EvidenceService(config=_cfg())
    results = [SearchResultItem(title="T", snippet="S", url=None, publisher="IBGE")]
    sources, items = svc.to_evidence(results)
    assert len(sources) == 1
    assert sources[0].url is None
    assert sources[0].publisher == "IBGE"
    assert len(items) == 1
    assert items[0].origin == EvidenceOrigin.EXTERNAL


def test_to_evidence_descarta_item_sem_conteudo() -> None:
    svc = EvidenceService(config=_cfg())
    results = [SearchResultItem(title="", snippet="", url=None, publisher=None)]
    sources, items = svc.to_evidence(results)
    assert sources == []
    assert items == []
    assert any("descartado" in w for w in svc.warnings)


def test_to_evidence_deduplica_sources_por_id() -> None:
    """Fontes com mesmo conteúdo colapsam em 1 Source; itens distintos permanecem."""
    svc = EvidenceService(config=_cfg())
    items_in = [
        SearchResultItem(title="T", snippet="S1", url="https://a/1"),
        SearchResultItem(title="T", snippet="S2", url="https://a/1"),
        SearchResultItem(title="T", snippet="S3", url="https://a/1"),
    ]
    sources, items = svc.to_evidence(items_in)
    assert len(sources) == 1
    assert len(items) == 3
    assert {it.quote_or_summary for it in items} == {"S1", "S2", "S3"}


def test_to_evidence_deduplica_items_identicos() -> None:
    """Itens totalmente idênticos são dedupados (regra v5.2.1-2/3)."""
    svc = EvidenceService(config=_cfg())
    r = SearchResultItem(title="T", snippet="S", url="https://a/1")
    sources, items = svc.to_evidence([r, r, r])
    assert len(sources) == 1
    assert len(items) == 1
    # 3 itens idênticos -> 1 mantido + 2 removidos
    assert any("2 evidência(s) duplicada(s) removida(s)" in w for w in svc.warnings)


# ─────────────────────────────────────────────────────────────
# EvidenceService — bind_claims
# ─────────────────────────────────────────────────────────────

def test_bind_claims_por_overlap_de_keywords() -> None:
    svc = EvidenceService(config=_cfg())
    results = [
        SearchResultItem(title="T1", snippet="PMEs reduzem pegada de carbono em 20%",
                         url="https://a/1"),
        SearchResultItem(title="T2", snippet="Dados sobre mercado financeiro",
                         url="https://a/2"),
    ]
    _, items = svc.to_evidence(results)
    claims = [
        Claim(claim_id="c1", text="PMEs querem reduzir pegada de carbono",
              origin=EvidenceOrigin.MODEL_OPINION),
        Claim(claim_id="c2", text="outro assunto sem relação",
              origin=EvidenceOrigin.MODEL_OPINION),
    ]
    bound = svc.bind_claims(claims, items)
    assert bound[0].claim_id == "c1"
    assert len(bound[0].evidence_ids) >= 1
    assert bound[1].evidence_ids == []


def test_bind_claims_preserva_ids_existentes() -> None:
    svc = EvidenceService(config=_cfg())
    results = [SearchResultItem(title="T", snippet="PMEs carbono", url="https://a/1")]
    _, items = svc.to_evidence(results)
    claims = [Claim(
        claim_id="c1", text="PMEs carbono", origin=EvidenceOrigin.MODEL_OPINION,
        evidence_ids=["pre-existente"],
    )]
    bound = svc.bind_claims(claims, items)
    assert bound[0].evidence_ids[0] == "pre-existente"


# ─────────────────────────────────────────────────────────────
# EvidenceService — build_graph
# ─────────────────────────────────────────────────────────────

def test_build_graph_inclui_tudo_e_warnings() -> None:
    svc = EvidenceService(config=_cfg())
    svc.warnings.append("aviso de teste")
    results = [SearchResultItem(title="T", snippet="S", url="https://a/1")]
    sources, items = svc.to_evidence(results)
    claims = [Claim(claim_id="c1", text="claim x", origin=EvidenceOrigin.EXTERNAL)]
    g = svc.build_graph("m-1", claims, items, sources)
    assert g.mission_id == "m-1"
    assert len(g.sources) == 1
    assert len(g.evidence_items) == 1
    assert len(g.claims) == 1
    assert "aviso de teste" in g.notes


def test_build_graph_deduplica_claims() -> None:
    svc = EvidenceService(config=_cfg())
    claims = [
        Claim(claim_id="c1", text="PMEs querem carbono.", origin=EvidenceOrigin.EXTERNAL),
        Claim(claim_id="c2", text="PMEs  querem carbono!", origin=EvidenceOrigin.EXTERNAL),
    ]
    g = svc.build_graph("m-2", claims, [], [])
    assert len(g.claims) == 1
    assert any("1 claim(s) duplicado(s) removido(s)" in w for w in svc.warnings)