"""
Modelos de domínio do FounderAI (v5.3.0 — inclui memória de projeto).
"""

from backend.domain.artifacts import Artifact, ArtifactManager
from backend.domain.evidence import (
    Claim,
    EvidenceGraph,
    EvidenceItem,
    EvidenceOrigin,
    Source,
)
from backend.domain.evidence_store import load_evidence_graph, save_evidence_graph
from backend.domain.enums import (
    DeploymentStrategy,
    MissionStatus,
    ProjectMode,
    ProjectType,
)
from backend.domain.memory import (
    ArtifactKind,
    ArtifactVersion,
    MemoryDecision,
    MemoryEvent,
    MemoryEventType,
    MemoryLearning,
    ProjectMemory,
)
from backend.domain.memory_store import DiskProjectMemoryStore, ProjectMemoryStore
from backend.domain.models import MissionState

__all__ = [
    "Artifact",
    "ArtifactKind",
    "ArtifactManager",
    "ArtifactVersion",
    "Claim",
    "DeploymentStrategy",
    "DiskProjectMemoryStore",
    "EvidenceGraph",
    "EvidenceItem",
    "EvidenceOrigin",
    "MemoryDecision",
    "MemoryEvent",
    "MemoryEventType",
    "MemoryLearning",
    "MissionState",
    "MissionStatus",
    "ProjectMemory",
    "ProjectMemoryStore",
    "ProjectMode",
    "ProjectType",
    "Source",
    "load_evidence_graph",
    "save_evidence_graph",
]