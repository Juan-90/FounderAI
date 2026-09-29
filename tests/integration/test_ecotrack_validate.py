"""
Caso canônico do EcoTrack-IA — North Star do Modo VALIDATE (v4.4.0).

Cobre (sem Docker, roda sempre em CI):
  • Pipeline executa 100% e persiste os 8 artefatos;
  • Veredito válido ∈ {INVESTIGATE, BUILD, PIVOT, DISCARD};
  • evidence_gaps preenchido;
  • Falha graciosa salva validation_report.md + mission_state.json.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus
from backend.validate.pipeline import ValidatePipeline
from backend.validate.schemas import ValidateRequest, ValidationVerdict

INTENT_ECOTRACK = (
    "Validar o EcoTrack-IA, um sistema com IA para pequenas empresas acompanharem "
    "e reduzirem sua pegada de carbono, com relatórios simples e recomendações automáticas."
)

_INTAKE = {
    "summary": "EcoTrack-IA: rastreio de pegada de carbono para PMEs",
    "assumptions": ["PMEs querem medir carbono", "dispostas a pagar SaaS"],
    "gaps": ["sem dados de willingness-to-pay", "precisão de fatores de emissão"],
    "clarified_fields": {
        "name": "EcoTrack-IA", "target_audience": "pequenas empresas",
        "problem": "medir/reduzir pegada de carbono",
        "solution": "IA + relatórios simples", "business_model": "SaaS",
        "constraints": "equipe pequena",
    },
}
_PROBLEM = {
    "pain_description": "PMEs não conseguem medir impacto ambiental.",
    "pain_severity": "high",
    "audience_segment": "PMEs de varejo/serviços",
    "evidence": ["regulação ESG crescente para cadeias de suprimento"],
    "inferences": ["PMEs pagariam R$ 99/mês", "IA reduz custo de auditoria"],
    "market_size_hint": "R$ 1,2B no BR",
}
_COMPETITORS = {
    "direct_competitors": [{"name": "Sweep", "differentiator": "foco enterprise"}],
    "indirect_alternatives": [{"name": "planilha", "why_used": "grátis"}],
    "status_quo": "Maioria não mede",
    "our_differentiators": ["foco PME + automação IA"],
}
_TECH = {
    "complexity": "medium",
    "data_requirements": ["fatores de emissão EPA/IBGE", "contas de energia"],
    "ai_risks": ["alucinação em recomendações"],
    "technical_mvp_outline": "upload de contas + dashboard + recomendações",
    "effort_weeks_estimate": 10,
}
_CONTRARIAN = {
    "regulatory_risks": ["greenwashing / publicidade enganosa"],
    "false_positive_risks": ["dados autodeclarados imprecisos"],
    "hidden_costs": ["aquisição de fatores de emissão confiáveis"],
    "reasons_to_kill": ["planilha resolve caso básico"],
    "skeptic_score": 6,
}
_EXPERIMENTS = {
    "experiments": [
        {"hypothesis": "PMEs pagam R$99/mês", "method": "landing + pricing test",
         "metric": "conversão > 2%", "go_threshold": "20 signups pagos", "estimated_cost_days": 7},
        {"hypothesis": "dados autodeclarados são suficientes", "method": "piloto com 5 PMEs",
         "metric": "erro < 15% vs conta real", "go_threshold": "4/5 dentro do erro", "estimated_cost_days": 14},
        {"hypothesis": "IA gera recomendações acionáveis", "method": "avaliação cega por especialista",
         "metric": "score > 4/5", "go_threshold": "média >= 4", "estimated_cost_days": 5},
    ]
}
_SYNTH = {
    "verdict": "INVESTIGATE",
    "confidence": 0.62,
    "rationale": "Dor real e regulação favorável, mas WTP e precisão de dados não validados.",
    "conditions": ["executar 3 experimentos em 30 dias"],
    "final_report": "# Validation Report — EcoTrack-IA\n\nVeredito: INVESTIGATE...",
}


class _FakeQueueClient:
    """Retorna payloads em ordem de chamada (7 estágios)."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._q = list(payloads)

    async def complete(self, system_prompt, user_prompt, model=None, role=None) -> str:
        raise NotImplementedError

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        if not self._q:
            raise RuntimeError("FakeQueueClient: payloads esgotados.")
        return self._q.pop(0)


def _payloads() -> list[dict[str, Any]]:
    return [_INTAKE, _PROBLEM, _COMPETITORS, _TECH, _CONTRARIAN, _EXPERIMENTS, _SYNTH]


_EXPECTED_ARTIFACTS = [
    "idea_profile.json", "market_problem.md", "competitors.md",
    "technical_feasibility.md", "risks_contrarian.md", "experiments.md",
    "validation_report.md", "mission_state.json",
]


def test_ecotrack_pipeline_persiste_8_artefatos_e_verdict_valido(tmp_path: Path) -> None:
    pipe = ValidatePipeline(
        client=_FakeQueueClient(_payloads()),
        artifact_manager=ArtifactManager(root=tmp_path),
    )
    state = asyncio.run(pipe.run(ValidateRequest(idea_text=INTENT_ECOTRACK, name="EcoTrack-IA")))

    assert state.status == MissionStatus.COMPLETED
    verdict = state.mode_payload["recommendation"]["verdict"]
    assert verdict in {v.value for v in ValidationVerdict}

    mid = state.mission_id
    for fname in _EXPECTED_ARTIFACTS:
        assert (tmp_path / mid / fname).exists(), f"artefato ausente: {fname}"

    # idea_profile.json é JSON válido
    idea = json.loads((tmp_path / mid / "idea_profile.json").read_text(encoding="utf-8"))
    assert idea["summary"].startswith("EcoTrack")


def test_ecotrack_evidence_gaps_preenchido(tmp_path: Path) -> None:
    pipe = ValidatePipeline(
        client=_FakeQueueClient(_payloads()),
        artifact_manager=ArtifactManager(root=tmp_path),
    )
    state = asyncio.run(pipe.run(ValidateRequest(idea_text=INTENT_ECOTRACK)))

    gaps = state.mode_payload["evidence_gaps"]
    assert isinstance(gaps, list) and len(gaps) >= 2
    assert "sem dados de willingness-to-pay" in gaps
    assert "PMEs pagariam R$ 99/mês" in gaps  # inferência tratada como lacuna
    assert len(state.mode_payload["hypotheses"]) == len(gaps)
    assert len(state.mode_payload["experiments"]) == 3


def test_validate_falha_graciosa_salva_report_e_state(tmp_path: Path) -> None:
    class _BoomClient(_FakeQueueClient):
        async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
            raise RuntimeError("LLM caiu no estágio 2")

    pipe = ValidatePipeline(
        client=_BoomClient(_payloads()),
        artifact_manager=ArtifactManager(root=tmp_path),
    )
    state = asyncio.run(pipe.run(ValidateRequest(idea_text=INTENT_ECOTRACK)))

    assert state.status == MissionStatus.FAILED
    assert "error" in state.mode_payload
    mid = state.mission_id
    assert (tmp_path / mid / "mission_state.json").exists()
    assert (tmp_path / mid / "validation_report.md").exists()
    report = (tmp_path / mid / "validation_report.md").read_text(encoding="utf-8")
    assert "LLM caiu no estágio 2" in report