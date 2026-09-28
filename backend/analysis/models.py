"""
Schemas Pydantic V2 do Pre-Sandbox Guardrail (v4.1.0 Módulo A).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StaticIssue(BaseModel):
    """Issue individual reportada por ruff ou mypy."""

    tool: Literal["ruff", "mypy"] = Field(description="Ferramenta que detectou a issue")
    code: str | None = Field(
        default=None, description="Código da regra (ex: E501, unused-import)"
    )
    message: str = Field(description="Mensagem descritiva da issue")
    file: str | None = Field(default=None, description="Arquivo afetado (relativo)")
    line: int | None = Field(default=None, description="Linha do problema")
    severity: Literal["error", "warning"] = Field(
        default="error", description="Severidade da issue"
    )


class StaticAnalysisResult(BaseModel):
    """Resultado consolidado da análise estática."""

    passed: bool = Field(
        description="True apenas se não houver issues de severidade 'error'"
    )
    issues: list[StaticIssue] = Field(default_factory=list)
    ruff_passed: bool = Field(default=True, description="Status isolado do ruff")
    mypy_passed: bool = Field(default=True, description="Status isolado do mypy")
    summary: str = Field(default="", description="Resumo legível do resultado")
    duration_ms: int = Field(default=0, description="Tempo total de execução em ms")