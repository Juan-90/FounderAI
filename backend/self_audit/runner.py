"""
AuditRunner — executa o pack canônico e consolida o scorecard (v4.6.0).

Reutiliza BuildPipeline / ValidatePipeline / ValidateAndBuildPipeline via injeção
(testável sem LLM/Docker). Aplica objective checks determinísticos após cada missão:
  • status final == COMPLETED
  • artefatos obrigatórios presentes (state.artifacts; disco SOMENTE se o
    diretório da missão existir — pipelines reais gravam, fakes não)
  • relatório final presente e não-vazio
  • VALIDATE/VAB: veredito ∈ {INVESTIGATE,BUILD,PIVOT,DISCARD}; VAB: gate válido

A revisão adversarial (LLM) é opcional/injetável e degrada graciosamente.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from backend.build.pipeline import BuildPipeline
from backend.core.config import Settings, settings
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode, ProjectType
from backend.domain.models import MissionState
from backend.self_audit.canonical_pack import CanonicalMission, select_missions
from backend.self_audit.schemas import (
    AdversarialReview,
    AuditMissionResult,
    SelfAuditRequest,
    SelfAuditScorecard,
)
from backend.validate.pipeline import ValidatePipeline
from backend.validate.schemas import ValidateRequest
from backend.validate_and_build.pipeline import ValidateAndBuildPipeline
from backend.validate_and_build.schemas import ValidateAndBuildRequest

VALID_VERDICTS = {"INVESTIGATE", "BUILD", "PIVOT", "DISCARD"}

BuildFactory = Callable[[Optional[ProjectType]], Any]


class ValidatePipelineLike(Protocol):
    async def run(self, request: ValidateRequest, on_stage: Any = None,
                  mission_id: Optional[str] = None) -> MissionState: ...


class VabPipelineLike(Protocol):
    async def run(self, request: ValidateAndBuildRequest, confirm: Any = None,
                  no_build: bool = False) -> MissionState: ...


class AdversarialReviewerLike(Protocol):
    async def review(self, context: dict[str, Any]) -> AdversarialReview: ...


class LLMAdversarialReviewer:
    """Auditor adversarial baseado em LLM (best-effort)."""

    def __init__(self, client: Any | None = None, config: Settings | None = None) -> None:
        self._config = config if config is not None else settings
        if client is not None:
            self._client = client
        else:
            from backend.core.llm_client import LLMClient
            self._client = LLMClient(self._config)

    async def review(self, context: dict[str, Any]) -> AdversarialReview:
        data = await self._client.complete_json(
            system_prompt=(
                "Você é um auditor adversarial cético. Analise os resultados da "
                "auto-auditoria e aponte inconsistências, overclaims e falhas. "
                "Responda APENAS JSON válido."
            ),
            user_prompt=(
                "RESULTADOS:\n" + json.dumps(context, ensure_ascii=False) + "\n\n"
                'Retorne: {"findings": ["..."], "severity_counts": {"critical": 0, '
                '"major": 0, "minor": 0}, "overclaim_detected": false, '
                '"consistency_score": 0.0-1.0, "notes": "..."}'
            ),
        )
        return AdversarialReview(
            findings=list(data.get("findings", [])),
            severity_counts={k: int(v) for k, v in (data.get("severity_counts") or {}).items()},
            overclaim_detected=bool(data.get("overclaim_detected", False)),
            consistency_score=float(data.get("consistency_score", 1.0)),
            notes=str(data.get("notes", "")),
        )


class AuditRunner:
    """Executa missões canônicas e consolida o SelfAuditScorecard."""

    def __init__(
        self,
        config: Settings | None = None,
        root: Path | None = None,
        build_factory: BuildFactory | None = None,
        validate_pipeline: ValidatePipelineLike | None = None,
        vab_pipeline: VabPipelineLike | None = None,
        adversarial_reviewer: AdversarialReviewerLike | None = None,
    ) -> None:
        self._config = config if config is not None else settings
        self._root = root if root is not None else Path(self._config.SELF_AUDIT_ARTIFACTS_DIR)
        self._build_factory = build_factory or self._default_build_factory()
        self._validate = validate_pipeline or ValidatePipeline(
            artifact_manager=ArtifactManager(root=self._root), config=self._config
        )
        self._vab = vab_pipeline or ValidateAndBuildPipeline(
            artifact_manager=ArtifactManager(root=self._root), config=self._config
        )
        self._reviewer = adversarial_reviewer

    def _default_build_factory(self) -> BuildFactory:
        def factory(ptype: Optional[ProjectType]) -> Any:
            return BuildPipeline(
                artifact_manager=ArtifactManager(root=self._root),
                config=self._config, project_type=ptype,
            )
        return factory

    # ── Objective checks ──
    def _extract_verdict(self, state: MissionState) -> str:
        vp = state.mode_payload
        gate = vp.get("gate") or {}
        rec = vp.get("recommendation") or {}
        return str(gate.get("source_verdict") or rec.get("verdict") or "")

    def _objective_checks(
        self, mission: CanonicalMission, state: MissionState, root: Path | None
    ) -> dict[str, bool]:
        checks: dict[str, bool] = {}
        checks["status_completed"] = state.status == MissionStatus.COMPLETED

        saved = {a.name for a in state.artifacts}
        names_ok = set(mission.required_artifacts) <= saved
        # Checagem em disco SOMENTE se o diretório da missão existir
        # (pipelines reais gravam; fakes de teste não).
        disk_ok = True
        if root is not None:
            mdir = root / state.mission_id
            if mdir.exists():
                disk_ok = all((mdir / n).exists() for n in mission.required_artifacts)
        checks["artifacts_present"] = names_ok and disk_ok

        report_ok = mission.report_file in saved
        if root is not None:
            mdir = root / state.mission_id
            if mdir.exists():
                rp = mdir / mission.report_file
                report_ok = rp.exists() and rp.read_text(encoding="utf-8").strip() != ""
        checks["report_not_empty"] = report_ok

        if mission.mode in (ProjectMode.VALIDATE, ProjectMode.VALIDATE_AND_BUILD):
            checks["verdict_valid"] = self._extract_verdict(state) in VALID_VERDICTS
            if mission.mode == ProjectMode.VALIDATE_AND_BUILD:
                gate = state.mode_payload.get("gate") or {}
                checks["gate_valid"] = isinstance(gate.get("should_build"), bool)
        return checks

    # ── Execução de missão ──
    async def _run_mission(self, mission: CanonicalMission) -> MissionState:
        mid = uuid.uuid4().hex
        if mission.mode == ProjectMode.BUILD:
            build = self._build_factory(mission.project_type)
            return await build.run(mission.intent, project_name=mission.mission_name,
                                   mission_id=mid)
        if mission.mode == ProjectMode.VALIDATE:
            return await self._validate.run(
                ValidateRequest(idea_text=mission.intent), mission_id=mid
            )
        return await self._vab.run(ValidateAndBuildRequest(
            idea_text=mission.intent, require_human_confirmation=False,
        ))

    # ── Consolidação ──
    def _aggregate(
        self, results: list[AuditMissionResult], review: AdversarialReview
    ) -> SelfAuditScorecard:
        total = len(results)
        succ = sum(1 for r in results if r.success)
        success_rate = (succ / total) if total else 0.0

        def rate(mode: ProjectMode) -> Optional[float]:
            subset = [r for r in results if r.mode == mode]
            if not subset:
                return None
            return sum(1 for r in subset if r.success) / len(subset)

        checks_passed = sum(sum(r.objective_checks.values()) for r in results)
        checks_total = sum(len(r.objective_checks) for r in results)

        critical_count = review.severity_counts.get("critical", 0)
        critical_findings = review.findings[:critical_count] if critical_count else []

        if total == 0:
            verdict = "CRITICAL"
        elif success_rate >= 0.8 and not critical_findings and not review.overclaim_detected:
            verdict = "HEALTHY"
        elif success_rate >= 0.5 and not critical_findings:
            verdict = "DEGRADED"
        else:
            verdict = "CRITICAL"

        confidence = round(max(0.0, min(1.0, success_rate * review.consistency_score)), 3)
        summary = (
            f"{succ}/{total} missões OK (taxa {success_rate:.0%}); "
            f"veredito {verdict}; {len(review.findings)} achado(s) adversarial(is)."
        )
        return SelfAuditScorecard(
            total_missions=total, success_rate=round(success_rate, 3),
            build_success_rate=rate(ProjectMode.BUILD),
            validate_success_rate=rate(ProjectMode.VALIDATE),
            vab_success_rate=rate(ProjectMode.VALIDATE_AND_BUILD),
            objective_checks_passed=int(checks_passed), objective_checks_total=int(checks_total),
            adversarial_findings=list(review.findings), critical_findings=critical_findings,
            overall_verdict=verdict, confidence=confidence, summary=summary,
        )

    async def run(self, request: SelfAuditRequest | None = None) -> SelfAuditScorecard:
        req = request or SelfAuditRequest(
            max_missions_per_mode=self._config.SELF_AUDIT_MAX_MISSIONS_PER_MODE,
            adversarial_enabled=self._config.SELF_AUDIT_ADVERSARIAL_ENABLED,
        )
        results: list[AuditMissionResult] = []
        for mission in select_missions(req):
            started = time.perf_counter()
            error: str | None = None
            checks: dict[str, bool] = {}
            artifacts_path: str | None = None
            success = False
            try:
                state = await self._run_mission(mission)
                checks = self._objective_checks(mission, state, self._root)
                success = all(checks.values())
                artifacts_path = str(self._root / state.mission_id)
            except Exception as exc:
                success = False
                error = f"{type(exc).__name__}: {exc}"

            results.append(AuditMissionResult(
                mission_name=mission.mission_name, mode=mission.mode, success=success,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=error, objective_checks=checks, artifacts_path=artifacts_path,
            ))
            if req.fail_fast and not success:
                break

        review = AdversarialReview()
        if req.adversarial_enabled and self._reviewer is not None:
            try:
                review = await self._reviewer.review(
                    {"results": [r.model_dump() for r in results]}
                )
            except Exception as exc:
                review = AdversarialReview(notes=f"Auditor adversarial falhou: {exc}")

        scorecard = self._aggregate(results, review)
        self._persist(scorecard, results)
        return scorecard

    def _persist(self, scorecard: SelfAuditScorecard, results: list[AuditMissionResult]) -> None:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            (self._root / "scorecard.json").write_text(
                scorecard.model_dump_json(indent=2), encoding="utf-8"
            )
            lines = ["# Self-Audit Report", "", f"- Veredito: {scorecard.overall_verdict}",
                     f"- Sucesso: {scorecard.success_rate:.0%}", f"- {scorecard.summary}", "",
                     "## Missões"]
            for r in results:
                lines.append(
                    f"- [{'OK' if r.success else 'FAIL'}] {r.mission_name} ({r.mode.value})"
                    + (f" — {r.error}" if r.error else "")
                )
            (self._root / "self_audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass