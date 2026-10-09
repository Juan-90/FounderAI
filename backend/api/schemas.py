"""
Modelo unificado de interação da API (v5.1.0).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SourceLiteral = Literal["cli", "web", "mobile", "voice"]
TargetModeLiteral = Literal[
    "discover", "validate", "build", "validate_and_build", "self_audit", "golden", "improve"
]
ResponseStatusLiteral = Literal["pending", "running", "completed", "failed"]
HealthStatusLiteral = Literal["healthy", "degraded"]


class InteractionRequest(BaseModel):
    """Pedido unificado de interação, independente da origem."""

    source: SourceLiteral = Field(default="cli", description="Origem da requisição")
    target_mode: TargetModeLiteral = Field(..., description="Modo do pipeline a executar")
    prompt: str = Field(..., description="Intent/tema/missão em texto livre")
    options: Optional[dict[str, Any]] = Field(
        default=None, description="Opções específicas do modo (ex: project_type, max)"
    )
    project_id: Optional[str] = Field(
        default=None, description="ID do projeto para vincular a missão à memória"
    )
    project_name: Optional[str] = Field(
        default=None, description="Nome do projeto (cria/carrega por nome)"
    )


class InteractionResponse(BaseModel):
    """Resposta unificada de uma interação."""

    mission_id: str
    status: ResponseStatusLiteral
    mode: str
    summary: str
    artifacts_path: str
    created_at: datetime


class HealthResponse(BaseModel):
    """Health check da plataforma."""

    status: HealthStatusLiteral
    version: str = "5.1.0"
    environment: str
    active_providers: list[str] = Field(default_factory=list)