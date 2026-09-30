"""
Schemas Pydantic V2 do Modo SELF-AUDIT (v4.6 + failure_class v5.0).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.domain.enums import ProjectMode


class SelfAuditRequest(BaseModel):
    include_build: bool = Field(default=True)
    include_validate: bool = Field(default=True)
    include_validate_and_build: bool = Field(default=True)
    max_missions_per_mode: int = Field(default=3, ge=1)
    adversarial_enabled: bool = Field(default=True)
    fail_fast: bool = Field(default=False)


class AuditMissionResult(BaseModel):
    mission_name: str
    mode: ProjectMode
    success: bool
    duration_ms: int
    error: Optional[str] = None
    failure_class: Optional[Literal["infra", "logic"]] = Field(
        default=None,
        description="infra=provedor/modelo; logic=ecossistema (checks/contratos)",
    )
    objective_checks: dict[str, bool] = Field(default_factory=dict)
    artifacts_path: Optional[str] = None
    notes: Optional[str] = None


class AdversarialReview(BaseModel):
    findings: list[str] = Field(default_factory=list)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    overclaim_detected: bool = Field(default=False)
    consistency_score: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: str = ""
    adversarial_degraded: bool = Field(default=False)


class SelfAuditScorecard(BaseModel):
    total_missions: int
    success_rate: float
    build_success_rate: Optional[float] = None
    validate_success_rate: Optional[float] = None
    vab_success_rate: Optional[float] = None
    objective_checks_passed: int
    objective_checks_total: int
    infra_failures: int = Field(default=0)
    adversarial_findings: list[str] = Field(default_factory=list)
    critical_findings: list[str] = Field(default_factory=list)
    overall_verdict: Literal["HEALTHY", "DEGRADED", "CRITICAL"]
    confidence: float
    summary: str