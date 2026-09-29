"""
Agentes especializados do pipeline VALIDATE (v4.4.0).

Cada agente encapsula uma chamada ao LLMClient com prompt estruturado e
retorna um dict (não string) com os campos específicos de cada estágio.
Usa o Protocol LLMBuildClient (já existente em build/agents.py).
"""

from __future__ import annotations

from typing import Any, Protocol

from backend.build.agents import LLMBuildClient
from backend.core.llm_client import LLMClient


class ValidateAgentError(Exception):
    """Falha de contrato de um agente VALIDATE (JSON inválido/ausente)."""


_SYSTEM: str = (
    "Você é um consultor sênior de validação de produtos do FounderAI. "
    "Analise com rigor, separe evidência de inferência e seja específico. "
    "Responda APENAS com JSON válido, sem fences, sem texto extra."
)


def _require_keys(data: dict[str, Any], required: list[str], agent: str) -> None:
    missing = [k for k in required if k not in data]
    if missing:
        raise ValidateAgentError(
            f"{agent}: campos obrigatórios ausentes: {', '.join(missing)}"
        )


class IdeaIntakeAgent:
    """
    Estágio 1/7 — Normaliza a ideia e extrai premissas/lacunas.

    Saída:
        {
          "summary": str,
          "assumptions": list[str],
          "gaps": list[str],
          "clarified_fields": dict[str, str | None]
        }
    """

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
        data = await self._client.complete_json(system_prompt=_SYSTEM, user_prompt=user)
        _require_keys(data, ["summary", "assumptions", "gaps", "clarified_fields"],
                      "IdeaIntakeAgent")
        return data


class ProblemMarketAgent:
    """
    Estágio 2/7 — Avalia dor, gravidade, público e distingue evidência vs inferência.

    Saída:
        {
          "pain_description": str,
          "pain_severity": "low" | "medium" | "high" | "critical",
          "audience_segment": str,
          "evidence": list[str],
          "inferences": list[str],
          "market_size_hint": str
        }
    """

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
            "Separe RIGOROSAMENTE o que é evidência do que é inferência."
        )
        data = await self._client.complete_json(system_prompt=_SYSTEM, user_prompt=user)
        _require_keys(
            data,
            ["pain_description", "pain_severity", "audience_segment",
             "evidence", "inferences", "market_size_hint"],
            "ProblemMarketAgent",
        )
        if data.get("pain_severity") not in ("low", "medium", "high", "critical"):
            raise ValidateAgentError(
                "ProblemMarketAgent: pain_severity inválido."
            )
        return data


class CompetitorAgent:
    """
    Estágio 3/7 — Mapeia concorrentes, alternativas (incluindo planilhas/status quo)
    e diferenciais.

    Saída:
        {
          "direct_competitors": [{"name": str, "differentiator": str}, ...],
          "indirect_alternatives": [{"name": str, "why_used": str}, ...],
          "status_quo": str,
          "our_differentiators": list[str]
        }
    """

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
            "Considere planilhas, processos manuais e status quo como alternativas válidas."
        )
        data = await self._client.complete_json(system_prompt=_SYSTEM, user_prompt=user)
        _require_keys(
            data,
            ["direct_competitors", "indirect_alternatives",
             "status_quo", "our_differentiators"],
            "CompetitorAgent",
        )
        return data


class TechnicalFeasibilityAgent:
    """
    Estágio 4/7 — Avalia complexidade, dados, riscos de IA e MVP técnico (sem gerar código).

    Saída:
        {
          "complexity": "low" | "medium" | "high" | "extreme",
          "data_requirements": list[str],
          "ai_risks": list[str],
          "technical_mvp_outline": str,
          "effort_weeks_estimate": int
        }
    """

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
            "effort_weeks_estimate deve ser inteiro (1..52)."
        )
        data = await self._client.complete_json(system_prompt=_SYSTEM, user_prompt=user)
        _require_keys(
            data,
            ["complexity", "data_requirements", "ai_risks",
             "technical_mvp_outline", "effort_weeks_estimate"],
            "TechnicalFeasibilityAgent",
        )
        if not isinstance(data.get("effort_weeks_estimate"), int):
            raise ValidateAgentError(
                "TechnicalFeasibilityAgent: effort_weeks_estimate deve ser int."
            )
        return data


class ContrarianRiskAgent:
    """
    Estágio 5/7 — Papel estritamente cético: riscos regulatórios, falsos positivos,
    custos ocultos. Deve procurar razões para NÃO construir.

    Saída:
        {
          "regulatory_risks": list[str],
          "false_positive_risks": list[str],
          "hidden_costs": list[str],
          "reasons_to_kill": list[str],
          "skeptic_score": int
        }
    """

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
            "O papel deste agente é o devil's advocate; não suavize críticas."
        )
        data = await self._client.complete_json(system_prompt=_SYSTEM, user_prompt=user)
        _require_keys(
            data,
            ["regulatory_risks", "false_positive_risks", "hidden_costs",
             "reasons_to_kill", "skeptic_score"],
            "ContrarianRiskAgent",
        )
        score = data.get("skeptic_score")
        if not isinstance(score, int) or not (1 <= score <= 10):
            raise ValidateAgentError(
                "ContrarianRiskAgent: skeptic_score deve ser int em [1, 10]."
            )
        return data


class ExperimentDesignAgent:
    """
    Estágio 6/7 — Propõe 3 a 7 experimentos práticos (hipótese, método, métrica, go/no-go).

    Saída:
        {
          "experiments": [
            {
              "hypothesis": str,
              "method": str,
              "metric": str,
              "go_threshold": str,
              "estimated_cost_days": int
            },
            ...
          ]
        }
    """

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
        data = await self._client.complete_json(system_prompt=_SYSTEM, user_prompt=user)
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
    """
    Estágio 7/7 — Consolida o veredito final (INVESTIGATE/BUILD/PIVOT/DISCARD),
    confiança, rationale e condições.

    Saída:
        {
          "verdict": "INVESTIGATE" | "BUILD" | "PIVOT" | "DISCARD",
          "confidence": float,
          "rationale": str,
          "conditions": list[str],
          "final_report": str
        }
    """

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
            "confidence deve refletir o quanto as evidências suportam o veredito."
        )
        data = await self._client.complete_json(system_prompt=_SYSTEM, user_prompt=user)
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