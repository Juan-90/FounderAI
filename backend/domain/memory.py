"""
Modelos de domínio da Memória de Projeto (v5.3.0).

ProjectMemory é o agregado raiz que concentra eventos, decisões, versões
de artefatos e aprendizados de um projeto ao longo de múltiplas missões.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from backend.domain.enums import DeploymentStrategy, ProjectType


class MemoryEventType(str, Enum):
    """Tipo de evento registrado na memória do projeto."""

    PROJECT_CREATED = "project_created"
    VALIDATED = "validated"
    BUILD_STARTED = "build_started"
    BUILD_SUCCEEDED = "build_succeeded"
    BUILD_FAILED = "build_failed"
    ESCALATED = "escalated"
    DECISION_RECORDED = "decision_recorded"
    ARTIFACT_VERSIONED = "artifact_versioned"
    LEARNING_ADDED = "learning_added"
    IMPROVED = "improved"


class ArtifactKind(str, Enum):
    """Tipo de artefato versionado."""

    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    CODE_BUNDLE = "code_bundle"
    TEST_REPORT = "test_report"
    VALIDATION_REPORT = "validation_report"
    DISCOVER_REPORT = "discover_report"
    COMPOSITE_REPORT = "composite_report"
    EVIDENCE_GRAPH = "evidence_graph"
    OTHER = "other"


class ArtifactVersion(BaseModel):
    """Uma versão de artefato associada ao projeto."""

    version_id: str
    kind: ArtifactKind
    path: str
    checksum: Optional[str] = None
    mission_id: Optional[str] = None
    created_at: datetime
    summary: Optional[str] = None


class MemoryDecision(BaseModel):
    """Decisão arquitetural ou de produto registrada."""

    decision_id: str
    title: str
    rationale: str
    status: Literal["accepted", "rejected", "superseded"] = "accepted"
    mission_id: Optional[str] = None
    created_at: datetime


class MemoryLearning(BaseModel):
    """Aprendizado capturado de falhas, riscos ou feedback."""

    learning_id: str
    text: str
    source: Literal[
        "qa_failure", "validation_risk", "human_feedback", "self_audit", "other"
    ]
    mission_id: Optional[str] = None
    created_at: datetime


class MemoryEvent(BaseModel):
    """Evento registrado na linha do tempo do projeto."""

    event_id: str
    type: MemoryEventType
    mission_id: Optional[str] = None
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ProjectMemory(BaseModel):
    """Agregado raiz: memória completa de um projeto."""

    project_id: str
    name: str
    project_type: Optional[ProjectType] = None
    deployment_strategy: Optional[DeploymentStrategy] = None
    current_goal: Optional[str] = None
    status: Literal["active", "archived"] = "active"
    events: list[MemoryEvent] = Field(default_factory=list)
    decisions: list[MemoryDecision] = Field(default_factory=list)
    artifact_versions: list[ArtifactVersion] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    learnings: list[MemoryLearning] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime