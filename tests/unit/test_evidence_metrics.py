"""
Testes de observabilidade do EvidenceService (v5.2.1-3/3).

Valida métricas de cache (hits/misses), dedup (sources/evidence/claims) e
persistência de metrics no evidence_graph.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.evidence.cache import FileEvidenceCache
from backend.core.evidence.providers import MockSearchProvider, SearchResultItem
from backend.core.evidence.service import EvidenceService, SearchQuery
from backend.domain.evidence import Claim, EvidenceOrigin
from backend.domain.evidence_store import save_evidence_graph


def _cfg(**overrides: Any) -> Settings:
    base = {
        "EVIDENCE_ENABLED": True,
        "EVIDENCE_PROVIDER": "mock",
        "EVIDENCE_MAX_QUERIES_PER_MISSION": 3,
        "EVIDENCE_MAX_RESULTS_PER_QUERY": 5,
        "EVIDENCE_FAIL_OPEN": True,
    }
    base.update(overrides)
    return Settings(**base)


def test_metrics_cache_hits_e_misses(tmp_path: Path) -> None:
    mock = MockSearchProvider()
    mock.add_fixture("q1", [SearchResultItem(title="T", snippet="S", url="https://x/1")])
    cache = FileEvidenceCache(root=tmp_path / "cache", config=_cfg())
    svc = EvidenceService(config=_cfg(), provider=mock, cache=cache, provider_name="mock")

    svc.search([SearchQuery(query="q1", max_results=3)])  # miss -> provider
    svc.search([SearchQuery(query="q1", max_results=3)])  # hit -> cache

    assert svc.metrics["provider_used"] == "mock"
    assert svc.metrics["cache_misses"] >= 1
    assert svc.metrics["cache_hits"] >= 1


def test_metrics_dedup_counts(tmp_path: Path) -> None:
    svc = EvidenceService(config=_cfg())
    r = SearchResultItem(title="T", snippet="S", url="https://a/1")
    svc.to_evidence([r, r, r])  # 1 mantido + 2 removidos
    assert svc.metrics["deduped_sources_count"] >= 0
    assert svc.metrics["deduped_evidence_count"] >= 2

    claims = [
        Claim(claim_id="c1", text="PMEs carbono.", origin=EvidenceOrigin.EXTERNAL),
        Claim(claim_id="c2", text="PMEs  carbono!", origin=EvidenceOrigin.EXTERNAL),
    ]
    svc.build_graph("m", claims, [], [])
    assert svc.metrics["deduped_claims_count"] >= 1


def test_build_graph_dedupa_todos_e_persiste_metrics(tmp_path: Path) -> None:
    svc = EvidenceService(config=_cfg())
    r = SearchResultItem(title="T", snippet="S", url="https://a/1")
    sources, items = svc.to_evidence([r])
    claims = [Claim(claim_id="c1", text="claim", origin=EvidenceOrigin.EXTERNAL)]

    graph = svc.build_graph("m-metrics", claims, items, sources)
    assert graph.metrics["provider_used"] == "mock"

    save_evidence_graph(tmp_path, graph)
    data = json.loads(
        (tmp_path / "evidence" / "evidence_graph.json").read_text(encoding="utf-8")
    )
    assert "metrics" in data
    assert data["metrics"]["provider_used"] == "mock"
    assert "cache_hits" in data["metrics"]