"""
Schemas Pydantic V2 do Modo VALIDATE (v4.4.0).

Contratos:
  • ValidateRequest:    entrada bruta da missão VALIDATE.
  • ValidationVerdict:  enum de veredito final (INVESTIGATE/BUILD/PIVOT/DISCARD).
  • ValidatePayload:    helper que monta o dict a ser persistido no
                        MissionState.mode_payload sob project_mode=VALIDATE.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.domain.enums import ProjectType


class ValidationVerdict(str, Enum):
    """Veredito consolidado pelo ValidationSynthesizer."""

    INVESTIGATE = "INVESTIGATE"  # hipótese promissora mas incerta; exige experimentos
    BUILD       = "BUILD"        # validado o suficiente para iniciar o BUILD Mode
    PIVOT       = "PIVOT"        # problema real mas solução/segmento errado
    DISCARD     = "DISCARD"      # premissas fracas demais; abandone a ideia


class ValidateRequest(BaseModel):
    """Entrada bruta do Modo VALIDATE."""

    idea_text: str = Field(..., description="Texto livre da ideia/projeto")
    name: Optional[str] = Field(
        default=None, description="Nome opcional da ideia/projeto"
    )
    target_audience: Optional[str] = Field(
        default=None, description="Público-alvo declarado"
    )
    problem: Optional[str] = Field(
        default=None, description="Problema a ser resolvido"
    )
    solution: Optional[str] = Field(
        default=None, description="Solução proposta"
    )
    business_model: Optional[str] = Field(
        default=None, description="Modelo de monetização"
    )
    constraints: Optional[str] = Field(
        default=None, description="Restrições conhecidas (tempo, equipe, capital)"
    )
    context_files: list[str] = Field(
        default_factory=list,
        description="Arquivos anexados como contexto (processados pelo orquestrador)",
    )
    project_type: Optional[ProjectType] = Field(
        default=None, description="Tipo de produto alvo (WEB_APP/GAME/etc.)"
    )


class ValidatePayload:
    """
    Estrutura esperada do mode_payload de um MissionState.VALIDATE.

    Não é um BaseModel (mode_payload é dict[str, Any]), mas documenta a
    topologia e oferece um helper .build() para montar dict consistente.
    """

    @staticmethod
    def build(
        *,
        idea_profile: dict[str, Any] | None = None,
        problem_market: dict[str, Any] | None = None,
        competitors: dict[str, Any] | None = None,
        technical_feasibility: dict[str, Any] | None = None,
        risks_contrarian: dict[str, Any] | None = None,
        hypotheses: list[dict[str, Any]] | None = None,
        experiments: list[dict[str, Any]] | None = None,
        recommendation: dict[str, Any] | None = None,
        evidence_gaps: list[str] | None = None,
        final_report: str | None = None,
    ) -> dict[str, Any]:
        return {
            "idea_profile": idea_profile or {},
            "problem_market": problem_market or {},
            "competitors": competitors or {},
            "technical_feasibility": technical_feasibility or {},
            "risks_contrarian": risks_contrarian or {},
            "hypotheses": hypotheses or [],
            "experiments": experiments or [],
            "recommendation": recommendation or {},
            "evidence_gaps": evidence_gaps or [],
            "final_report": final_report or "",
        }