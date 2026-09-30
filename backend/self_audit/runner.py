"""
AuditRunner — executa o pack canônico (v4.6.0 + run_missions).

run_missions(): executa missões e retorna resultados (sem agregar/persistir),
para uso pelo SelfAuditPipeline. run(): retrocompatível (agrega + persiste).
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
    def __init__(self, client: Any | None = None, config: Settings | None = None) -> None:
        self._config = config if config is not None else settings
        if client is not None:
            self._client = client
        else:
            from backend.core.llm_client import LLMClient
            self._client = LLMClient(self._config)

    async def review(self, context: dict[str, Any]) -> AdversarialReview:
        data = await self._client.complete_json(
            system_prompt=("Você é um auditor adversarial cético. Responda APENAS JSON válido."),
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

    async def run_missions(self, request: SelfAuditRequest) -> list[AuditMissionResult]:
        """Executa as missões selecionadas e retorna resultados (sem agregar)."""
        results: list[AuditMissionResult] = []
        for mission in select_missions(request):
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
            if request.fail_fast and not success:
                break
        return results

    def _aggregate(self, results, review) -> SelfAuditScorecard:
        from backend.self_audit.scorecard import ScorecardSynthesizer
        return ScorecardSynthesizer().synthesize(results, review)

    async def run(self, request: SelfAuditRequest | None = None) -> SelfAuditScorecard:
        req = request or SelfAuditRequest(
            max_missions_per_mode=self._config.SELF_AUDIT_MAX_MISSIONS_PER_MODE,
            adversarial_enabled=self._config.SELF_AUDIT_ADVERSARIAL_ENABLED,
        )
        results = await self.run_missions(req)

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