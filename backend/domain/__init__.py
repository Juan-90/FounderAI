"""
Domínio do FounderAI v4.2.0 (BUILD Mode Mínimo — Path A).

Enums de projeto/missão, modelos de domínio (Artifact, MissionState, Project)
e o ArtifactManager que persiste artefatos de missão no disco local.
"""

from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import (
    DeploymentStrategy,
    MissionStatus,
    ProjectMode,
    ProjectType,
)
from backend.domain.models import Artifact, MissionState, Project

__all__ = [
    "Artifact",
    "ArtifactManager",
    "DeploymentStrategy",
    "MissionState",
    "MissionStatus",
    "Project",
    "ProjectMode",
    "ProjectType",
]