"""
SelfAuditPipeline — consolida Runner → Adversarial Auditor → Scorecard →
Persistência em artifacts/self_audit/<audit_id>/ (v4.6.0).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from backend.core.config import Settings, settings
from backend.self_audit.adversarial import AdversarialAuditor
from backend.self_audit.runner import AuditRunner, BuildFactory
from backend.self_audit.scorecard import ScorecardSynthesizer
from backend.self_audit.schemas import SelfAuditRequest, SelfAuditScorecard


class SelfAuditPipeline:
    def __init__(
        self,
        config: Settings | None = None,
        root_base: Path | None = None,
        build_factory: Optional[BuildFactory] = None,
        validate_pipeline: Any | None = None,
        vab_pipeline: Any | None = None,
        auditor: AdversarialAuditor | None = None,
    ) -> None:
        self._config = config if config is not None else settings
        self._base = root_base if root_base is not None else Path(
            self._config.SELF_AUDIT_ARTIFACTS_DIR
        )
        self._build_factory = build_factory
        self._validate = validate_pipeline
        self._vab = vab_pipeline
        self._auditor = auditor or AdversarialAuditor(self._config)
        self.last_audit_dir: Path | None = None

    async def run(self, request: SelfAuditRequest | None = None) -> SelfAuditScorecard:
        req = request or SelfAuditRequest(
            max_missions_per_mode=self._config.SELF_AUDIT_MAX_MISSIONS_PER_MODE,
            adversarial_enabled=self._config.SELF_AUDIT_ADVERSARIAL_ENABLED,
        )
        audit_id = uuid.uuid4().hex
        audit_dir = self._base / audit_id
        self.last_audit_dir = audit_dir

        runner = AuditRunner(
            config=self._config, root=audit_dir,
            build_factory=self._build_factory,
            validate_pipeline=self._validate, vab_pipeline=self._vab,
        )
        results = await runner.run_missions(req)
        review = await self._auditor.audit(results, audit_dir)
        scorecard = ScorecardSynthesizer().synthesize(results, review)
        self._persist(audit_dir, scorecard, results, review)
        return scorecard

    def _persist(
        self, audit_dir: Path, scorecard: SelfAuditScorecard,
        results: list, review,
    ) -> None:
        try:
            audit_dir.mkdir(parents=True, exist_ok=True)
            (audit_dir / "scorecard.json").write_text(
                scorecard.model_dump_json(indent=2), encoding="utf-8"
            )
            (audit_dir / "adversarial_review.json").write_text(
                review.model_dump_json(indent=2), encoding="utf-8"
            )
            lines = ["# Self-Audit Report", "", f"- Audit ID: {audit_dir.name}",
                     f"- Veredito: {scorecard.overall_verdict}",
                     f"- Sucesso: {scorecard.success_rate:.0%}",
                     f"- Auditor degradado: {review.adversarial_degraded}",
                     f"- {scorecard.summary}", "", "## Missões"]
            for r in results:
                lines.append(
                    f"- [{'OK' if r.success else 'FAIL'}] {r.mission_name} ({r.mode.value})"
                    + (f" — {r.error}" if r.error else "")
                )
            (audit_dir / "self_audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass