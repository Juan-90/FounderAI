"""
Schemas Pydantic V2 do Modo DISCOVER (v4.7.0).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class DiscoverRequest(BaseModel):
    """Entrada do Modo DISCOVER."""

    theme: str = Field(..., description="Tema/área a explorar")
    audience: Optional[str] = Field(default=None)
    geography: Optional[str] = Field(default="Brasil")
    constraints: list[str] = Field(default_factory=list)
    seeds: list[str] = Field(default_factory=list, description="Ideias-semente opcionais")
    max_opportunities: int = Field(default=8, ge=1)
    include_contrarian: bool = Field(default=True)
    handoff_to_validate: bool = Field(default=False)
    selected_opportunity_id: Optional[str] = Field(default=None)


class OpportunityProfile(BaseModel):
    """Perfil estruturado de uma oportunidade."""

    id: str
    title: str
    one_liner: str
    problem: str
    audience: str
    why_now: str
    solution_sketch: str
    business_model_hint: Optional[str] = None
    score: float = Field(ge=0.0, le=1.0)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    evidence_level: Literal["low", "medium", "high"] = "low"
    tags: list[str] = Field(default_factory=list)


class DiscoverResult(BaseModel):
    """Resultado consolidado do DISCOVER."""

    opportunities: list[OpportunityProfile] = Field(default_factory=list)
    rejected: list[dict] = Field(default_factory=list)
    ranking_method: str
    summary: str
    recommended_next: list[str] = Field(default_factory=list)