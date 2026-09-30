"""
GoldenRunner — executa as 7 Golden Missions sequencialmente (v5.0.0 GA).

Persistência isolada em artifacts/golden/<mission_id>/ (mission_state.json +
golden_report.md) + consolidação em artifacts/golden/<run_id>/.
O dispatcher é injetável (fakes em testes; pipelines reais em produção).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from backend.core.config import Settings, settings
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode, ProjectType
from backend.domain.models import MissionState
from backend.golden.pack import GoldenMission, get_golden_pack
from pydantic import BaseModel, Field

Dispatch = Callable[[GoldenMission], Awaitable[MissionState]]


class GoldenMissionResult(BaseModel):
    id: str
    name: str
    mode: ProjectMode
    success: bool
    mission_id: str
    artifacts_path: str
    error: Optional[str] = None


class GoldenReport(BaseModel):
    run_id: str
    total: int
    success_count: int
    all_passed: bool
    results: list[GoldenMissionResult] = Field(default_factory=list)
    summary: str
    artifacts_path: str


def _mission_report(m: GoldenMission, state: MissionState) -> str:
    return (
        f"# Golden Mission {m.id} — {m.name}\n\n"
        f"- Modo: {m.mode.value}\n- Intent: {m.intent}\n"
        f"- Status: {state.status.value}\n"
    )


class GoldenRunner:
    def __init__(
        self,
        config: Settings | None = None,
        root: Path | None = None,
        dispatcher: Optional[Dispatch] = None,
    ) -> None:
        self._config = config if config is not None else settings
        self._root = root if root is not None else Path(self._config.GOLDEN_ARTIFACTS_DIR)
        self._artifacts = ArtifactManager(root=self._root)
        self._dispatcher = dispatcher or self._default_dispatch

    @property
    def root(self) -> Path:
        return self._root

    # ── Dispatcher real (produção) ──
    async def _default_dispatch(self, m: GoldenMission) -> MissionState:
        am = lambda: ArtifactManager(root=self._root)  # noqa: E731
        if m.mode == ProjectMode.DISCOVER:
            from backend.discover.pipeline import DiscoverPipeline
            from backend.discover.schemas import DiscoverRequest
            pipe = DiscoverPipeline(artifact_manager=am(), config=self._config)
            res = await pipe.run(DiscoverRequest(
                theme=m.intent, max_opportunities=m.options.get("max_opportunities", 5),
            ))
            return MissionState(
                mission_id=pipe.last_mission_id or uuid.uuid4().hex,
                project_id=uuid.uuid4().hex, mode=m.mode,
                status=MissionStatus.COMPLETED if res.opportunities else MissionStatus.FAILED,
                current_stage="golden", mode_payload={"golden_id": m.id},
            )
        if m.mode == ProjectMode.VALIDATE:
            from backend.validate.pipeline import ValidatePipeline
            from backend.validate.schemas import ValidateRequest
            pipe = ValidatePipeline(artifact_manager=am(), config=self._config)
            return await pipe.run(ValidateRequest(idea_text=m.intent))
        if m.mode == ProjectMode.VALIDATE_AND_BUILD:
            from backend.validate_and_build.pipeline import ValidateAndBuildPipeline
            from backend.validate_and_build.schemas import ValidateAndBuildRequest
            pipe = ValidateAndBuildPipeline(artifact_manager=am(), config=self._config)
            return await pipe.run(
                ValidateAndBuildRequest(
                    idea_text=m.intent,
                    auto_build=m.options.get("auto_build", True),
                    require_human_confirmation=False,
                ),
                no_build=m.options.get("no_build", False),
            )
        if m.mode == ProjectMode.BUILD:
            from backend.build.pipeline import BuildPipeline
            ptype = ProjectType(m.options.get("project_type", "WEB_APP"))
            pipe = BuildPipeline(artifact_manager=am(), config=self._config, project_type=ptype)
            return await pipe.run(m.intent, project_name=m.name)
        # SELF_AUDIT
        from backend.self_audit.pipeline import SelfAuditPipeline
        from backend.self_audit.schemas import SelfAuditRequest
        sp = SelfAuditPipeline(config=self._config, root_base=self._root)
        sc = await sp.run(SelfAuditRequest(max_missions_per_mode=1, adversarial_enabled=False))
        ok = sc.overall_verdict in ("HEALTHY", "DEGRADED")
        return MissionState(
            mission_id=(sp.last_audit_dir.name if sp.last_audit_dir else uuid.uuid4().hex),
            project_id=uuid.uuid4().hex, mode=m.mode,
            status=MissionStatus.COMPLETED if ok else MissionStatus.FAILED,
            current_stage="golden",
            mode_payload={"golden_id": m.id, "verdict": sc.overall_verdict},
        )

    # ── Execução ──
    async def run(self) -> GoldenReport:
        run_id = uuid.uuid4().hex
        results: list[GoldenMissionResult] = []

        for m in get_golden_pack():
            error: Optional[str] = None
            try:
                state = await self._dispatcher(m)
                success = state.status == MissionStatus.COMPLETED
                mid = state.mission_id
                error = state.mode_payload.get("error")
                self._artifacts.save_artifact(mid, "golden_report.md", _mission_report(m, state))
                self._artifacts.save_mission_state(state)
            except Exception as exc:
                success = False
                error = f"{type(exc).__name__}: {exc}"
                mid = uuid.uuid4().hex
                failed = MissionState(
                    mission_id=mid, project_id=uuid.uuid4().hex, mode=m.mode,
                    status=MissionStatus.FAILED, current_stage="golden",
                    mode_payload={"golden_id": m.id, "error": error},
                )
                self._artifacts.save_mission_state(failed)

            results.append(GoldenMissionResult(
                id=m.id, name=m.name, mode=m.mode, success=success,
                mission_id=mid, artifacts_path=str(self._root / mid), error=error,
            ))

        success_count = sum(1 for r in results if r.success)
        all_passed = success_count == len(results)
        report = GoldenReport(
            run_id=run_id, total=len(results), success_count=success_count,
            all_passed=all_passed, results=results,
            summary=f"{success_count}/{len(results)} golden missions OK.",
            artifacts_path=str(self._root / run_id),
        )

        lines = ["# Golden Missions Report", "", f"- Run: {run_id}",
                 f"- Passed: {success_count}/{len(results)}", "", "## Missões"]
        for r in results:
            lines.append(f"- [{'OK' if r.success else 'FAIL'}] {r.id} {r.name} ({r.mode.value})"
                         + (f" — {r.error}" if r.error else ""))
        self._artifacts.save_artifact(run_id, "golden_report.md", "\n".join(lines) + "\n")
        self._artifacts.save_artifact(run_id, "golden_state.json",
                                      report.model_dump_json(indent=2))
        return report