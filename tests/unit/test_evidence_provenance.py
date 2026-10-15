"""
v5.5.7 P0 #2: isolamento de proveniência e integridade do cache de evidências.

Valida que resultados simulados (mock) nunca poluem o cache de providers reais:
  1. MockSearchProvider marca is_simulated=True em todos os itens.
  2. Quando o usuário pede 'tavily' mas não tem TAVILY_API_KEY, o service usa
     'mock_tavily' como chave de cache (não 'tavily').
  3. O cache recusa gravar payload simulado sob provider real.
  4. O cache recusa sobrescrever entrada real com payload simulado.
  5. Métrica provider_used reflete o nome efetivo.
"""

from __future__ import annotations

from pathlib import Path

from backend.core.config import Settings
from backend.core.evidence.cache import FileEvidenceCache
from backend.core.evidence.providers import (
    MockSearchProvider,
    SearchResultItem,
    get_search_provider,
)
from backend.core.evidence.service import EvidenceService


def _cfg(tmp_path: Path, **over) -> Settings:
    base = {
        "EVIDENCE_ENABLED": True,
        "EVIDENCE_PROVIDER": "mock",
        "EVIDENCE_CACHE_ENABLED": True,
        "EVIDENCE_CACHE_TTL_SECONDS": 3600,
        "EVIDENCE_CACHE_BYPASS": False,
        "EVIDENCE_MAX_QUERIES_PER_MISSION": 3,
        "EVIDENCE_MAX_RESULTS_PER_QUERY": 5,
        "EVIDENCE_FAIL_OPEN": True,
        "EVIDENCE_TIMEOUT_SECONDS": 5.0,
        "TAVILY_API_KEY": "",
        "SERPER_API_KEY": "",
        "EVIDENCE_HTTP_ENDPOINT": "",
        "EVIDENCE_HTTP_API_KEY": "",
        "BUILD_ARTIFACTS_DIR": str(tmp_path / "build"),
    }
    base.update(over)
    return Settings(**base)


def test_mock_search_provider_marca_is_simulated() -> None:
    p = MockSearchProvider()
    items = p.search("qualquer query")
    assert items, "MockSearchProvider deve retornar itens determinísticos"
    assert all(it.is_simulated is True for it in items)
    assert p.is_mock_fallback is True


def test_tavily_sem_key_vira_mock_tavily() -> None:
    """Solicitar 'tavily' sem TAVILY_API_KEY cai em mock, mas com nome distinto."""
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(Path(tmp), TAVILY_API_KEY="")
        provider = get_search_provider("tavily", config=cfg)
        assert getattr(provider, "is_mock_fallback", False) is True

        svc = EvidenceService(config=cfg, provider_name="tavily")
        assert svc.effective_provider == "mock_tavily"
        assert svc.metrics["provider_used"] == "mock_tavily"
        assert svc.metrics["is_simulated"] is True
        assert any("mock_tavily" in w for w in svc.warnings)


def test_cache_recusa_simulado_sob_provider_real(tmp_path: Path) -> None:
    """Defesa 1: set() com provider='tavily' + is_simulated=True é recusado."""
    cfg = _cfg(tmp_path)
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)
    items = [SearchResultItem(title="T", snippet="S", url="https://x",
                              publisher="p", score=1.0, is_simulated=True)]
    cache.set("tavily", "query x", items, is_simulated=True)
    # A chave sob 'tavily' deve continuar vazia (recusado)
    assert cache.get("tavily", "query x") is None


def test_cache_recusa_sobrescrever_real_com_simulado(tmp_path: Path) -> None:
    """Defesa 2: entrada real não pode ser sobrescrita por payload simulado."""
    cfg = _cfg(tmp_path)
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)

    real_items = [SearchResultItem(title="Real", snippet="real", url="https://real",
                                   publisher="tavily", score=1.0, is_simulated=False)]
    cache.set("tavily", "query y", real_items, is_simulated=False)

    # Tenta sobrescrever com simulado (mesmo provider) -> deve ser recusado
    fake_items = [SearchResultItem(title="Fake", snippet="fake", url="https://fake",
                                   publisher="mock", score=1.0, is_simulated=True)]
    cache.set("tavily", "query y", fake_items, is_simulated=True)

    # O cache deve ainda retornar os itens reais originais
    cached = cache.get("tavily", "query y")
    assert cached is not None
    assert cached[0].title == "Real"
    assert cached[0].is_simulated is False


def test_service_usa_chave_distinta_quando_fallback(tmp_path: Path) -> None:
    """Integração: ao pedir tavily sem key, cache grava sob 'mock_tavily'."""
    cfg = _cfg(tmp_path, TAVILY_API_KEY="")
    cache = FileEvidenceCache(root=tmp_path / "cache", config=cfg)
    svc = EvidenceService(config=cfg, cache=cache, provider_name="tavily")

    queries = svc.plan_queries("discover", {"theme": "barbearias"})
    assert queries, "deve haver queries planejadas"

    results = svc.search(queries[:1])
    assert results, "deve haver resultados mock"
    assert all(r.is_simulated for r in results)

    # Cache sob 'mock_tavily' deve existir
    cached_mock = cache.get("mock_tavily", queries[0].query)
    assert cached_mock is not None, "cache deve ter entrada sob mock_tavily"
    # Cache sob 'tavily' deve estar vazio (nunca poluído)
    cached_real = cache.get("tavily", queries[0].query)
    assert cached_real is None, "cache sob 'tavily' deve permanecer vazio (anti-poluição)"