"""
Módulo VALIDATE_AND_BUILD (v4.5.0 — Ponte Direta).

Encadeia o pipeline VALIDATE ao BUILD mediante um DecisionGate puro:
somente prossegue para a construção quando o veredito/confiança/condições
autorizam (com confirmação humana quando exigido).
"""

from backend.validate_and_build.gate import DecisionGate
from backend.validate_and_build.schemas import (
    BuildGateDecision,
    BuildSeed,
    ValidateAndBuildRequest,
)

__all__ = [
    "BuildGateDecision",
    "BuildSeed",
    "DecisionGate",
    "ValidateAndBuildRequest",
]