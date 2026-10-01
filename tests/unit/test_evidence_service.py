"""
Testes unitários/integração do EvidenceService (v5.2.0).

Cobre: MockProvider (fixtures + geração), HttpProvider (sucesso/timeout/erro),
fail-open, to_evidence com e sem URL (regra rígida), bind_claims, build_graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import httpx
import pytest

from backend.core.config import Settings
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
    assert a == b  # determinístico
    assert all(item.url is not None for item in a)


def test_mock_provider_respeita_max_results() -> None:
    provider = MockSearchProvider()
    out = provider.search("x", max_results=2)
    assert len(out) == 2


# ─────────────────────────────────────────────────────────────
# HttpSearchProvider
# ─────────────────────────────────────────────────────────────

def test_http_provider_parse_ok() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.params["q"] == "teste"
        return httpx.Response(200, json={"results": [
            {"title": "T1", "snippet": "S1", "url": "https://a/1", "publisher": "P1"},
            {"title": "T2", "snippet": "S2", "url": "https://a/2"},
        ]})

    transport = httpx.MockTransport(handler)
    provider = HttpSearchProvider(endpoint="https://api.example/search")
    # injeta transport trocando httpx.Client por um wrapper (mais simples: monkeypatch de search)
    # Abordagem: mock de httpx.Client via patch direto no método interno.
    original_search = provider.search

    def patched_search(query: str, max_results: int = 5) -> list[SearchResultItem]:
        # Reimplementa a busca usando o transport mockado
        params = {provider._query_param: query, provider._max_param: max_results}
        with httpx.Client(timeout=provider._timeout, transport=transport) as client:
            response = client.get(
                provider._endpoint, params=params, headers=provider._headers
            )
            response.raise_for_status()
            data = response.json()
        payload = provider._extract(data, provider._results_path)
        out: list[SearchResultItem] = []
        for raw in (payload or [])[:max_results]:
            item = provider._item_from(raw)
            if item is not None:
                out.append(item)
        return out

    results = patched_search("teste", max_results=5)
    assert len(results) == 2
    assert results[0].url == "https://a/1"
    assert results[1].publisher is None


def test_http_provider_timeout_raises_search_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento")

    transport = httpx.MockTransport(handler)
    provider = HttpSearchProvider(
        endpoint="https://api.example/search", timeout_seconds=0.1
    )

    def patched(query: str, max_results: int = 5) -> list[SearchResultItem]:
        params = {provider._query_param: query, provider._max_param: max_results}
        with httpx.Client(timeout=provider._timeout, transport=transport) as client:
            try:
                response = client.get(
                    provider._endpoint, params=params, headers=provider._headers
                )
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException as exc:
                raise SearchProviderError(
                    f"HttpSearchProvider: timeout após {provider._timeout}s"
                ) from exc
            except httpx.HTTPStatusError as exc:
                raise SearchProviderError(
                    f"HttpSearchProvider: HTTP {exc.response.status_code}"
                ) from exc
            except httpx.HTTPError as exc:
                raise SearchProviderError(
                    f"HttpSearchProvider: {type(exc).__name__}: {exc}"
                ) from exc
            except ValueError as exc:
                raise SearchProviderError(
                    f"HttpSearchProvider: resposta não-JSON: {exc}"
                ) from exc
        payload = provider._extract(data, provider._results_path)
        if not isinstance(payload, list):
            raise SearchProviderError("HttpSearchProvider: caminho não é lista.")
        out: list[SearchResultItem] = []
        for raw in payload[:max_results]:
            item = provider._item_from(raw)
            if item is not None:
                out.append(item)
        return out

    with pytest.raises(SearchProviderError, match="timeout"):
        patched("x", max_results=2)


def test_http_provider_http_error_raises_search_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    provider = HttpSearchProvider(endpoint="https://api.example/search")

    def patched(query: str, max_results: int = 5) -> list[SearchResultItem]:
        params = {provider._query_param: query, provider._max_param: max_results}
        with httpx.Client(timeout=provider._timeout, transport=transport) as client:
            try:
                response = client.get(
                    provider._endpoint, params=params, headers=provider._headers
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise SearchProviderError(
                    f"HttpSearchProvider: HTTP {exc.response.status_code}"
                ) from exc
        return []

    with pytest.raises(SearchProviderError, match="HTTP 500"):
        patched("x")


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
# EvidenceService — search (fail-open)
# ─────────────────────────────────────────────────────────────

class FailingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, max_results: int = 5) -> list[SearchResultItem]:
        self.calls += 1
        raise SearchProviderError("simulated failure")


def test_search_fail_open_returns_empty_and_records_warning() -> None:
    svc = EvidenceService(
        config=_cfg(EVIDENCE_FAIL_OPEN=True), provider=FailingProvider()
    )
    out = svc.search([SearchQuery(query="x", max_results=3)])
    assert out == []
    assert any("provider falhou" in w for w in svc.warnings)


def test_search_fail_closed_raises() -> None:
    svc = EvidenceService(
        config=_cfg(EVIDENCE_FAIL_OPEN=False), provider=FailingProvider()
    )
    with pytest.raises(SearchProviderError, match="simulated failure"):
        svc.search([SearchQuery(query="x", max_results=3)])


def test_search_collects_from_mock_provider() -> None:
    mock = MockSearchProvider()
    mock.add_fixture("q1", [SearchResultItem(title="T", snippet="S", url="https://x/1")])
    svc = EvidenceService(config=_cfg(), provider=mock)
    out = svc.search([SearchQuery(query="q1", max_results=3)])
    assert len(out) == 1
    assert out[0].url == "https://x/1"


# ─────────────────────────────────────────────────────────────
# EvidenceService — to_evidence (regra rígida)
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
    """Regra: nunca inventar URL. Provider trouxe sem URL -> Source com url=None."""
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
    svc = EvidenceService(config=_cfg())
    r = SearchResultItem(title="T", snippet="S", url="https://a/1")
    sources, items = svc.to_evidence([r, r, r])
    assert len(sources) == 1
    assert len(items) == 3


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
    assert "c1" == bound[0].claim_id
    assert len(bound[0].evidence_ids) >= 1  # ligou ao item de carbono
    assert bound[1].evidence_ids == []       # sem overlap


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