"""
Modelos de domínio Pydantic V2 do FounderAI v4.2.0 (BUILD Mode).

Defaults operacionais (id/timestamps/coleções) via default_factory para
facilitar construção no ArtifactManager e nos testes, sem remover nenhum
campo exigido pela especificação.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.domain.enums import (
    DeploymentStrategy,
    MissionStatus,
    ProjectMode,
    ProjectType,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Artifact(BaseModel):
    """Arquivo produzido/persistido por uma missão."""

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Identificador único do artefato",
    )
    name: str = Field(description="Nome do arquivo (ex: index.html)")
    type: str = Field(description="Tipo/extensão inferida (ex: html, py, text)")
    path: str = Field(description="Caminho relativo à raiz de artefatos")
    content: str = Field(description="Conteúdo textual do artefato")
    created_at: datetime = Field(
        default_factory=_utcnow, description="Timestamp de criação (UTC)"
    )


class MissionState(BaseModel):
    """Estado de execução de uma missão BUILD Mode."""

    mission_id: str = Field(description="ID único da missão")
    project_id: str = Field(description="ID do projeto pai")
    mode: ProjectMode = Field(description="Modo de operação")
    status: MissionStatus = Field(description="Status atual do ciclo de vida")
    current_stage: str = Field(description="Estágio atual do pipeline")
    mode_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Payload específico do modo (ex: specs do BUILD)",
    )
    artifacts: list[Artifact] = Field(
        default_factory=list, description="Artefatos produzidos pela missão"
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Project(BaseModel):
    """Projeto de produto gerenciado pelo FounderAI."""

    id: str = Field(
        default_factory=lambda: uuid4().hex, description="ID único do projeto"
    )
    name: str = Field(description="Nome legível do projeto")
    intent: str = Field(description="Intenção/missão declarada pelo fundador")
    type: ProjectType = Field(default=ProjectType.WEB_APP)
    mode: ProjectMode = Field(default=ProjectMode.BUILD)
    deployment: DeploymentStrategy = Field(default=DeploymentStrategy.PRIVATE)
    created_at: datetime = Field(default_factory=_utcnow)