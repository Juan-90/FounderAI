"""
Schemas Pydantic V2 do Loop TDD (v4.0 + v4.3 env headless).
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.sandbox.models import SandboxOutput


class TDDRequest(BaseModel):
    """Pedido de execução do loop TDD."""

    source_files: Dict[str, str] = Field(...)
    test_files: Dict[str, str] = Field(default_factory=dict)
    entry_command: List[str] = Field(default_factory=lambda: ["pytest", "-q"])
    max_retries: int = Field(default=3, ge=1, le=5)
    goal: Optional[str] = Field(default=None)
    mission_id: str = Field(default="")
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Env repassado à sandbox (ex: SDL headless para GAME)",
    )


class TDDAttempt(BaseModel):
    attempt_number: int = Field(...)
    source_code: Dict[str, str]
    tests_code: Dict[str, str]
    sandbox_result: SandboxOutput
    analysis: str = Field(default="")
    patch_summary: Optional[str] = Field(default=None)


class TDDResult(BaseModel):
    success: bool
    final_source_code: Dict[str, str]
    final_tests_code: Dict[str, str]
    attempts: List[TDDAttempt]
    final_sandbox_result: Optional[SandboxOutput] = None
    escalated: bool = Field(default=False)
    summary: str
    static_gate_passed: Optional[bool] = Field(default=None)
    failure_stage: Optional[Literal["static_gate", "sandbox"]] = Field(default=None)