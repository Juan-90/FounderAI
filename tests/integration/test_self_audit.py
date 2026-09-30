"""
Teste de integração do SelfAuditPipeline (v4.6.0) — sem LLM/Docker.

Config com PRIMARY/FALLBACK=local e GROQ sem chave força o AdversarialAuditor
a degradar (heurísticas locais), mantendo o teste determinístico.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from backend.core.config import Settings
from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.models import Artifact, MissionState
from backend.self_audit.pipeline import SelfAuditPipeline
from backend.self_audit.schemas import SelfAuditRequest


def _art(names):
    return [Artifact(name=n, type="x", path=n, content="c") for n in names]


class FakeBuild:
    async def run(self, intent, project_name="App", on_stage=None,
                  mission_id=None, seed=None):
        return MissionState(
            mission_id=mission_id or "mb", project_id="p", mode=ProjectMode.BUILD,
            status=MissionStatus.COMPLETED, current_stage="report",
            mode_payload={"tdd_summary": "ok"},
            artifacts=_art(["requirements.md", "architecture.md", "report.md"]),
        )


class FakeValidate:
    async def run(self, request, on_stage=None, mission_id=None):
        return MissionState(
            mission_id=mission_id or "mv", project_id="p", mode=ProjectMode.VALIDATE,
            status=MissionStatus.COMPLETED, current_stage="report",
            mode_payload={"recommendation": {"verdict": "BUILD", "confidence": 0.8}},
            artifacts=_art(["idea_profile.json", "validation_report.md"]),
        )


class FakeVab:
    async def run(self, request, confirm=None, no_build=False):
        return MissionState(
            mission_id="mz", project_id="p", mode=ProjectMode.VALIDATE_AND_BUILD,
            status=MissionStatus.COMPLETED, current_stage="report",
            mode_payload={"gate": {"should_build": True, "source_verdict": "BUILD"},
                          "recommendation": {"verdict": "BUILD"}},
            artifacts=_art(["gate_decision.json", "composite_report.md"]),
        )


def _cfg() -> Settings:
    return Settings(
        PRIMARY_PROVIDER="local", FALLBACK_PROVIDER="local", GROQ_API_KEY="",
    )


def test_self_audit_executa_calcula_e_persiste(tmp_path: Path) -> None:
    pipe = SelfAuditPipeline(
        config=_cfg(), root_base=tmp_path,
        build_factory=lambda ptype: FakeBuild(),
        validate_pipeline=FakeValidate(), vab_pipeline=FakeVab(),
    )
    sc = asyncio.run(pipe.run(SelfAuditRequest(adversarial_enabled=True)))

    assert sc.total_missions > 0
    assert sc.success_rate == 1.0
    assert sc.overall_verdict == "HEALTHY"
    assert sc.objective_checks_passed == sc.objective_checks_total

    audit_dir = pipe.last_audit_dir
    assert audit_dir is not None and audit_dir.exists()
    assert (audit_dir / "scorecard.json").exists()
    assert (audit_dir / "adversarial_review.json").exists()
    assert (audit_dir / "self_audit_report.md").exists()


def test_self_audit_flags_excluem_modos(tmp_path: Path) -> None:
    pipe = SelfAuditPipeline(
        config=_cfg(), root_base=tmp_path,
        build_factory=lambda ptype: FakeBuild(),
        validate_pipeline=FakeValidate(), vab_pipeline=FakeVab(),
    )
    sc = asyncio.run(pipe.run(SelfAuditRequest(
        include_validate=False, include_validate_and_build=False,
        adversarial_enabled=False,
    )))
    assert sc.validate_success_rate is None
    assert sc.vab_success_rate is None
    assert sc.build_success_rate == 1.0