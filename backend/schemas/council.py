"""
Schemas Pydantic v2 do Conselho Consultivo Artificial.
v3.0 / Módulo C1: Validação de consistência score↔verdict via model_validator.
v3.0 / Módulo C3: CouncilDecision com campo `reason` para observabilidade.
"""

from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, model_validator


class JurorVerdict(str, Enum):
    APPROVE = "APPROVE"
    VETO    = "VETO"


class JurorResponse(BaseModel):
    """
    Resposta individual de um jurado do Conselho.

    Regras de consistência (Módulo C1):
      - VETO   + score >= 7.0  → inválido (jurado contraditório)
      - APPROVE + score <  5.0  → inválido (aprovação sem convicção)
    """

    juror_name: str = Field(
        description="Nome/papel do jurado (ex: Architect, SecurityCoder, Generalist)"
    )
    score: float = Field(
        ge=1.0, le=10.0,
        description="Pontuação de 1.0 a 10.0 para a missão avaliada",
    )
    verdict: JurorVerdict = Field(
        description="Veredicto: APPROVE ou VETO"
    )
    reasoning: str = Field(
        max_length=500,
        description="Justificativa do veredicto em até 500 caracteres",
    )

    @model_validator(mode="after")
    def check_score_verdict_consistency(self) -> "JurorResponse":
        """
        Garante consistência entre score e verdict.
        Chamado automaticamente pelo Pydantic após a construção do modelo.
        """
        if self.verdict == JurorVerdict.VETO and self.score >= 7.0:
            raise ValueError(
                f"Inconsistent verdict: VETO is not allowed with score >= 7.0 "
                f"(received score={self.score})"
            )
        if self.verdict == JurorVerdict.APPROVE and self.score < 5.0:
            raise ValueError(
                f"Inconsistent verdict: APPROVE is not allowed with score < 5.0 "
                f"(received score={self.score})"
            )
        return self


class CouncilDecision(BaseModel):
    """
    Decisão consolidada do Conselho Consultivo.
    v3.0 / Módulo C3: campo `reason` para observabilidade da decisão.
    """

    mission: str = Field(description="Missão avaliada")
    final_verdict: str = Field(description="APPROVED ou REJECTED")
    average_score: float = Field(description="Média dos scores dos jurados")
    reason: str = Field(
        default="",
        description="Justificativa técnica resumida da decisão final",
    )
    juror_responses: List[JurorResponse] = Field(
        description="Respostas individuais de cada jurado"
    )