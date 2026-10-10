"""
Testes unitários dos agentes do pipeline VALIDATE (v4.4.0).

Cobre:
  • Schemas (ValidateRequest, ValidationVerdict, ValidatePayload);
  • Cada um dos 7 agentes com JSON válido do FakeClient;
  • Validação de contrato (campos obrigatórios ausentes / inválidos).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.domain.enums import ProjectType
from backend.validate.agents import (
    CompetitorAgent,
    ContrarianRiskAgent,
    ExperimentDesignAgent,
    IdeaIntakeAgent,
    ProblemMarketAgent,
    TechnicalFeasibilityAgent,
    ValidateAgentError,
    ValidationSynthesizer,
)
from backend.validate.schemas import (
    ValidatePayload,
    ValidateRequest,
    ValidationVerdict,
)


# ─────────────────────────────────────────────────────────────
# FakeClient (mock do LLM)
# ─────────────────────────────────────────────────────────────

class FakeValidateClient:
    """Cliente fake que retorna sempre o mesmo payload JSON."""

    def __init__(self, json_payload: dict[str, Any]) -> None:
        self._json = json_payload
        self.system_prompts: list[str] = []
        self.user_prompts: list[str] = []

    async def complete(self, system_prompt, user_prompt, model=None, role=None) -> str:
        raise NotImplementedError("FakeValidateClient é apenas para JSON.")

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        self.system_prompts.append(system_prompt)
        self.user_prompts.append(user_prompt)
        return self._json


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────

def test_validate_request_aceita_todos_os_campos() -> None:
    req = ValidateRequest(
        idea_text="App de rastreamento de pegada de carbono",
        name="EcoTrack",
        target_audience="Consumidores conscientes 25-40 anos",
        problem="Dificuldade de medir impacto ambiental individual",
        solution="App que agrega dados de consumo e sugere reduções",
        business_model="Assinatura freemium",
        constraints="Equipe de 3 devs, 6 meses",
        context_files=["research.md"],
        project_type=ProjectType.WEB_APP,
    )
    assert req.idea_text.startswith("App de rastreamento")
    assert req.name == "EcoTrack"
    assert req.project_type == ProjectType.WEB_APP
    assert req.context_files == ["research.md"]


def test_validate_request_minimo() -> None:
    req = ValidateRequest(idea_text="Uma ideia qualquer")
    assert req.name is None
    assert req.target_audience is None
    assert req.context_files == []
    assert req.project_type is None


def test_validation_verdict_enum() -> None:
    assert ValidationVerdict.INVESTIGATE.value == "INVESTIGATE"
    assert ValidationVerdict.BUILD.value == "BUILD"
    assert ValidationVerdict.PIVOT.value == "PIVOT"
    assert ValidationVerdict.DISCARD.value == "DISCARD"


def test_validate_payload_build() -> None:
    payload = ValidatePayload.build(
        idea_profile={"summary": "x"},
        problem_market={"pain_severity": "high"},
        recommendation={"verdict": "BUILD"},
    )
    assert payload["idea_profile"] == {"summary": "x"}
    assert payload["problem_market"] == {"pain_severity": "high"}
    assert payload["recommendation"] == {"verdict": "BUILD"}
    # defaults preenchidos
    assert payload["competitors"] == {}
    assert payload["hypotheses"] == []
    assert payload["experiments"] == []
    assert payload["evidence_gaps"] == []
    assert payload["final_report"] == ""


# ─────────────────────────────────────────────────────────────
# Estágio 1 — IdeaIntakeAgent
# ─────────────────────────────────────────────────────────────

_INTAKE_OK = {
    "summary": "App de pegada de carbono",
    "assumptions": ["usuários querem medir impacto"],
    "gaps": ["não há dados de aceitação de preço"],
    "clarified_fields": {
        "name": "EcoTrack", "target_audience": "25-40 anos",
        "problem": "medir impacto", "solution": "app agregador",
        "business_model": "freemium", "constraints": "6 meses",
    },
}


def test_idea_intake_retorna_dict_completo() -> None:
    agent = IdeaIntakeAgent(client=FakeValidateClient(_INTAKE_OK))
    out = _run(agent.analyze({"idea_text": "EcoTrack"}))
    assert out["summary"] == "App de pegada de carbono"
    assert isinstance(out["assumptions"], list)
    assert isinstance(out["gaps"], list)
    assert "name" in out["clarified_fields"]


def test_idea_intake_summary_ausente_raise() -> None:
    """summary segue crítico (v5.5.2): ausente -> ValidateAgentError."""
    bad = {"assumptions": [], "gaps": [], "clarified_fields": {}}  # falta summary
    agent = IdeaIntakeAgent(client=FakeValidateClient(bad))
    with pytest.raises(ValidateAgentError, match="summary"):
        asyncio.run(agent.analyze({}))


def test_idea_intake_clarified_fields_omitido_default() -> None:
    """v5.5.2: clarified_fields omitido -> default {} (sem raise)."""
    bad = {"summary": "x", "assumptions": [], "gaps": []}  # falta clarified_fields
    agent = IdeaIntakeAgent(client=FakeValidateClient(bad))
    out = asyncio.run(agent.analyze({}))
    assert out["clarified_fields"] == {}
    assert out["assumptions"] == []
    assert out["gaps"] == []


# ─────────────────────────────────────────────────────────────
# Estágio 2 — ProblemMarketAgent
# ─────────────────────────────────────────────────────────────

_PROBLEM_OK = {
    "pain_description": "Usuários não sabem seu impacto ambiental.",
    "pain_severity": "high",
    "audience_segment": "Consumidores urbanos 25-40",
    "evidence": ["pesquisa X mostra 70% de interesse"],
    "inferences": ["usuários pagariam R$ 20/mês"],
    "market_size_hint": "R$ 500M no Brasil",
}


def test_problem_market_retorna_dict_completo() -> None:
    agent = ProblemMarketAgent(client=FakeValidateClient(_PROBLEM_OK))
    out = _run(agent.analyze(_INTAKE_OK))
    assert out["pain_severity"] == "high"
    assert isinstance(out["evidence"], list)
    assert isinstance(out["inferences"], list)


def test_problem_market_severity_invalida_raise() -> None:
    bad = dict(_PROBLEM_OK, pain_severity="muito_alta")
    agent = ProblemMarketAgent(client=FakeValidateClient(bad))
    with pytest.raises(ValidateAgentError, match="pain_severity"):
        _run(agent.analyze(_INTAKE_OK))


# ─────────────────────────────────────────────────────────────
# Estágio 3 — CompetitorAgent
# ─────────────────────────────────────────────────────────────

_COMPETITORS_OK = {
    "direct_competitors": [{"name": "Joro", "differentiator": "foco em food"}],
    "indirect_alternatives": [{"name": "planilha Excel", "why_used": "grátis"}],
    "status_quo": "Maioria não mede",
    "our_differentiators": ["automação via APIs de bancos"],
}


def test_competitor_retorna_dict_completo() -> None:
    agent = CompetitorAgent(client=FakeValidateClient(_COMPETITORS_OK))
    out = _run(agent.analyze(_INTAKE_OK, _PROBLEM_OK))
    assert out["direct_competitors"][0]["name"] == "Joro"
    assert isinstance(out["indirect_alternatives"], list)
    assert out["status_quo"] == "Maioria não mede"


# ─────────────────────────────────────────────────────────────
# Estágio 4 — TechnicalFeasibilityAgent
# ─────────────────────────────────────────────────────────────

_TECH_OK = {
    "complexity": "medium",
    "data_requirements": ["APIs bancárias", "fatores de emissão EPA"],
    "ai_risks": ["modelo de classificação de transações"],
    "technical_mvp_outline": "Ingestão de CSV + dashboard básico",
    "effort_weeks_estimate": 8,
}


def test_tech_feasibility_retorna_dict_completo() -> None:
    agent = TechnicalFeasibilityAgent(client=FakeValidateClient(_TECH_OK))
    out = _run(agent.analyze(_INTAKE_OK, _PROBLEM_OK, _COMPETITORS_OK))
    assert out["complexity"] == "medium"
    assert out["effort_weeks_estimate"] == 8


def test_tech_feasibility_effort_nao_int_raise() -> None:
    bad = dict(_TECH_OK, effort_weeks_estimate="oito")
    agent = TechnicalFeasibilityAgent(client=FakeValidateClient(bad))
    with pytest.raises(ValidateAgentError, match="effort_weeks_estimate"):
        _run(agent.analyze(_INTAKE_OK, _PROBLEM_OK, _COMPETITORS_OK))


# ─────────────────────────────────────────────────────────────
# Estágio 5 — ContrarianRiskAgent
# ─────────────────────────────────────────────────────────────

_CONTRARIAN_OK = {
    "regulatory_risks": ["LGPD sobre dados financeiros"],
    "false_positive_risks": ["usuários mentem sobre consumo"],
    "hidden_costs": ["manutenção de integrações bancárias"],
    "reasons_to_kill": ["planilha resolve 80% do caso por R$ 0"],
    "skeptic_score": 7,
}


def test_contrarian_retorna_dict_completo() -> None:
    agent = ContrarianRiskAgent(client=FakeValidateClient(_CONTRARIAN_OK))
    out = _run(agent.analyze(_INTAKE_OK, _PROBLEM_OK, _COMPETITORS_OK, _TECH_OK))
    assert out["skeptic_score"] == 7
    assert isinstance(out["reasons_to_kill"], list)


def test_contrarian_score_fora_do_intervalo_clamp() -> None:
    """v5.5.3: skeptic_score fora de [1,10] é clampado, não raise."""
    hi = dict(_CONTRARIAN_OK, skeptic_score=15)
    lo = dict(_CONTRARIAN_OK, skeptic_score=0)
    agent_hi = ContrarianRiskAgent(client=FakeValidateClient(hi))
    agent_lo = ContrarianRiskAgent(client=FakeValidateClient(lo))
    out_hi = asyncio.run(agent_hi.analyze({}, {}, {}, {}))
    out_lo = asyncio.run(agent_lo.analyze({}, {}, {}, {}))
    assert out_hi["skeptic_score"] == 10
    assert out_lo["skeptic_score"] == 1


def test_contrarian_score_ausente_default() -> None:
    """v5.5.3: skeptic_score ausente -> default 5."""
    bad = dict(_CONTRARIAN_OK)
    bad.pop("skeptic_score", None)
    agent = ContrarianRiskAgent(client=FakeValidateClient(bad))
    out = asyncio.run(agent.analyze({}, {}, {}, {}))
    assert out["skeptic_score"] == 5


# ─────────────────────────────────────────────────────────────
# Estágio 6 — ExperimentDesignAgent
# ─────────────────────────────────────────────────────────────

_EXPERIMENTS_OK = {
    "experiments": [
        {"hypothesis": "H1", "method": "landing page", "metric": "CTR > 5%",
         "go_threshold": "50 signups", "estimated_cost_days": 3},
        {"hypothesis": "H2", "method": "interviews", "metric": "8/10 confirmam dor",
         "go_threshold": "8 confirmações", "estimated_cost_days": 5},
        {"hypothesis": "H3", "method": "smoke test", "metric": "conversão > 2%",
         "go_threshold": "20 conversões", "estimated_cost_days": 7},
    ]
}


def test_experiment_design_retorna_3_a_7() -> None:
    agent = ExperimentDesignAgent(client=FakeValidateClient(_EXPERIMENTS_OK))
    out = _run(agent.analyze(_INTAKE_OK, _PROBLEM_OK, ["gap1", "gap2"]))
    assert 3 <= len(out["experiments"]) <= 7
    assert out["experiments"][0]["hypothesis"] == "H1"


def test_experiment_design_menos_de_3_raise() -> None:
    bad = {"experiments": [
        {"hypothesis": "H1", "method": "m", "metric": "x",
         "go_threshold": "t", "estimated_cost_days": 1},
    ]}
    agent = ExperimentDesignAgent(client=FakeValidateClient(bad))
    with pytest.raises(ValidateAgentError, match="3 e 7"):
        _run(agent.analyze(_INTAKE_OK, _PROBLEM_OK, []))


def test_experiment_design_mais_de_7_raise() -> None:
    exp = {"hypothesis": "H", "method": "m", "metric": "x",
           "go_threshold": "t", "estimated_cost_days": 1}
    bad = {"experiments": [exp] * 8}
    agent = ExperimentDesignAgent(client=FakeValidateClient(bad))
    with pytest.raises(ValidateAgentError, match="3 e 7"):
        _run(agent.analyze(_INTAKE_OK, _PROBLEM_OK, []))


def test_experiment_design_campo_ausente_no_experimento_raise() -> None:
    bad = {"experiments": [
        {"hypothesis": "H1", "method": "m"},  # falta metric/go/cost
        {"hypothesis": "H2", "method": "m", "metric": "x",
         "go_threshold": "t", "estimated_cost_days": 1},
        {"hypothesis": "H3", "method": "m", "metric": "x",
         "go_threshold": "t", "estimated_cost_days": 1},
    ]}
    agent = ExperimentDesignAgent(client=FakeValidateClient(bad))
    with pytest.raises(ValidateAgentError, match="metric"):
        _run(agent.analyze(_INTAKE_OK, _PROBLEM_OK, []))


# ─────────────────────────────────────────────────────────────
# Estágio 7 — ValidationSynthesizer
# ─────────────────────────────────────────────────────────────

_SYNTH_OK = {
    "verdict": "INVESTIGATE",
    "confidence": 0.6,
    "rationale": "Dor real mas evidências fracas; execute experimentos.",
    "conditions": ["executar 3 experimentos em 30 dias"],
    "final_report": "# Relatório Final\n...",
}


def test_synthesizer_retorna_verdict_valido() -> None:
    agent = ValidationSynthesizer(client=FakeValidateClient(_SYNTH_OK))
    out = _run(agent.synthesize({"idea_profile": _INTAKE_OK}))
    assert out["verdict"] == "INVESTIGATE"
    assert out["confidence"] == 0.6
    assert isinstance(out["conditions"], list)


def test_synthesizer_todos_os_verdicts_sao_aceitos() -> None:
    for verdict in ("INVESTIGATE", "BUILD", "PIVOT", "DISCARD"):
        payload = dict(_SYNTH_OK, verdict=verdict)
        agent = ValidationSynthesizer(client=FakeValidateClient(payload))
        out = _run(agent.synthesize({}))
        assert out["verdict"] == verdict


def test_synthesizer_verdict_invalido_raise() -> None:
    bad = dict(_SYNTH_OK, verdict="MAYBE")
    agent = ValidationSynthesizer(client=FakeValidateClient(bad))
    with pytest.raises(ValidateAgentError, match="verdict"):
        _run(agent.synthesize({}))


def test_synthesizer_confidence_nao_numerica_raise() -> None:
    bad = dict(_SYNTH_OK, confidence="alta")
    agent = ValidationSynthesizer(client=FakeValidateClient(bad))
    with pytest.raises(ValidateAgentError, match="confidence"):
        _run(agent.synthesize({}))