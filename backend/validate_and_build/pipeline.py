"""
ValidateAndBuildPipeline — orquestrador da Ponte Direta (v5.3.0 + Memory Hooks).

v5.3.0: Injeta memória do projeto no contexto dos agentes e grava ambas as fases
(VALIDATE + BUILD) na mesma memória do projeto.
v4.5.0 hotfix: sub-pipelines tipados por Protocols estruturais.
"""

from __future__ import annotations

import json
import uuid
from uuid import uuid4
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from backend.build.pipeline import BuildPipeline
from backend.core.config import Settings, settings
from backend.core.memory_compiler import MemoryContextCompiler
from backend.core.memory_hooks import (
    attach_memory_to_intent,
    build_memory_block,
    record_vab_completion,
    resolve_memory,
)
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.memory_store import DiskProjectMemoryStore
from backend.domain.models import MissionState
from backend.validate.pipeline import ValidatePipeline
from backend.validate.schemas import ValidateRequest
from backend.validate_and_build.gate import DecisionGate
from backend.validate_and_build.schemas import (
    BuildGateDecision,
    BuildSeed,
    ValidateAndBuildRequest,
)

ConfirmCallback = Callable[[BuildGateDecision], bool]
StageCallback = Callable[[int, str], None]

class ValidatePipelineLike(Protocol):
    """Contrato estrutural do sub-pipeline de validação (reais e fakes)."""

    async def run(
        self,
        request: ValidateRequest,
        on_stage: Optional[StageCallback] = None,
        mission_id: Optional[str] = None,
    ) -> MissionState: ...

class BuildPipelineLike(Protocol):
    """Contrato estrutural do sub-pipeline de construção (reais e fakes)."""

    async def run(
        self,
        intent: str,
        project_name: str = "BarbeariaApp",
        on_stage: Optional[StageCallback] = None,
        mission_id: Optional[str] = None,
        seed: Optional[BuildSeed] = None,
    ) -> MissionState: ...

