"""
Testes de integração do ValidateAndBuildPipeline (v4.5.0) — os 3 caminhos do gate.

Usa sub-pipelines fake (sem LLM/Docker): determinístico e roda em CI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.models import MissionState
from backend.validate.schemas import ValidatePayload
from backend.validate_and_build.gate import DecisionGate
from backend.validate_and_build.pipeline import ValidateAndBuildPipeline
from backend.validate_and_build.schemas import BuildGateDecision, ValidateAndBuildRequest


class FakeValidatePipeline:
    def __init__(self, recommendation: dict[str, Any]) -> None:
        self.rec = recommendation

    async def run(self, request, on_stage=None, mission_id=None) -> MissionState:
        return MissionState(
            mission_id=mission_id or "v-fake", project_id="p",
            mode=ProjectMode.VALIDATE, status=MissionStatus.COMPLETED,
            current_stage="report",
            mode_payload=ValidatePayload.build(
                idea_profile={"summary": "x", "gaps": ["g1"],
                              "clarified_fields": {"constraints": "pouco tempo"}},
                technical_feasibility={"technical_mvp_outline": "MVP web"},
                risks_contrarian={"reasons": [], "reasons_to_kill": ["r1"],
                                  "regulatory_risks": ["lgpd"]},
                recommendation=self.rec,
                final_report="# Validation Report",
            ),
        )


class FakeBuildPipeline:
    def __init__(self) -> None:
        self.called = False
        self.seed = None

    async def run(self, intent, project_name="App", on_stage=None,
                  mission_id=None, seed=None) -> MissionState:
        self.called = True
        self.seed = seed
        return MissionState(
            mission_id=mission_id or "b-fake", project_id="p",
            mode=ProjectMode.BUILD, status=MissionStatus.COMPLETED,
            current_stage="report", mode_payload={"tdd_summary": "ok"},
        )


def _make_pipe(tmp_path: Path, rec: dict[str, Any]) -> tuple[ValidateAndBuildPipeline, FakeBuildPipeline]:
    build = FakeBuildPipeline()
    pipe = ValidateAndBuildPipeline(
        artifact_manager=ArtifactManager(root=tmp_path),
        validate_pipeline=FakeValidatePipeline(rec),
        build_pipeline=build,
        gate=DecisionGate(),
    )
    return pipe, build


# ─────────────────────────────────────────────────────────────
# Caminho 1 — DISCARD/PIVOT: não builda
# ─────────────────────────────────────────────────────────────

def test_caminho_discard_nao_builda(tmp_path: Path) -> None:
    pipe, build = _make_pipe(tmp_path, {"verdict": "DISCARD", "confidence": 0.9, "conditions": []})
    state = asyncio.run(pipe.run(ValidateAndBuildRequest(idea_text="ideia ruim")))

    assert state.status == MissionStatus.COMPLETED
    assert build.called is False
    gate = BuildGateDecision(**state.mode_payload["gate"])
    assert gate.should_build is False

    mid = state.mission_id
    assert (tmp_path / mid / "gate_decision.json").exists()
    assert (tmp_path / mid / "validation_report.md").exists()
    assert (tmp_path / mid / "composite_report.md").exists()
    assert (tmp_path / mid / "mission_state.json").exists()


# ─────────────────────────────────────────────────────────────
# Caminho 2 — BUILD com confirmação humana (WAITING_HUMAN)
# ─────────────────────────────────────────────────────────────

def test_caminho_waiting_human_sem_callback(tmp_path: Path) -> None:
    pipe, build = _make_pipe(tmp_path, {"verdict": "BUILD", "confidence": 0.9, "conditions": []})
    state = asyncio.run(pipe.run(ValidateAndBuildRequest(idea_text="ideia")))
    assert state.status == MissionStatus.WAITING_HUMAN
    assert build.called is False


def test_caminho_humano_rejeita(tmp_path: Path) -> None:
    pipe, build = _make_pipe(tmp_path, {"verdict": "BUILD", "confidence": 0.9, "conditions": []})
    state = asyncio.run(pipe.run(
        ValidateAndBuildRequest(idea_text="ideia"), confirm=lambda d: False))
    assert state.status == MissionStatus.COMPLETED
    assert build.called is False
    assert state.mode_payload["build_skipped_reason"] == "Rejeitado pelo fundador."


def test_caminho_humano_aprova_builda(tmp_path: Path) -> None:
    pipe, build = _make_pipe(tmp_path, {"verdict": "BUILD", "confidence": 0.9, "conditions": []})
    state = asyncio.run(pipe.run(
        ValidateAndBuildRequest(idea_text="ideia"), confirm=lambda d: True))
    assert state.status == MissionStatus.COMPLETED
    assert build.called is True
    assert build.seed is not None  # BuildSeed extraído e repassado


# ─────────────────────────────────────────────────────────────
# Caminho 3 — auto-build (sem confirmação) -> build
# ─────────────────────────────────────────────────────────────

def test_caminho_auto_build(tmp_path: Path) -> None:
    pipe, build = _make_pipe(tmp_path, {"verdict": "BUILD", "confidence": 0.9, "conditions": []})
    state = asyncio.run(pipe.run(ValidateAndBuildRequest(
        idea_text="ideia", require_human_confirmation=False, min_confidence_to_autobuild=0.75)))
    assert state.status == MissionStatus.COMPLETED
    assert build.called is True
    gate = BuildGateDecision(**state.mode_payload["gate"])
    assert gate.should_build is True
    assert gate.needs_human_confirmation is False

    mid = state.mission_id
    composite = (tmp_path / mid / "composite_report.md").read_text(encoding="utf-8")
    assert "## Build" in composite and "COMPLETED" in composite


def test_no_build_forca_encerramento(tmp_path: Path) -> None:
    pipe, build = _make_pipe(tmp_path, {"verdict": "BUILD", "confidence": 0.9, "conditions": []})
    state = asyncio.run(pipe.run(
        ValidateAndBuildRequest(idea_text="ideia", require_human_confirmation=False),
        no_build=True))
    assert state.status == MissionStatus.COMPLETED
    assert build.called is False