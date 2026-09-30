"""
Módulo SELF-AUDIT (v4.6.0 — Auditoria Interna).

Executa um pack de missões canônicas nos modos BUILD/VALIDATE/VALIDATE_AND_BUILD,
aplica objective checks determinísticos e consolida um scorecard com veredito
HEALTHY/DEGRADED/CRITICAL, opcionalmente revisado por um auditor adversarial (LLM).
"""

from backend.self_audit.canonical_pack import (
    CanonicalMission,
    get_canonical_pack,
    select_missions,
)
from backend.self_audit.runner import AuditRunner
from backend.self_audit.schemas import (
    AdversarialReview,
    AuditMissionResult,
    SelfAuditRequest,
    SelfAuditScorecard,
)

__all__ = [
    "AdversarialReview",
    "AuditMissionResult",
    "AuditRunner",
    "CanonicalMission",
    "SelfAuditRequest",
    "SelfAuditScorecard",
    "get_canonical_pack",
    "select_missions",
]