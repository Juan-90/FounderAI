"""
Testes do FeedbackService + prioridade de human_feedback no compiler (v5.5.0).
"""

from __future__ import annotations

from pathlib import Path

from backend.core.config import Settings
from backend.core.memory.compiler import MemoryContextCompiler
from backend.core.memory.feedback_service import FeedbackService
from backend.domain.feedback import ProjectFeedbackRequest
from backend.domain.memory import MemoryEventType
from backend.domain.memory_store import DiskProjectMemoryStore


def _cfg(tmp_path: Path, **overrides) -> Settings:
    base = {
        "PROJECT_MEMORY_DIR": str(tmp_path / "projects"),
        "OBSERVE_FEEDBACK_ENABLED": True,
        "OBSERVE_FEEDBACK_MAX_NOTE_CHARS": 2000,
    }
    base.update(overrides)
    return Settings(**base)


def test_record_feedback_grava_learning_e_evento(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    svc = FeedbackService(config=_cfg(tmp_path))

    res = svc.record_feedback(store, ProjectFeedbackRequest(
        project_id=mem.project_id, rating=4, note="MVP ótimo mas lento",
        tags=["ux", "perf"],
    ))
    assert res.accepted is True
    assert res.learning_id and res.event_id

    m = store.get(mem.project_id)
    assert m is not None
    assert any(
        l.source == "human_feedback" and "rating=4" in l.text and "MVP ótimo" in l.text
        for l in m.learnings
    )
    assert any(e.type == MemoryEventType.OBSERVED for e in m.events)

    raw = (tmp_path / "projects" / mem.project_id / "memory.json").read_text(encoding="utf-8")
    assert "human_feedback" in raw and "observed" in raw


def test_rejeita_feedback_sem_rating_e_sem_note(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    svc = FeedbackService(config=_cfg(tmp_path))

    res = svc.record_feedback(store, ProjectFeedbackRequest(project_id=mem.project_id))
    assert res.accepted is False
    assert res.learning_id is None and res.event_id is None

    m = store.get(mem.project_id)
    assert m is not None
    assert m.learnings == []
    assert m.events == []


def test_learning_human_feedback_tem_prioridade_no_contexto(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    svc = FeedbackService(config=_cfg(tmp_path))
    svc.record_feedback(store, ProjectFeedbackRequest(
        project_id=mem.project_id, rating=5, note="priorizar mobile",
    ))
    # Ruído: muitos learnings de QA depois do feedback
    for i in range(5):
        store.add_learning(mem.project_id, f"qa ruido {i}", "qa_failure")

    compiler = MemoryContextCompiler(store=store, config=_cfg(tmp_path))
    block = compiler.compile(mem.project_id)
    # human_feedback priorizado mesmo com ruído de QA
    assert "priorizar mobile" in block


def test_trunca_note_acima_do_limite(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    svc = FeedbackService(config=_cfg(tmp_path, OBSERVE_FEEDBACK_MAX_NOTE_CHARS=20))

    svc.record_feedback(store, ProjectFeedbackRequest(
        project_id=mem.project_id, rating=3, note="x" * 100,
    ))
    m = store.get(mem.project_id)
    assert m is not None
    learning = m.learnings[0]
    assert "x" * 20 in learning.text
    assert "x" * 21 not in learning.text