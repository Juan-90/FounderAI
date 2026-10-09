"""
Testes unitários do ImproveDiagnoser (v5.4.0).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.core.improve.diagnoser import ImproveDiagnoser
from backend.domain.improve import ImproveDiagnosis
from backend.domain.memory import (
    ArtifactKind,
    ArtifactVersion,
    MemoryEvent,
    MemoryEventType,
    MemoryLearning,
    ProjectMemory,
)
from typing import Literal

LearningSource = Literal[
    "qa_failure", "validation_risk", "human_feedback", "self_audit", "other"
]


def _now(offset_minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)


def _memory(**kw) -> ProjectMemory:
    base = {
        "project_id": "p-1",
        "name": "EcoTrack",
        "created_at": _now(),
        "updated_at": _now(),
    }
    base.update(kw)
    return ProjectMemory(**base)


def _event(etype: MemoryEventType, message: str, offset: int = 0) -> MemoryEvent:
    return MemoryEvent(
        event_id=f"ev-{offset}-{etype.value}", type=etype, message=message,
        created_at=_now(offset),
    )


def _learning(text: str, source: LearningSource, offset: int = 0) -> MemoryLearning:
    return MemoryLearning(
        learning_id=f"ln-{offset}-{source}", text=text, source=source,
        created_at=_now(offset),
    )


def _version(kind: ArtifactKind, path: str, offset: int = 0) -> ArtifactVersion:
    return ArtifactVersion(
        version_id=f"v-{offset}-{kind.value}", kind=kind, path=path,
        created_at=_now(offset),
    )


def test_diagnose_falhas_recorrentes_e_citacoes() -> None:
    mem = _memory(
        events=[
            _event(MemoryEventType.BUILD_FAILED, "Build finalizado (FAILED)", 1),
            _event(MemoryEventType.BUILD_FAILED, "Build finalizado (FAILED)", 5),
        ],
        learnings=[
            _learning("Testes falharam por timeout de 30s", "qa_failure", 2),
            _learning("Concorrência forte no nicho", "validation_risk", 3),
        ],
        artifact_versions=[
            _version(ArtifactKind.REQUIREMENTS, "art/req.md", 1),
            _version(ArtifactKind.TEST_REPORT, "art/report.md", 4),
        ],
    )
    d = ImproveDiagnoser().diagnose(mem)
    assert isinstance(d, ImproveDiagnosis)
    assert d.risk_level == "high"  # 2 falhas
    assert any("recorrente" in i and "2x" in i for i in d.top_issues)
    # citação explícita de learnings e artefatos
    assert "Testes falharam por timeout de 30s" in d.leveraged_learnings
    assert "Concorrência forte no nicho" in d.leveraged_learnings
    assert "art/req.md" in d.leveraged_artifacts
    assert "art/report.md" in d.leveraged_artifacts
    assert "EcoTrack" in d.summary


def test_diagnose_risco_medium_uma_falha() -> None:
    mem = _memory(events=[_event(MemoryEventType.BUILD_FAILED, "falhou", 1)])
    d = ImproveDiagnoser().diagnose(mem)
    assert d.risk_level == "medium"


def test_diagnose_risco_low_sem_historico() -> None:
    d = ImproveDiagnoser().diagnose(_memory())
    assert d.risk_level == "low"
    assert d.leveraged_learnings == []
    assert d.leveraged_artifacts == []
    assert any("Sem artefatos" in i for i in d.top_issues)


def test_diagnose_escalated_risco_high() -> None:
    mem = _memory(events=[_event(MemoryEventType.ESCALATED, "escalou", 1)])
    d = ImproveDiagnoser().diagnose(mem)
    assert d.risk_level == "high"


def test_diagnose_gap_de_goal() -> None:
    mem = _memory(current_goal="Lançar MVP")
    d = ImproveDiagnoser().diagnose(mem, goal="Reduzir custos de infra")
    assert any("Gap de goal" in i for i in d.top_issues)


def test_diagnose_sem_gap_quando_goal_igual() -> None:
    mem = _memory(current_goal="Lançar MVP")
    d = ImproveDiagnoser().diagnose(mem, goal="lançar mvp")
    assert not any("Gap de goal" in i for i in d.top_issues)


def test_diagnose_usa_versao_mais_recente_do_artefato() -> None:
    mem = _memory(artifact_versions=[
        _version(ArtifactKind.REQUIREMENTS, "art/req-v1.md", 1),
        _version(ArtifactKind.REQUIREMENTS, "art/req-v2.md", 9),
    ])
    d = ImproveDiagnoser().diagnose(mem)
    assert "art/req-v2.md" in d.leveraged_artifacts
    assert "art/req-v1.md" not in d.leveraged_artifacts
