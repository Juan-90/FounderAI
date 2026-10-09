"""
Modelos de domínio do Modo IMPROVE (v5.4.0).

IMPROVE fecha o loop de versionamento: diagnostica o projeto a partir da
memória acumulada, planeja melhorias e as aplica com confirmação humana.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high"]


class ImproveRequest(BaseModel):
    """Pedido de melhoria sobre um projeto existente."""

    project_id: str
    goal: Optional[str] = None
    focus: list[str] = Field(default_factory=list)
    max_files_touched: int = 8
    require_human_confirmation: bool = True
    auto_apply: bool = False


class ImproveDiagnosis(BaseModel):
    """Diagnóstico estruturado com citação explícita do que foi reutilizado."""

    summary: str
    top_issues: list[str] = Field(default_factory=list)
    leveraged_learnings: list[str] = Field(default_factory=list)
    leveraged_artifacts: list[str] = Field(default_factory=list)
    risk_level: RiskLevel


class ImprovePlanItem(BaseModel):
    """Um item acionável do plano de melhoria."""

    title: str
    rationale: str
    target_files: list[str] = Field(default_factory=list)
    expected_impact: str
    risk_level: RiskLevel = "low"


class ImprovePlan(BaseModel):
    """Plano consolidado de melhoria."""

    items: list[ImprovePlanItem] = Field(default_factory=list)
    overall_risk: RiskLevel
    requires_confirmation: bool


class ImproveResult(BaseModel):
    """Resultado completo de uma execução IMPROVE."""

    success: bool
    diagnosis: ImproveDiagnosis
    plan: ImprovePlan
    changed_files: list[str] = Field(default_factory=list)
    tdd_result: Optional[dict] = None
    report_path: Optional[str] = None
    escalated: bool = False
    waiting_human: bool = False
    summary: str
