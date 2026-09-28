"""
Schemas Pydantic V2 da Sandbox Isolada (v4.0 Fase A + v4.1.0 Telemetry).
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
    max_output_bytes: int = Field(
        default=1_048_576, description="Teto de output (1MB)"
    )


class SandboxOutput(BaseModel):
    """Resultado da execução isolada + telemetria de recursos (v4.1.0)."""

    exit_code: Optional[int] = Field(
        default=None,
        description="None para timeout ou erro de infraestrutura",
    )
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    duration_ms: int = Field(default=0)
    timed_out: bool = Field(default=False)
    stdout_truncated: bool = Field(default=False)
    stderr_truncated: bool = Field(default=False)
    error: Optional[str] = Field(
        default=None, description="Erros do Docker/infraestrutura"
    )

    # ── v4.1.0 Telemetry (opcionais, coleta best-effort) ──
    ram_peak_mb: Optional[float] = Field(
        default=None, description="Pico de RAM em MB (via docker stats)"
    )
    cpu_percent_avg: Optional[float] = Field(
        default=None, description="Média de uso de CPU (%)"
    )
    cpu_percent_max: Optional[float] = Field(
        default=None, description="Pico de uso de CPU (%)"
    )
    container_id: Optional[str] = Field(
        default=None, description="ID do container que executou o comando"
    )