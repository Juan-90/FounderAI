"""
ImprovePlanner — diagnóstico → plano de melhoria (v5.4.0).

Determinístico (sem LLM): mapeia categorias do ImproveDiagnosis em itens de
ação objetivos (bugs, testes, alinhamento de requisitos). Gera de 1 a 7 itens.
Confirmação humana obrigatória se risco global medium/high OU se o pedido
exigir (require_human_confirmation).
"""

from __future__ import annotations

from backend.domain.improve import (
    ImproveDiagnosis,
    ImprovePlan,
    ImprovePlanItem,
    ImproveRequest,
    RiskLevel,
)

_MAX_ITEMS = 7
_ORDER = {"low": 0, "medium": 1, "high": 2}


class ImprovePlanner:
    def plan(self, diagnosis: ImproveDiagnosis, request: ImproveRequest) -> ImprovePlan:
        items: list[ImprovePlanItem] = []

        for issue in diagnosis.top_issues:
            if issue.startswith("QA:"):
                items.append(ImprovePlanItem(
                    title=f"Corrigir falha de QA: {issue[3:].strip()[:60]}",
                    rationale="Learning de QA da memória indica defeito recorrente.",
                    expected_impact="Testes voltam a passar; regressão eliminada.",
                    risk_level="medium",
                ))
            elif issue.startswith("Falha recorrente") or issue.startswith("Falha registrada"):
                items.append(ImprovePlanItem(
                    title=f"Corrigir bug: {issue.split(':', 1)[-1].strip()[:60]}",
                    rationale="Evento de falha registrado na memória do projeto.",
                    expected_impact="Build volta a completar sem falhas.",
                    risk_level="medium",
                ))
            elif issue.startswith("Risco:"):
                items.append(ImprovePlanItem(
                    title=f"Mitigar risco: {issue[6:].strip()[:60]}",
                    rationale="Risco de validação registrado na memória.",
                    expected_impact="Risco crítico mitigado antes de escalar.",
                    risk_level="medium",
                ))
            elif issue.startswith("Gap de goal"):
                items.append(ImprovePlanItem(
                    title="Realinhar requisitos ao novo goal",
                    rationale=issue,
                    expected_impact="Requisitos e arquitetura coerentes com o goal atual.",
                    risk_level="low",
                ))

        if not items:
            items.append(ImprovePlanItem(
                title="Revisão de regressão e hardening",
                rationale="Diagnóstico sem issues críticas; manutenção preventiva.",
                expected_impact="Base estabilizada para próximas melhorias.",
                risk_level="low",
            ))

        items = items[:_MAX_ITEMS]

        overall: RiskLevel = diagnosis.risk_level
        for _item in items:
            if _ORDER[_item.risk_level] > _ORDER[overall]:
                overall = _item.risk_level
        requires = bool(request.require_human_confirmation) or overall in ("medium", "high")

        return ImprovePlan(items=items, overall_risk=overall, requires_confirmation=requires)