"""
Schemas Pydantic V2 do Escalation Webhook Engine (v4.1.0 Módulo C).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WebhookProvider(str, Enum):
    """Provedores suportados para notificação de escalação."""
    GENERIC  = "GENERIC"
    DISCORD  = "DISCORD"
    SLACK    = "SLACK"
    TELEGRAM = "TELEGRAM"


class EscalationPayload(BaseModel):
    """Payload estruturado de uma escalação do TDDLoop."""

    event: str = Field(description="Identificador do evento (ex: 'tdd_loop.escalated')")
    project_name: str = Field(description="Nome do projeto FounderAI")
    mission_id: str = Field(description="ID da missão que escalou")
    goal: Optional[str] = Field(default=None, description="Objetivo declarado")
    attempts: int = Field(description="Número de tentativas executadas")
    max_retries: int = Field(description="Limite configurado de retries")
    final_summary: str = Field(description="Resumo final do TDDResult")
    last_error: Optional[str] = Field(default=None, description="Último erro capturado")
    stdout_tail: str = Field(default="", description="Últimos N bytes do stdout")
    stderr_tail: str = Field(default="", description="Últimos N bytes do stderr")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=None),
        description="Timestamp da escalação",
    )


class NotificationResult(BaseModel):
    """Resultado de uma tentativa de notificação (never-throw)."""

    sent: bool = Field(description="True se o webhook foi entregue com sucesso")
    provider: WebhookProvider
    status_code: Optional[int] = Field(
        default=None, description="HTTP status code (None em erro de rede)"
    )
    error: Optional[str] = Field(
        default=None, description="Descrição do erro (None em sucesso)"
    )