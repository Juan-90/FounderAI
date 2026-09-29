"""
Schemas Pydantic V2 do Modo VALIDATE_AND_BUILD (v4.5.0).

Contratos:
  • ValidateAndBuildRequest: entrada combinada (validação + build).
  • BuildGateDecision:       resultado puro do DecisionGate.
  • BuildSeed:               contexto pré-validado injetado no BUILD.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.domain.enums import DeploymentStrategy, ProjectType

ValidationVerdictLiteral = Literal["INVESTIGATE", "BUILD", "PIVOT", "DISCARD"]


class ValidateAndBuildRequest(BaseModel):
    """Entrada do Modo VALIDATE_AND_BUILD."""

    idea_text: str = Field(..., description="Texto livre da ideia/projeto")
    name: Optional[str] = Field(default=None)
    target_audience: Optional[str] = Field(default=None)
    problem: Optional[str] = Field(default=None)
    solution: Optional[str] = Field(default=None)
    business_model: Optional[str] = Field(default=None)
    constraints: Optional[str] = Field(default=None)
    context_files: list[str] = Field(default_factory=list)
    project_type: Optional[ProjectType] = Field(default=None)
    deployment_strategy: DeploymentStrategy = Field(default=DeploymentStrategy.PRIVATE)

    auto_build: bool = Field(
        default=True, description="Permitir prosseguir para o BUILD se o gate autorizar"
    )
    require_human_confirmation: bool = Field(
        default=True, description="Exigir confirmação humana antes do BUILD"
    )
    min_confidence_to_autobuild: float = Field(
        default=0.75, ge=0.0, le=1.0,
        description="Confiança mínima para auto-build sem confirmação",
    )


class BuildGateDecision(BaseModel):
    """Resultado puro do DecisionGate (sem LLM)."""

    should_build: bool = Field(description="Se o gate autoriza prosseguir para o BUILD")
    needs_human_confirmation: bool = Field(
        description="Se exige confirmação humana antes de construir"
    )
    reason: str = Field(description="Justificativa da decisão")
    source_verdict: ValidationVerdictLiteral = Field(
        description="Veredito de origem vindo do ValidationSynthesizer"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confiança do veredito")
    conditions: list[str] = Field(default_factory=list)


class BuildSeed(BaseModel):
    """Contexto pré-validado injetado no RequirementsAgent do BUILD."""

    idea_profile: dict = Field(default_factory=dict)
    recommended_mvp_scope: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risks_to_mitigate: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    suggested_project_type: Optional[ProjectType] = Field(default=None)