class ValidateAndBuildPipeline:
    """Orquestra VALIDATE → DecisionGate → BUILD com artefatos combinados."""

    def __init__(
        self,
        client: Any | None = None,
        artifact_manager: ArtifactManager | None = None,
        config: Settings | None = None,
        validate_pipeline: ValidatePipelineLike | None = None,
        build_pipeline: BuildPipelineLike | None = None,
        gate: DecisionGate | None = None,
        memory_store: Optional[DiskProjectMemoryStore] = None,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._artifacts: ArtifactManager = (
            artifact_manager
            if artifact_manager is not None
            else ArtifactManager(root=Path(self._config.VAB_ARTIFACTS_DIR))
        )
        self._validate: ValidatePipelineLike = (
            validate_pipeline
            if validate_pipeline is not None
            else ValidatePipeline(
                client=client, artifact_manager=self._artifacts, config=self._config
            )
        )
        self._build: BuildPipelineLike = (
            build_pipeline
            if build_pipeline is not None
            else BuildPipeline(
                client=client, artifact_manager=self._artifacts, config=self._config
            )
        )
        self._gate = gate or DecisionGate(self._config)
        self._memory_store = memory_store
        self._project_id = project_id
        self._project_name = project_name
        self._compiler = MemoryContextCompiler(memory_store) if memory_store else None

    @property
    def artifacts(self) -> ArtifactManager:
        return self._artifacts

    def _save(self, state: MissionState, name: str, content: str) -> None:
        artifact = self._artifacts.save_artifact(state.mission_id, name, content)
        state.artifacts.append(artifact)

    @staticmethod
    def _to_validate_request(request: ValidateAndBuildRequest) -> ValidateRequest:
        return ValidateRequest(
            idea_text=request.idea_text, name=request.name,
            target_audience=request.target_audience, problem=request.problem,
            solution=request.solution, business_model=request.business_model,
            constraints=request.constraints, context_files=request.context_files,
            project_type=request.project_type,
        )

    @staticmethod
    def _extract_seed(request: ValidateAndBuildRequest, vp: dict[str, Any]) -> BuildSeed:
        tech = vp.get("technical_feasibility", {}) or {}
        risks = vp.get("risks_contrarian", {}) or {}
        outline = tech.get("technical_mvp_outline", "")
        return BuildSeed(
            idea_profile=vp.get("idea_profile", {}) or {},
            recommended_mvp_scope=[outline] if outline else [],
            constraints=[request.constraints] if request.constraints else [],
            risks_to_mitigate=(risks.get("reasons_to_kill") or [])
            + (risks.get("regulatory_risks") or []),
            non_goals=[],
            suggested_project_type=request.project_type,
        )

    def _composite_report(
        self, state: MissionState, decision: BuildGateDecision,
        bstate: MissionState | None,
    ) -> str:
        lines = [
            "# Composite Report (VALIDATE_AND_BUILD)", "",
            "## Validação",
            f"- Veredito: {decision.source_verdict}",
            f"- Confiança: {decision.confidence:.2f}", "",
            "## Gate Decision",
            f"- should_build: {decision.should_build}",
            f"- needs_human_confirmation: {decision.needs_human_confirmation}",
            f"- reason: {decision.reason}", "",
            "## Build",
        ]
        if bstate is None:
            lines.append(
                "- Não executado. Motivo: "
                + state.mode_payload.get("build_skipped_reason", "n/a")
            )
        else:
            lines.append(f"- Status: {bstate.status.value}")
            lines.append(f"- TDD: {bstate.mode_payload.get('tdd_summary', '')}")
            lines.append(f"- Artefatos: {', '.join(a.name for a in bstate.artifacts) or '(nenhum)'}")
        return "\n".join(lines) + "\n"

    async def run(
        self,
        request: ValidateAndBuildRequest,
        confirm: Optional[ConfirmCallback] = None,
        no_build: bool = False,
    ) -> MissionState:
        mission_id = uuid.uuid4().hex
        state = MissionState(
            mission_id=mission_id, project_id=uuid4().hex,
            mode=ProjectMode.VALIDATE_AND_BUILD, status=MissionStatus.IN_PROGRESS,
            current_stage="validate", mode_payload={},
        )
        bstate: MissionState | None = None
        
        # Injeção de memória (v5.3.0)
        memory = None
        if (self._memory_store is not None and self._compiler is not None
                and (self._project_id or self._project_name)):
            memory = resolve_memory(self._memory_store, self._project_id, self._project_name)
            if memory is not None:
                block = build_memory_block(self._compiler, memory.project_id)
                request = request.model_copy(update={
                    "idea_text": attach_memory_to_intent(request.idea_text, block)})
        
        try:
            # 1 — Validação
            vstate = await self._validate.run(
                self._to_validate_request(request), mission_id=mission_id
            )
            vp = vstate.mode_payload
            state.mode_payload["validation"] = {
                "status": vstate.status.value,
                "recommendation": vp.get("recommendation", {}),
                "evidence_gaps": vp.get("evidence_gaps", []),
            }
            self._save(state, "validation_report.md", vp.get("final_report", ""))

            # 2 — Gate
            rec = vp.get("recommendation", {}) or {}
            decision = self._gate.evaluate(
                rec.get("verdict", "INVESTIGATE"),
                rec.get("confidence", 0.0),
                rec.get("conditions", []),
                require_human_confirmation=request.require_human_confirmation,
                min_confidence=request.min_confidence_to_autobuild,
            )
            state.mode_payload["gate"] = decision.model_dump()
            self._save(state, "gate_decision.json",
                       json.dumps(decision.model_dump(), indent=2, ensure_ascii=False))

            # 3 — Encerra sem build?
            if no_build or not request.auto_build or not decision.should_build:
                state.mode_payload["build_skipped_reason"] = (
                    "no_build" if no_build
                    else "auto_build desabilitado" if not request.auto_build
                    else decision.reason
                )
                state.status = MissionStatus.COMPLETED
                self._save(state, "composite_report.md",
                           self._composite_report(state, decision, None))
                return state

            # 4 — Confirmação humana
            if decision.needs_human_confirmation:
                state.status = MissionStatus.WAITING_HUMAN
                if confirm is None:
                    self._save(state, "composite_report.md",
                               self._composite_report(state, decision, None))
                    return state
                approved = confirm(decision)
                if not approved:
                    state.status = MissionStatus.COMPLETED
                    state.mode_payload["build_skipped_reason"] = "Rejeitado pelo fundador."
                    self._save(state, "composite_report.md",
                               self._composite_report(state, decision, None))
                    return state
                state.status = MissionStatus.IN_PROGRESS

            # 5 — Build
            seed = self._extract_seed(request, vp)
            bstate = await self._build.run(
                request.idea_text,
                project_name=request.name or "VABApp",
                mission_id=mission_id,
                seed=seed,
            )
            state.mode_payload["build"] = {
                "status": bstate.status.value,
                "tdd_summary": bstate.mode_payload.get("tdd_summary", ""),
                "files": [a.name for a in bstate.artifacts],
            }
            self._save(state, "composite_report.md",
                       self._composite_report(state, decision, bstate))
            state.status = (
                MissionStatus.COMPLETED if bstate.status == MissionStatus.COMPLETED
                else MissionStatus.ESCALATED if bstate.status == MissionStatus.ESCALATED
                else MissionStatus.FAILED
            )

        except Exception as exc:
            state.status = MissionStatus.FAILED
            state.mode_payload["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            self._artifacts.save_mission_state(state)
            
            # Gravação de memória (v5.3.0) — fail-open
            if memory is not None and self._memory_store is not None:
                try:
                    record_vab_completion(
                        self._memory_store, memory, state,
                        self._artifacts.root / state.mission_id)
                except Exception:
                    pass

        return state