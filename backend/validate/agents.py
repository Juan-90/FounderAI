"""
Agentes especializados do pipeline VALIDATE (v5.5.3 — Contrarian resiliente).

v5.5.3: ContrarianRiskAgent NUNCA levanta ValidateAgentError por skeptic_score:
  • ausente -> default 5;
  • texto ("7/10", "score: 8") -> extrai primeiro número via regex;
  • fora de [1,10] -> clamp.
v5.5.2: IdeaIntakeAgent tolerante (clarified_fields default {}).
v4.4.0 hotfix 2: _apply_defaults() preenche campos não-críticos ausentes.
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend.build.agents import LLMBuildClient
from backend.core.llm_client import (
    LLMClient,
    _clean_json,
    _sanitize_json_for_parse,
)
from backend.utils.payload_guard import require_clarified_fields


class ValidateAgentError(Exception):
    """Falha de contrato de um agente VALIDATE (JSON inválido/ausente)."""


_SYSTEM: str = (
    "Você é um consultor sênior de validação de produtos do FounderAI. "
    "Analise com rigor, separe evidência de inferência e seja específico. "
    "Responda APENAS com JSON válido, sem fences, sem texto extra. "
    "Inclua TODAS as chaves solicitadas, mesmo que com listas/textos vazios."
)

_SCORE_RE = re.compile(r"\d+(?:\.\d+)?")
_DEFAULT_SKEPTIC: int = 5


def _to_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        cleaned = _sanitize_json_for_parse(_clean_json(raw))
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise ValidateAgentError(
        "Resposta do LLM não pôde ser interpretada como objeto JSON."
    )


async def _call_json(client: Any, user_prompt: str) -> dict[str, Any]:
    method = getattr(client, "complete_json_with_fallback", client.complete_json)
    return await method(system_prompt=_SYSTEM, user_prompt=user_prompt)


def _apply_defaults(data: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    for key, value in defaults.items():
        data.setdefault(key, value)
    return data


def _require_keys(data: dict[str, Any], required: list[str], agent: str) -> None:
    missing = [k for k in required if k not in data]
    if missing:
        raise ValidateAgentError(
            f"{agent}: campos obrigatórios ausentes: {', '.join(missing)}"
        )


def _coerce_skeptic_score(value: Any) -> int:
    """v5.5.3: skeptic_score seguro — default 5, regex p/ texto, clamp [1,10]."""
    if isinstance(value, bool):
        return _DEFAULT_SKEPTIC
    if isinstance(value, int):
        score = value
    elif isinstance(value, float):
        score = int(round(value))
    elif isinstance(value, str):
        m = _SCORE_RE.search(value)
        if not m:
            return _DEFAULT_SKEPTIC
        score = int(round(float(m.group())))
    else:
        return _DEFAULT_SKEPTIC
    return max(1, min(10, score))


class IdeaIntakeAgent:
    """Estágio 1/7 — Normaliza a ideia e extrai premissas/lacunas. (tolerante v5.5.2)"""

    _DEFAULTS = {"assumptions": [], "gaps": []}
    _REQUIRED = ["summary"]

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def analyze(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        user = (
            "IDEIA BRUTA DO FUNDADOR:\n"
            f"{request_payload}\n\n"
            "Retorne JSON com EXATAMENTE: "
            '{"summary": "...", "assumptions": ["..."], "gaps": ["..."], '
            '"clarified_fields": {"name": ..., "target_audience": ..., "problem": ..., '
            '"solution": ..., "business_model": ..., "constraints": ...}}\n'
            "Cada campo de clarified_fields usa o valor do fundador ou null se ausente."
        )
        data = _apply_defaults(_to_dict(await _call_json(self._client, user)), self._DEFAULTS)
        _require_keys(data, self._REQUIRED, "IdeaIntakeAgent")
        data["clarified_fields"] = require_clarified_fields(data)
        return data


class ProblemMarketAgent:
    """Estágio 2/7 — Dor, gravidade, público; evidência vs inferência. (tolerante)"""

    _DEFAULTS = {"evidence": [], "inferences": [], "market_size_hint": "",
                 "audience_segment": ""}
    _REQUIRED = ["pain_description", "pain_severity"]

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def analyze(self, idea_profile: dict[str, Any]) -> dict[str, Any]:
        user = (
            "PERFIL DA IDEIA:\n"
            f"{idea_profile}\n\n"
            "Avalie a dor/mercado e retorne JSON com: "
            '{"pain_description": "...", "pain_severity": "low|medium|high|critical", '
            '"audience_segment": "...", "evidence": ["fato conhecido"], '
            '"inferences": ["hipótese não comprovada"], "market_size_hint": "..."}\n'
            "Inclua TODAS as chaves. Separe RIGOROSAMENTE evidência de inferência."
        )
        data = _apply_defaults(_to_dict(await _call_json(self._client, user)), self._DEFAULTS)
        _require_keys(data, self._REQUIRED, "ProblemMarketAgent")
        if data.get("pain_severity") not in ("low", "medium", "high", "critical"):
            raise ValidateAgentError("ProblemMarketAgent: pain_severity inválido.")
        return data


class CompetitorAgent:
    """Estágio 3/7 — Concorrentes, alternativas e diferenciais. (tolerante)"""

    _DEFAULTS = {"direct_competitors": [], "indirect_alternatives": [],
                 "our_differentiators": [], "status_quo": ""}
    _REQUIRED = ["status_quo"]

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def analyze(
        self, idea_profile: dict[str, Any], problem_market: dict[str, Any]
    ) -> dict[str, Any]:
        user = (
            "PERFIL DA IDEIA:\n" f"{idea_profile}\n\n"
            "ANÁLISE DE DOR/MERCADO:\n" f"{problem_market}\n\n"
            "Retorne JSON com: "
            '{"direct_competitors": [{"name": "...", "differentiator": "..."}], '
            '"indirect_alternatives": [{"name": "...", "why_used": "..."}], '
            '"status_quo": "...", "our_differentiators": ["..."]}\n'
            "Inclua TODAS as chaves. Considere planilhas/status quo como alternativas."
        )
        data = _apply_defaults(_to_dict(await _call_json(self._client, user)), self._DEFAULTS)
        _require_keys(data, self._REQUIRED, "CompetitorAgent")
        return data


class TechnicalFeasibilityAgent:
    """Estágio 4/7 — Complexidade, dados, riscos de IA, MVP técnico. (tolerante)"""

    _DEFAULTS = {"data_requirements": [], "ai_risks": [], "technical_mvp_outline": ""}
    _REQUIRED = ["complexity", "effort_weeks_estimate"]

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def analyze(
        self,
        idea_profile: dict[str, Any],
        problem_market: dict[str, Any],
        competitors: dict[str, Any],
    ) -> dict[str, Any]:
        user = (
            "PERFIL DA IDEIA:\n" f"{idea_profile}\n\n"
            "DOR/MERCADO:\n" f"{problem_market}\n\n"
            "CONCORRÊNCIA:\n" f"{competitors}\n\n"
            "Avalie a viabilidade técnica (NÃO gere código). Retorne JSON com: "
            '{"complexity": "low|medium|high|extreme", '
            '"data_requirements": ["..."], "ai_risks": ["..."], '
            '"technical_mvp_outline": "...", "effort_weeks_estimate": <int>}\n'
            "Inclua TODAS as chaves. effort_weeks_estimate deve ser inteiro (1..52)."
        )
        data = _apply_defaults(_to_dict(await _call_json(self._client, user)), self._DEFAULTS)
        _require_keys(data, self._REQUIRED, "TechnicalFeasibilityAgent")
        if not isinstance(data.get("effort_weeks_estimate"), int):
            raise ValidateAgentError(
                "TechnicalFeasibilityAgent: effort_weeks_estimate deve ser int."
            )
        return data


class ContrarianRiskAgent:
    """Estágio 5/7 — Cético tolerante a skeptic_score (v5.5.3)."""

    _DEFAULTS = {"regulatory_risks": [], "false_positive_risks": [],
                 "hidden_costs": [], "reasons_to_kill": []}

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def analyze(
        self,
        idea_profile: dict[str, Any],
        problem_market: dict[str, Any],
        competitors: dict[str, Any],
        technical_feasibility: dict[str, Any],
    ) -> dict[str, Any]:
        user = (
            "PERFIL DA IDEIA:\n" f"{idea_profile}\n\n"
            "DOR/MERCADO:\n" f"{problem_market}\n\n"
            "CONCORRÊNCIA:\n" f"{competitors}\n\n"
            "VIABILIDADE TÉCNICA:\n" f"{technical_feasibility}\n\n"
            "Seja ESTRITAMENTE cético: procure razões para NÃO construir. Retorne JSON com: "
            '{"regulatory_risks": ["..."], "false_positive_risks": ["..."], '
            '"hidden_costs": ["..."], "reasons_to_kill": ["..."], '
            '"skeptic_score": <int de 1 a 10, onde 10 = altíssimo ceticismo>}.\n'
            "Inclua TODAS as chaves. Não suavize críticas."
        )
        data = _apply_defaults(_to_dict(await _call_json(self._client, user)), self._DEFAULTS)
        # v5.5.3: nunca ValidateAgentError por skeptic_score
        data["skeptic_score"] = _coerce_skeptic_score(data.get("skeptic_score"))
        return data


class ExperimentDesignAgent:
    """Estágio 6/7 — Propõe 3 a 7 experimentos práticos. (estrito)"""

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def analyze(
        self,
        idea_profile: dict[str, Any],
        problem_market: dict[str, Any],
        evidence_gaps: list[str],
    ) -> dict[str, Any]:
        user = (
            "PERFIL DA IDEIA:\n" f"{idea_profile}\n\n"
            "DOR/MERCADO:\n" f"{problem_market}\n\n"
            "LACUNAS DE EVIDÊNCIA:\n" f"{evidence_gaps}\n\n"
            "Proponha entre 3 e 7 experimentos práticos (low-cost, 1-14 dias). "
            "Retorne JSON com: "
            '{"experiments": [{"hypothesis": "...", "method": "...", "metric": "...", '
            '"go_threshold": "...", "estimated_cost_days": <int>}]}.\n'
            "Cada experimento deve atacar uma lacuna de evidência específica."
        )
        data = _to_dict(await _call_json(self._client, user))
        if not isinstance(data, dict) or "experiments" not in data:
            raise ValidateAgentError("ExperimentDesignAgent: campo 'experiments' ausente.")
        experiments = data["experiments"]
        if not isinstance(experiments, list) or not (3 <= len(experiments) <= 7):
            raise ValidateAgentError(
                "ExperimentDesignAgent: quantidade de experimentos deve estar entre 3 e 7."
            )
        for i, exp in enumerate(experiments):
            if not isinstance(exp, dict):
                raise ValidateAgentError(
                    f"ExperimentDesignAgent: experimento #{i} não é dict."
                )
            for key in ("hypothesis", "method", "metric", "go_threshold", "estimated_cost_days"):
                if key not in exp:
                    raise ValidateAgentError(
                        f"ExperimentDesignAgent: experimento #{i} sem campo '{key}'."
                    )
        return data


class ValidationSynthesizer:
    """Estágio 7/7 — Consolida veredito, confiança, rationale e condições. (estrito)"""

    _VALID_VERDICTS = {"INVESTIGATE", "BUILD", "PIVOT", "DISCARD"}

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def synthesize(self, all_stages: dict[str, Any]) -> dict[str, Any]:
        user = (
            "TODOS OS ESTÁGIOS DO VALIDATE:\n"
            f"{all_stages}\n\n"
            "Consolide o veredito final em JSON com: "
            '{"verdict": "INVESTIGATE|BUILD|PIVOT|DISCARD", '
            '"confidence": <float 0.0 a 1.0>, '
            '"rationale": "...", "conditions": ["..."], "final_report": "..."}.\n'
            "• INVESTIGATE: promissor mas com lacunas críticas de evidência.\n"
            "• BUILD:     validado o suficiente para entrar em BUILD Mode.\n"
            "• PIVOT:     problema real, mas solução/segmento errado.\n"
            "• DISCARD:   premissas fracas demais; abandone a ideia.\n"
            "Inclua TODAS as chaves. confidence reflete o suporte das evidências."
        )
        data = _to_dict(await _call_json(self._client, user))
        _require_keys(
            data,
            ["verdict", "confidence", "rationale", "conditions", "final_report"],
            "ValidationSynthesizer",
        )
        if data["verdict"] not in self._VALID_VERDICTS:
            raise ValidateAgentError(
                f"ValidationSynthesizer: verdict '{data['verdict']}' inválido."
            )
        if not isinstance(data["confidence"], (int, float)):
            raise ValidateAgentError(
                "ValidationSynthesizer: confidence deve ser numérico."
            )
        return data