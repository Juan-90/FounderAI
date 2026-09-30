"""
Testes unitários do AuditRunner + objective checks (v4.6.0). Sem LLM/Docker.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.models import Artifact, MissionState
from backend.self_audit.canonical_pack import select_missions
from backend.self_audit.runner import AuditRunner
from backend.self_audit.schemas import (
    AdversarialReview,
    SelfAuditRequest,
)


def _art(names: list[str]) -> list[Artifact]:
    return [Artifact(name=n, type="x", path=n, content="c") for n in names]


class FakeBuild:
    def __init__(self, status=MissionStatus.COMPLETED,
                 names=("requirements.md", "architecture.md", "report.md")):
        self.status = status
        self.names = list(names)

    async def run(self, intent, project_name="App", on_stage=None,
                  mission_id=None, seed=None) -> MissionState:
        return MissionState(
            mission_id=mission_id or "mb", project_id="p", mode=ProjectMode.BUILD,
            status=self.status, current_stage="report",
            mode_payload={"tdd_summary": "ok"}, artifacts=_art(self.names),
        )


class FakeValidate:
    def __init__(self, verdict="BUILD"):
        self.verdict = verdict

    async def run(self, request, on_stage=None, mission_id=None) -> MissionState:
        return MissionState(
            mission_id=mission_id or "mv", project_id="p", mode=ProjectMode.VALIDATE,
            status=MissionStatus.COMPLETED, current_stage="report",
            mode_payload={"recommendation": {"verdict": self.verdict, "confidence": 0.8}},
            artifacts=_art(["idea_profile.json", "validation_report.md"]),
        )


class FakeVab:
    async def run(self, request, confirm=None, no_build=False) -> MissionState:
        return MissionState(
            mission_id="mz", project_id="p", mode=ProjectMode.VALIDATE_AND_BUILD,
            status=MissionStatus.COMPLETED, current_stage="report",
            mode_payload={"gate": {"should_build": True, "source_verdict": "BUILD"},
                          "recommendation": {"verdict": "BUILD"}},
            artifacts=_art(["gate_decision.json", "composite_report.md"]),
        )


class FakeReviewer:
    def __init__(self, review: AdversarialReview):
        self.review_obj = review

    async def review(self, context: dict[str, Any]) -> AdversarialReview:
        return self.review_obj


def _runner(tmp_path: Path, build=None, validate=None, vab=None, reviewer=None) -> AuditRunner:
    return AuditRunner(
        root=tmp_path,
        build_factory=lambda ptype: build or FakeBuild(),
        validate_pipeline=validate or FakeValidate(),
        vab_pipeline=vab or FakeVab(),
        adversarial_reviewer=reviewer,
    )


# ─────────────────────────────────────────────────────────────
# Seleção do pack
# ─────────────────────────────────────────────────────────────

def test_select_respeita_include_e_max() -> None:
    req = SelfAuditRequest(include_build=True, include_validate=False,
                           include_validate_and_build=False, max_missions_per_mode=1)
    missions = select_missions(req)
    assert len(missions) == 1
    assert missions[0].mode == ProjectMode.BUILD


def test_select_todos_os_modos() -> None:
    missions = select_missions(SelfAuditRequest(max_missions_per_mode=3))
    modes = {m.mode for m in missions}
    assert modes == {ProjectMode.BUILD, ProjectMode.VALIDATE, ProjectMode.VALIDATE_AND_BUILD}


# ─────────────────────────────────────────────────────────────
# Objective checks
# ─────────────────────────────────────────────────────────────

def test_objective_checks_passam_sem_root(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    mission = select_missions(SelfAuditRequest(max_missions_per_mode=1))[0]
    state = asyncio.run(runner._run_mission(mission))
    checks = runner._objective_checks(mission, state, root=None)
    assert all(checks.values())


def test_objective_checks_disk(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    mission = select_missions(SelfAuditRequest(max_missions_per_mode=1))[0]
    state = asyncio.run(runner._run_mission(mission))
    mdir = tmp_path / state.mission_id
    mdir.mkdir(parents=True)
    for n in mission.required_artifacts:
        (mdir / n).write_text("conteudo", encoding="utf-8")
    checks = runner._objective_checks(mission, state, root=tmp_path)
    assert checks["artifacts_present"] is True
    assert checks["report_not_empty"] is True

    (mdir / mission.report_file).unlink()
    checks2 = runner._objective_checks(mission, state, root=tmp_path)
    assert checks2["report_not_empty"] is False


def test_verdict_invalido_falha(tmp_path: Path) -> None:
    runner = _runner(tmp_path, validate=FakeValidate(verdict="MAYBE"))
    req = SelfAuditRequest(include_build=False, include_validate_and_build=False,
                           max_missions_per_mode=1)
    mission = select_missions(req)[0]
    state = asyncio.run(runner._run_mission(mission))
    checks = runner._objective_checks(mission, state, root=None)
    assert checks["verdict_valid"] is False


# ─────────────────────────────────────────────────────────────
# Scorecard
# ─────────────────────────────────────────────────────────────

def test_scorecard_healthy(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    sc = asyncio.run(runner.run(SelfAuditRequest(adversarial_enabled=False)))
    assert sc.overall_verdict == "HEALTHY"
    assert sc.success_rate == 1.0
    assert sc.total_missions > 0


def test_scorecard_degraded_ou_critical_quando_build_falha(tmp_path: Path) -> None:
    runner = _runner(tmp_path, build=FakeBuild(status=MissionStatus.FAILED))
    sc = asyncio.run(runner.run(SelfAuditRequest(adversarial_enabled=False)))
    assert sc.build_success_rate == 0.0
    assert sc.overall_verdict in ("DEGRADED", "CRITICAL")


def test_adversarial_findings_no_scorecard(tmp_path: Path) -> None:
    review = AdversarialReview(findings=["overclaim X", "crit Y"],
                               severity_counts={"critical": 1}, overclaim_detected=True,
                               consistency_score=0.5)
    runner = _runner(tmp_path, reviewer=FakeReviewer(review))
    sc = asyncio.run(runner.run(SelfAuditRequest(adversarial_enabled=True)))
    assert sc.adversarial_findings == ["overclaim X", "crit Y"]
    assert sc.critical_findings == ["overclaim X"]
    assert sc.overall_verdict == "CRITICAL"  # overclaim + critical


def test_persist_scorecard_e_report(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    asyncio.run(runner.run(SelfAuditRequest(adversarial_enabled=False)))
    assert (tmp_path / "scorecard.json").exists()
    assert (tmp_path / "self_audit_report.md").exists()