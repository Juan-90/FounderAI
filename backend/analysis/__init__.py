"""
Pre-Sandbox Guardrail — FounderAI v4.1.0 (Módulo A).

Análise estática (ruff + mypy) executada ANTES de submeter código à sandbox,
reduzindo ciclos de auto-correção ao rejeitar código com erros óbvios.
"""

from backend.analysis.models import StaticAnalysisResult, StaticIssue
from backend.analysis.static_gate import StaticAnalysisGate

__all__ = ["StaticAnalysisGate", "StaticAnalysisResult", "StaticIssue"]