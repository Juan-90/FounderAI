"""
ScorecardSynthesizer — calcula a saúde do sistema (v4.6.0).

  • HEALTHY:  success_rate >= 0.85 e zero achados críticos (e sem moderados).
  • DEGRADED: 0.60 <= success_rate < 0.85 ou achados moderados.
  • CRITICAL: success_rate < 0.60 ou achados críticos de integridade.
"""

from __future__ import annotations

from typing import Optional

from backend.domain.enums import ProjectMode
from backend.self_audit.schemas import (
    AdversarialReview,
    AuditMissionResult,
    SelfAuditScorecard,
)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


class ScorecardSynthesizer:
    def synthesize(
        self,
        results: list[AuditMissionResult],
        review: AdversarialReview,
    ) -> SelfAuditScorecard:
        total = len(results)
        succ = sum(1 for r in results if r.success)
        rate = (succ / total) if total else 0.0

        def mrate(mode: ProjectMode) -> Optional[float]:
            subset = [r for r in results if r.mode == mode]
            if not subset:
                return None
            return sum(1 for r in subset if r.success) / len(subset)

        checks_passed = int(sum(sum(r.objective_checks.values()) for r in results))
        checks_total = int(sum(len(r.objective_checks) for r in results))

        critical_count = review.severity_counts.get("critical", 0)
        critical_findings = review.findings[:critical_count] if critical_count else []
        moderate = review.severity_counts.get("major", 0) > 0

        if total == 0 or rate < 0.60 or critical_findings:
            verdict = "CRITICAL"
        elif rate >= 0.85 and not critical_findings and not moderate:
            verdict = "HEALTHY"
        else:
            verdict = "DEGRADED"

        confidence = round(_clamp(rate * review.consistency_score), 3)
        summary = (
            f"{succ}/{total} missões OK (taxa {rate:.0%}); veredito {verdict}; "
            f"{len(review.findings)} achado(s) adversarial(is)"
            + (" [auditor degradado]" if review.adversarial_degraded else "")
            + "."
        )
        return SelfAuditScorecard(
            total_missions=total, success_rate=round(rate, 3),
            build_success_rate=mrate(ProjectMode.BUILD),
            validate_success_rate=mrate(ProjectMode.VALIDATE),
            vab_success_rate=mrate(ProjectMode.VALIDATE_AND_BUILD),
            objective_checks_passed=checks_passed, objective_checks_total=checks_total,
            adversarial_findings=list(review.findings), critical_findings=critical_findings,
            overall_verdict=verdict, confidence=confidence, summary=summary,
        )