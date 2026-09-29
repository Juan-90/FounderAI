"""
Schemas Pydantic V2 da Sandbox Isolada (v4.0 + v4.1 telemetry + v4.3 env).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SandboxInput(BaseModel):
    """Pedido de execução isolada."""

    files: Dict[str, str] = Field(
        ..., description="Dicionário com caminho_relativo -> conteudo"
    )
    command: List[str] = Field(
        ..., description="Comando como lista de strings. Ex: ['pytest', '-q']"
    )
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    max_output_bytes: int = Field(default=1_048_576, description="Teto de output (1MB)")
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Variáveis de ambiente injetadas no container (ex: SDL headless)",
    )


class SandboxOutput(BaseModel):
    """Resultado da execução isolada + telemetria de recursos."""

    exit_code: Optional[int] = Field(default=None)
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    duration_ms: int = Field(default=0)
    timed_out: bool = Field(default=False)
    stdout_truncated: bool = Field(default=False)
    stderr_truncated: bool = Field(default=False)
    error: Optional[str] = Field(default=None)

    ram_peak_mb: Optional[float] = Field(default=None)
    cpu_percent_avg: Optional[float] = Field(default=None)
    cpu_percent_max: Optional[float] = Field(default=None)
    container_id: Optional[str] = Field(default=None)