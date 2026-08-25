"""
Schemas Pydantic v2 do Conselho Consultivo Artificial.
Define os contratos de dados entre jurados e orquestrador.
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class JurorVerdict(str, Enum):
    APPROVE = "APPROVE"
    VETO = "VETO"


class JurorResponse(BaseModel):
    """Resposta individual de um jurado do Conselho."""

    juror_name: str = Field(
        description="Nome/papel do jurado (ex: Architect, SecurityCoder, Generalist)"
    )
    score: float = Field(
        ge=1.0,
        le=10.0,
        description="Pontuação de 1.0 a 10.0 para a missão avaliada",
    )
    verdict: JurorVerdict = Field(
        description="Veredicto: APPROVE ou VETO"
    )
    reasoning: str = Field(
        max_length=500,
        description="Justificativa do veredicto em até 500 caracteres",
    )


class CouncilDecision(BaseModel):
    """Decisão consolidada do Conselho Consultivo."""

    mission: str = Field(description="Missão avaliada")
    final_verdict: str = Field(description="APPROVED ou REJECTED")
    average_score: float = Field(description="Média dos scores dos jurados")
    juror_responses: List[JurorResponse] = Field(
        description="Respostas individuais de cada jurado"
    )