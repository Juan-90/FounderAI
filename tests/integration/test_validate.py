"""
Testes de integração do Modo VALIDATE (v5.2.0 + Evidence).

Usa um FakeValidateClient com fila de payloads (ordem das 7 chamadas),
mantendo o teste determinístico e sem LLM real.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from backend.core.evidence.providers import MockSearchProvider, SearchResultItem
from backend.core.evidence.service import EvidenceService
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus
from backend.validate.pipeline import ValidatePipeline
from backend.validate.schemas import ValidateRequest

_INTAKE = {
    "summary": "app de agendamento para barbearias",
    "assumptions": ["barbearias querem agenda digital"],
    "gaps": ["sem dados de willingness-to-pay"],
    "clarified_fields": {"name": "BarberAgenda", "target_audience": "barbearias",
                         "problem": "agendamento manual", "solution": "web app",
                         "business_model": "SaaS", "constraints": "tempo"},
}
_PROBLEM = {
    "pain_description": "barbearias perdem tempo com agendamento manual",
    "pain_severity": "high", "audience_segment": "barbearias",
    "evidence": ["digitalização crescente"], "inferences": ["pagariam R$49"],
    "market_size_hint": "R$ 500M",
}
_COMPETITORS = {
    "direct_competitors": [{"name": "Booksy", "differentiator": "marketplace"}],
    "indirect_alternatives": [{"name": "WhatsApp", "why_used": "grátis"}],
    "status_quo": "agenda de papel", "our_differentiators": ["foco local"],
}
_TECH = {
    "complexity": "medium", "data_requirements": ["calendar API"],
    "ai_risks": [], "technical_mvp_outline": "web app", "effort_weeks_estimate": 8,
}
_CONTRARIAN = {
    "regulatory_risks": [], "false_positive_risks": [], "hidden_costs": [],
    "reasons_to_kill": ["concorrência forte"], "skeptic_score": 6,
}
_EXPERIMENTS = {
    "experiments": [
        {"hypothesis": "H1", "method": "landing", "metric": "CTR", "go_threshold": "5%",
         "estimated_cost_days": 5},
        {"hypothesis": "H2", "method": "interviews", "metric": "confirmações",
         "go_threshold": "8/10", "estimated_cost_days": 7},
        {"hypothesis": "H3", "method": "smoke", "metric": "conversão", "go_threshold": "2%",
         "estimated_cost_days": 6},
    ]
}
_SYNTH = {
    "verdict": "INVESTIGATE", "confidence": 0.7,
    "rationale": "dor real, evidências fracas", "conditions": ["validar WTP"],
    "final_report": "# Validation Report\n\nVeredito: INVESTIGATE",
}


class FakeValidateClient:
    def __init__(self) -> None:
        self._queue = [_INTAKE, _PROBLEM, _COMPETITORS, _TECH, _CONTRARIAN,
                       _EXPERIMENTS, _SYNTH]

    async def complete(self, system_prompt, user_prompt, model=None, role=None) -> str:
        raise NotImplementedError

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        return self._queue.pop(0)


def _pipe(tmp_path: Path, evidence=None) -> ValidatePipeline:
    return ValidatePipeline(
        client=FakeValidateClient(),
        artifact_manager=ArtifactManager(root=tmp_path),
        evidence_service=evidence,
    )


def test_validate_fluxo_completo(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    state = asyncio.run(pipe.run(ValidateRequest(
        idea_text="Quero validar um app de agendamento para barbearias")))

    assert state.status == MissionStatus.COMPLETED
    assert pipe.last_mission_id is not None
    mid = pipe.last_mission_id
    for fname in ("idea_profile.json", "market_problem.md", "competitors.md",
                  "technical_feasibility.md", "risks_contrarian.md", "experiments.md",
                  "validation_report.md", "mission_state.json"):
        assert (tmp_path / mid / fname).exists(), f"artefato ausente: {fname}"


def test_validate_com_evidence_gera_grafo_e_secao(tmp_path: Path) -> None:
    """v5.2.0: EvidenceService gera EvidenceGraph + seção 'Evidence vs Opinion'."""
    mock = MockSearchProvider()
    # Queries REAIS geradas por plan_queries("validate", payload):
    #   1) "barbearias perdem tempo com agendamento manual barbearias"
    #   2) "concorrentes barbearias perdem tempo com agendamento manual"
    mock.add_fixture("barbearias perdem tempo com agendamento manual barbearias", [
        SearchResultItem(title="Pesquisa Sebrae 2024",
                         snippet="70% das barbearias ainda usam agenda de papel",
                         url="https://sebrae.com.br/barbearias", publisher="Sebrae"),
    ])
    mock.add_fixture("concorrentes barbearias perdem tempo com agendamento manual", [
        SearchResultItem(title="Booksy vs Trinks",
                         snippet="concorrentes dominam 60% do agendamento online",
                         url="https://techcrunch.com/booking", publisher="TechCrunch"),
    ])
    pipe = _pipe(tmp_path, evidence=EvidenceService(provider=mock))
    state = asyncio.run(pipe.run(ValidateRequest(
        idea_text="Quero validar um app de agendamento para barbearias")))

    assert state.status == MissionStatus.COMPLETED
    assert pipe.last_mission_id is not None
    mid = pipe.last_mission_id

    evidence_dir = tmp_path / mid / "evidence"
    assert evidence_dir.exists()
    graph_file = evidence_dir / "evidence_graph.json"
    assert graph_file.exists()
    graph_data = json.loads(graph_file.read_text(encoding="utf-8"))
    assert graph_data["mission_id"] == mid
    assert len(graph_data["sources"]) >= 2
    assert len(graph_data["evidence_items"]) >= 2
    assert any(c["evidence_ids"] for c in graph_data["claims"])

    report = (tmp_path / mid / "validation_report.md").read_text(encoding="utf-8")
    assert "Evidence vs Opinion" in report
    assert "[Source:" in report
    assert "Sebrae" in report
    assert "TechCrunch" in report


def test_validate_evidence_gaps_registrados(tmp_path: Path) -> None:
    # Mock sem fixtures -> gera resultados genéricos; gaps derivados + reais presentes
    pipe = _pipe(tmp_path, evidence=EvidenceService(provider=MockSearchProvider()))
    state = asyncio.run(pipe.run(ValidateRequest(
        idea_text="Quero validar um app de agendamento para barbearias")))

    assert state.status == MissionStatus.COMPLETED
    gaps = state.mode_payload.get("evidence_gaps", [])
    assert len(gaps) >= 1