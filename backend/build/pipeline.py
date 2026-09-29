"""
BuildPipeline — orquestrador do Modo BUILD (v4.3: game_spec.json + env headless).

Fix v4.3.0: Protocol RepairAgentLike com anotação de retorno completa
(tuple[dict, dict, str]), tornando QAAgent estruturalmente compatível e
permitindo o unpack do resultado de generate_fix.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol
from uuid import uuid4

from backend.analysis.models import StaticAnalysisResult
from backend.analysis.static_gate import StaticAnalysisGate
from backend.build.agents import (
    ArchitectureAgent, BuildReporter, ImplementationAgent, RequirementsAgent,
)
from backend.build.profiles import BaseProjectProfile, GameProfile, profile_for
from backend.core.config import Settings, settings
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode, ProjectType
from backend.domain.models import MissionState
from backend.qa.agent import QAAgent
from backend.qa.schemas import TDDRequest, TDDResult

StageCallback = Callable[[int, str], None]


class StaticGateLike(Protocol):
    def run(self, files: dict[str, str]) -> StaticAnalysisResult: ...


class RepairAgentLike(Protocol):
    """Contrato do agente de reparo (satisfeito por QAAgent)."""

    async def generate_fix(
        self,
        source_files: dict[str, str],
        test_files: dict[str, str],
        analysis: str,
    ) -> tuple[dict[str, str], dict[str, str], str]: ...


class TDDRunnerLike(Protocol):
    async def run(self, request: TDDRequest) -> TDDResult: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BuildPipeline:
    def __init__(
        self,
        client: Any | None = None,
        artifact_manager: ArtifactManager | None = None,
        static_gate: StaticGateLike | None = None,
        repair_agent: RepairAgentLike | None = None,
        tdd_loop: TDDRunnerLike | None = None,
        config: Settings | None = None,
        project_type: ProjectType | None = None,
        profile: BaseProjectProfile | None = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._artifacts: ArtifactManager = (
            artifact_manager if artifact_manager is not None else ArtifactManager(self._config)
        )
        if profile is not None:
            self._profile = profile
        else:
            effective_type = project_type or ProjectType(self._config.BUILD_DEFAULT_PROJECT_TYPE)
            self._profile = profile_for(effective_type, headless=self._config.BUILD_GAME_HEADLESS)

        self._requirements = RequirementsAgent(client, self._profile)
        self._architecture = ArchitectureAgent(client, self._profile)
        self._implementation = ImplementationAgent(client, self._profile)
        self._reporter = BuildReporter(client)
        self._gate: StaticGateLike = static_gate if static_gate is not None else StaticAnalysisGate()
        self._repair: RepairAgentLike = repair_agent if repair_agent is not None else QAAgent()
        if tdd_loop is not None:
            self._tdd: TDDRunnerLike = tdd_loop
        else:
            from backend.qa.orchestrator import TDDLoop
            self._tdd = TDDLoop(config=self._config)

    @property
    def profile(self) -> BaseProjectProfile:
        return self._profile

    @staticmethod
    def _emit(on_stage: Optional[StageCallback], index: int, label: str) -> None:
        if on_stage is not None:
            on_stage(index, label)

    def _advance(self, state: MissionState, stage: str) -> None:
        state.current_stage = stage
        state.updated_at = _utcnow()

    def _save(self, state: MissionState, name: str, content: str) -> None:
        artifact = self._artifacts.save_artifact(state.mission_id, name, content)
        state.artifacts.append(artifact)

    def _save_game_spec(self, state: MissionState) -> None:
        spec = {
            "engine": self._config.BUILD_GAME_ENGINE,
            "headless": self._config.BUILD_GAME_HEADLESS,
            "project_type": self._profile.project_type.value,
            "file_structure": self._profile.file_structure,
            "execution_env": self._profile.execution_env,
        }
        self._save(state, "game_spec.json", json.dumps(spec, indent=2))

    async def _quality_gate(
        self,
        state: MissionState,
        files: dict[str, str],
        test_files: dict[str, str],
    ) -> tuple[dict[str, str], dict[str, str]]:
        result = self._gate.run({**files, **test_files})
        cycles = 0
        while not result.passed and cycles < self._config.STATIC_ANALYSIS_MAX_CYCLES:
            files, test_files, _p = await self._repair.generate_fix(files, test_files, result.summary)
            result = self._gate.run({**files, **test_files})
            cycles += 1
        state.mode_payload["static_gate_passed"] = result.passed
        state.mode_payload["static_gate_cycles"] = cycles
        return files, test_files

    async def run(
        self,
        intent: str,
        project_name: str = "BarbeariaApp",
        on_stage: Optional[StageCallback] = None,
    ) -> MissionState:
        state = MissionState(
            mission_id=uuid4().hex, project_id=uuid4().hex,
            mode=ProjectMode.BUILD, status=MissionStatus.IN_PROGRESS,
            current_stage="init",
            mode_payload={
                "project_name": project_name, "intent": intent,
                "project_type": self._profile.project_type.value,
            },
        )
        tests_success = False
        escalated = False

        try:
            self._emit(on_stage, 1, "Generating Requirements...")
            req_md = await self._requirements.generate(intent)
            self._save(state, "requirements.md", req_md)
            self._advance(state, "requirements")

            self._emit(on_stage, 2, "Designing Architecture...")
            arch_md = await self._architecture.generate(req_md)
            self._save(state, "architecture.md", arch_md)
            self._advance(state, "architecture")

            self._emit(on_stage, 3, "Generating Code & Tests...")
            files, test_files = await self._implementation.generate(arch_md)
            for name, content in files.items():
                self._save(state, name, content)
            for name, content in test_files.items():
                self._save(state, name, content)
            if isinstance(self._profile, GameProfile):
                self._save_game_spec(state)
            self._advance(state, "implementation")

            self._emit(on_stage, 4, "Static Analysis Gate (Ruff/Mypy)...")
            files, test_files = await self._quality_gate(state, files, test_files)
            self._advance(state, "quality_gate")

            self._emit(on_stage, 5, "Sandbox Execution & TDD Loop...")
            tdd = await self._tdd.run(TDDRequest(
                source_files=files, test_files=test_files, goal=intent,
                mission_id=state.mission_id,
                env=dict(self._profile.execution_env),
            ))
            tests_success = tdd.success
            escalated = tdd.escalated
            state.mode_payload["tdd_summary"] = tdd.summary
            self._advance(state, "test_execution")

            self._emit(on_stage, 6, "Generating Final Report...")
            report_md = await self._reporter.generate({
                "project_name": project_name, "intent": intent,
                "project_type": self._profile.project_type.value,
                "files": sorted(files.keys()), "test_files": sorted(test_files.keys()),
                "static_gate_passed": state.mode_payload.get("static_gate_passed"),
                "tests_success": tests_success, "escalated": escalated,
                "tdd_summary": tdd.summary,
            })
            self._save(state, "report.md", report_md)
            self._advance(state, "report")

            if tests_success:
                state.status = MissionStatus.COMPLETED
            elif escalated:
                state.status = MissionStatus.ESCALATED
            else:
                state.status = MissionStatus.FAILED

        except Exception as exc:
            state.status = MissionStatus.FAILED
            state.mode_payload["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            state.updated_at = _utcnow()
            self._artifacts.save_mission_state(state)

        return state