"""
Schemas Pydantic V2 do Loop TDD (v4.0 Fase B + v4.1.0 observabilidade estática).
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.sandbox.models import SandboxOutput


class TDDRequest(BaseModel):
    """Pedido de execução do loop TDD."""

    source_files: Dict[str, str] = Field(
        ..., description="Arquivo(s) de código-fonte {caminho: conteudo}"
    )
    test_files: Dict[str, str] = Field(
        default_factory=dict, description="Testes iniciais (opcional)"
    )
    entry_command: List[str] = Field(
        default_factory=lambda: ["pytest", "-q"],
        description="Comando seguro na Sandbox",
    )
    max_retries: int = Field(
        default=3, ge=1, le=5, description="Limite máximo de retries"
    )
    goal: Optional[str] = Field(
        default=None, description="Descrição opcional da intenção do código"
    )
    mission_id: str = Field(
        default="", description="ID da missão (usado em escalação/webhook)"
    )


class TDDAttempt(BaseModel):
    """Registro imutável de uma tentativa do loop."""

    attempt_number: int = Field(
        ..., description="0 para baseline inicial, 1..N para retries"
    )
    source_code: Dict[str, str]
    tests_code: Dict[str, str]
    sandbox_result: SandboxOutput
    analysis: str = Field(
        default="", description="Diagnóstico da falha produzido pelo QA Agent"
    )
    patch_summary: Optional[str] = Field(
        default=None, description="Resumo da alteração aplicada nesta tentativa"
    )


class TDDResult(BaseModel):
    """Resultado consolidado do loop TDD."""

    success: bool
    final_source_code: Dict[str, str]
    final_tests_code: Dict[str, str]
    attempts: List[TDDAttempt]
    final_sandbox_result: Optional[SandboxOutput] = None
    escalated: bool = Field(
        default=False,
        description="True se atingiu o limite de retries sem sucesso",
    )
    summary: str
    # ── v4.1.0 observabilidade do gate estático ──
    static_gate_passed: Optional[bool] = Field(
        default=None,
        description="None=gate não executado; True/False=resultado do gate",
    )
    failure_stage: Optional[Literal["static_gate", "sandbox"]] = Field(
        default=None,
        description="Estágio onde o loop falhou, se houver",
    )