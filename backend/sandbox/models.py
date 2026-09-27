"""
Schemas Pydantic V2 da Sandbox Isolada (v4.0 Fase A).

Contrato de entrada/saída do runner: arquivos + comando tipados,
limites de tempo e de output configuráveis por chamada.
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
    """Resultado da execução isolada."""

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
    