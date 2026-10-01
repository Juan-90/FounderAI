"""
Modelos de domínio do FounderAI (v5.2.0 — inclui evidências).
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
from backend.domain.models import MissionState

__all__ = [
    "Artifact",
    "ArtifactManager",
    "Claim",
    "DeploymentStrategy",
    "EvidenceGraph",
    "EvidenceItem",
    "EvidenceOrigin",
    "MissionState",
    "MissionStatus",
    "ProjectMode",
    "ProjectType",
    "Source",
    "load_evidence_graph",
    "save_evidence_graph",
]