"""
Módulo SELF-AUDIT (v4.6.0 — Auditoria Interna).
"""

from backend.self_audit.adversarial import AdversarialAuditor
from backend.self_audit.canonical_pack import (
    CanonicalMission,
    get_canonical_pack,
    select_missions,
)
from backend.self_audit.pipeline import SelfAuditPipeline
from backend.self_audit.runner import AuditRunner
from backend.self_audit.scorecard import ScorecardSynthesizer
from backend.self_audit.schemas import (
    AdversarialReview,
    AuditMissionResult,
    SelfAuditRequest,
    SelfAuditScorecard,
)

__all__ = [
    "AdversarialAuditor",
    "AdversarialReview",
    "AuditMissionResult",
    "AuditRunner",
    "CanonicalMission",
    "ScorecardSynthesizer",
    "SelfAuditPipeline",
    "SelfAuditRequest",
    "SelfAuditScorecard",
    "get_canonical_pack",
    "select_missions",
]   