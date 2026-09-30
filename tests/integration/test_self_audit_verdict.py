"""
Garantias SELF-AUDIT (v5.0.0 GA):
  • Ecossistema saudável -> HEALTHY/DEGRADED (nunca CRITICAL).
  • Falhas de infra (provedor/modelo) NÃO zeram para CRITICAL.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from backend.core.config import Settings
from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.models import Artifact, MissionState
from backend.self_audit.pipeline import SelfAuditPipeline
from backend.self_audit.schemas import (
    AdversarialReview,
    AuditMissionResult,
    SelfAuditRequest,
)
from backend.self_audit.scorecard import ScorecardSynthesizer


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
            mode_payload={"gate": {"should_build": True, "source_verdict": "BUILD"}},
            artifacts=_art(["gate_decision.json", "composite_report.md"]),
        )


def _cfg() -> Settings:
    return Settings(PRIMARY_PROVIDER="local", FALLBACK_PROVIDER="local", GROQ_API_KEY="")


def test_self_audit_veredito_nunca_critical_quando_tudo_passa(tmp_path: Path) -> None:
    pipe = SelfAuditPipeline(
        config=_cfg(), root_base=tmp_path,
        build_factory=lambda ptype: FakeBuild(),
        validate_pipeline=FakeValidate(), vab_pipeline=FakeVab(),
    )
    sc = asyncio.run(pipe.run(SelfAuditRequest(adversarial_enabled=True)))
    assert sc.success_rate == 1.0
    assert sc.overall_verdict in ("HEALTHY", "DEGRADED")
    assert sc.overall_verdict != "CRITICAL"


def test_falhas_de_infra_nao_zeram_para_critical() -> None:
    results = [
        AuditMissionResult(mission_name="VAB", mode=ProjectMode.VALIDATE_AND_BUILD,
                           success=True, duration_ms=1, failure_class=None),
        AuditMissionResult(mission_name="Build", mode=ProjectMode.BUILD,
                           success=False, duration_ms=1,
                           error="[TIMEOUT] local excedeu 180s", failure_class="infra"),
        AuditMissionResult(mission_name="Validate", mode=ProjectMode.VALIDATE,
                           success=False, duration_ms=1,
                           error="LLMProviderError: [INVALID_JSON] truncado", failure_class="infra"),
    ]
    sc = ScorecardSynthesizer().synthesize(results, AdversarialReview())
    assert sc.infra_failures == 2
    assert sc.overall_verdict == "DEGRADED"  # infra estressada, logica ok


def test_falha_de_logica_pode_ser_critical() -> None:
    # Falhas de lógica (ecossistema) abaixo de 0.60 ainda são CRITICAL (honesto)
    results = [
        AuditMissionResult(mission_name="A", mode=ProjectMode.BUILD,
                           success=True, duration_ms=1, failure_class=None),
        AuditMissionResult(mission_name="B", mode=ProjectMode.VALIDATE,
                           success=False, duration_ms=1,
                           error="check de artefatos falhou", failure_class="logic"),
        AuditMissionResult(mission_name="C", mode=ProjectMode.VALIDATE_AND_BUILD,
                           success=False, duration_ms=1,
                           error="gate inválido", failure_class="logic"),
    ]
    sc = ScorecardSynthesizer().synthesize(results, AdversarialReview())
    assert sc.overall_verdict == "CRITICAL"