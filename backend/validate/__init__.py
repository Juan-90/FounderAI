"""
Módulo VALIDATE (v4.4.0 — Path C / EcoTrack-IA).

Pipeline de validação de ideia em 7 estágios analíticos, do intake à
síntese de veredito (INVESTIGATE/BUILD/PIVOT/DISCARD) com confiança,
condições e evidências lacunas.
"""

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

__all__ = [
    "CompetitorAgent",
    "ContrarianRiskAgent",
    "ExperimentDesignAgent",
    "IdeaIntakeAgent",
    "ProblemMarketAgent",
    "TechnicalFeasibilityAgent",
    "ValidateAgentError",
    "ValidatePayload",
    "ValidateRequest",
    "ValidationSynthesizer",
    "ValidationVerdict",
]