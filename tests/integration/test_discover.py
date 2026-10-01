"""
Testes de integração do Modo DISCOVER (v5.2.0 + Evidence).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from backend.core.evidence.providers import MockSearchProvider, SearchResultItem
from backend.core.evidence.service import EvidenceService
from backend.discover.pipeline import DiscoverPipeline
from backend.discover.schemas import DiscoverRequest
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.models import MissionState
from backend.validate.schemas import ValidateRequest


class FakeDiscoverClient:
    def __init__(self, candidates: list[dict]) -> None:
        self._frame = {
            "theme": "serviços locais", "audience": "PMEs", "geography": "Brasil",
            "constraints": [], "attractiveness_criteria": ["dor forte", "MVP rápido"],
        }
        self._candidates = candidates

    async def complete(self, system_prompt, user_prompt, model=None, role=None) -> str:
        raise NotImplementedError

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        if "candidatos" in user_prompt.lower():
            return {"candidates": self._candidates}
        return self._frame


class FakeValidate:
    def __init__(self) -> None:
        self.requests: list[ValidateRequest] = []

    async def run(self, request, on_stage=None, mission_id=None) -> MissionState:
        self.requests.append(request)
        return MissionState(
            mission_id="vhand-123", project_id="p", mode=ProjectMode.VALIDATE,
            status=MissionStatus.COMPLETED, current_stage="report",
            mode_payload={"recommendation": {"verdict": "INVESTIGATE", "confidence": 0.6}},
        )


def _cand(title: str, **kw: Any) -> dict:
    base = {
        "title": title, "one_liner": f"resumo de {title}",
        "problem": "dor real caro lento difícil retrabalho",
        "audience": "PMEs de serviços", "why_now": "digitalização acelerada pós-2024",
        "solution_sketch": "MVP web com agendamento", "business_model_hint": "SaaS R$ 49/mês",
        "risks": ["concorrência"], "assumptions": ["PMEs pagam"], "tags": ["b2b", "saas"],
    }
    base.update(kw)
    return base


_CANDIDATES = [
    _cand("Agenda inteligente para barbearias"),
    _cand("Controle de estoque para restaurantes"),
    _cand("Relatórios de carbono para PMEs"),
    _cand("Rede social para tudo"),
    _cand("Agenda inteligente para barbearias e salões"),
]


def _pipe(tmp_path: Path, validate=None, evidence=None) -> DiscoverPipeline:
    return DiscoverPipeline(
        client=FakeDiscoverClient(_CANDIDATES),
        artifact_manager=ArtifactManager(root=tmp_path),
        validate_pipeline=validate,
        evidence_service=evidence,
    )


def test_discover_fluxo_completo_gera_artefatos(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    result = asyncio.run(pipe.run(DiscoverRequest(
        theme="Oportunidades de software para barbearias no Brasil",
        max_opportunities=3,
    )))

    assert 1 <= len(result.opportunities) <= 3
    scores = [p.score for p in result.opportunities]
    assert scores == sorted(scores, reverse=True)
    assert len(result.rejected) >= 2

    assert pipe.last_mission_id is not None
    mid = pipe.last_mission_id
    for fname in ("scope.json", "opportunities.json", "rejected.json",
                  "discover_report.md", "mission_state.json"):
        assert (tmp_path / mid / fname).exists(), f"artefato ausente: {fname}"

    report = (tmp_path / mid / "discover_report.md").read_text(encoding="utf-8")
    assert "# Discover Report" in report
    assert "Rejeitadas pelo Critic" in report


def test_discover_com_evidence_gera_grafo(tmp_path: Path) -> None:
    """v5.2.0: EvidenceService gera EvidenceGraph + evidence_level medium/high."""
    mock = MockSearchProvider()
    # Queries REAIS geradas por plan_queries("discover", scope):
    #   1) "serviços locais para PMEs em Brasil"
    #   2) "tendências de mercado serviços locais"
    # Fixtures com snippets ricos que têm overlap com as oportunidades.
    mock.add_fixture("serviços locais para PMEs em Brasil", [
        SearchResultItem(title="PMEs crescem",
                         snippet="PMEs adotam agenda inteligente para barbearias",
                         url="https://ibge.gov.br/pmes", publisher="IBGE"),
        SearchResultItem(title="Agendamento digital",
                         snippet="Barbearias contratam controle de estoque para restaurantes",
                         url="https://sebrae.com.br/agenda", publisher="Sebrae"),
        SearchResultItem(title="Carbono e PMEs",
                         snippet="Relatórios de carbono para PMEs ganham tração",
                         url="https://gov.br/carbono", publisher="Gov"),
    ])
    mock.add_fixture("tendências de mercado serviços locais", [
        SearchResultItem(title="Tendências 2025",
                         snippet="agenda inteligente para barbearias em alta",
                         url="https://trend.com/agenda", publisher="TrendCo"),
    ])
    evidence_svc = EvidenceService(provider=mock)
    pipe = _pipe(tmp_path, evidence=evidence_svc)
    result = asyncio.run(pipe.run(DiscoverRequest(theme="serviços locais", max_opportunities=3)))

    assert result.opportunities
    levels = [opp.evidence_level for opp in result.opportunities]
    assert any(level in ("medium", "high") for level in levels)

    assert pipe.last_mission_id is not None
    mid = pipe.last_mission_id
    evidence_dir = tmp_path / mid / "evidence"
    assert evidence_dir.exists()
    graph_file = evidence_dir / "evidence_graph.json"
    assert graph_file.exists()

    graph_data = json.loads(graph_file.read_text(encoding="utf-8"))
    assert graph_data["mission_id"] == mid
    assert len(graph_data["sources"]) >= 1
    assert len(graph_data["evidence_items"]) >= 1

    report = (tmp_path / mid / "discover_report.md").read_text(encoding="utf-8")
    assert "Evidências Externas e Sinais de Mercado" in report
    assert "IBGE" in report or "Sebrae" in report


def test_discover_handoff_envia_oportunidade_ao_validate(tmp_path: Path) -> None:
    fake_validate = FakeValidate()
    pipe = _pipe(tmp_path, validate=fake_validate)

    first = asyncio.run(pipe.run(DiscoverRequest(theme="serviços locais")))
    assert first.opportunities
    opp_id = first.opportunities[0].id

    second = asyncio.run(pipe.run(DiscoverRequest(
        theme="serviços locais", handoff_to_validate=True,
        selected_opportunity_id=opp_id,
    )))

    assert len(fake_validate.requests) == 1
    vreq = fake_validate.requests[0]
    assert vreq.name == first.opportunities[0].title
    assert vreq.problem == first.opportunities[0].problem

    assert second.handoff is not None
    assert second.handoff["opportunity_id"] == opp_id
    assert second.handoff["validate_mission_id"] == "vhand-123"

    assert pipe.last_mission_id is not None
    mid = pipe.last_mission_id
    state = json.loads((tmp_path / mid / "mission_state.json").read_text(encoding="utf-8"))
    assert state["mode_payload"]["handoff"]["validate_mission_id"] == "vhand-123"
    assert state["mode"] == ProjectMode.DISCOVER.value