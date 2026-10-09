"""
E2E: feedback humano (OBSERVE) → IMPROVE (v5.5.0).

Projeto memorizado → FeedbackService grava OBSERVED + learning human_feedback
→ IMPROVE diagnostica incluindo a observação em leveraged_learnings/top_issues
→ plano/patch aborda a observação → memória evolui (IMPROVED) preservando histórico.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from backend.core.config import Settings
from backend.core.improve.patcher import ImprovePatcher, ImproveQualityRunner
from backend.core.improve.pipeline import ImprovePipeline
from backend.core.memory.feedback_service import FeedbackService
from backend.domain.feedback import ProjectFeedbackRequest
from backend.domain.improve import ImprovePlanItem, ImproveRequest
from backend.domain.memory import ArtifactKind, MemoryEventType
from backend.domain.memory_store import DiskProjectMemoryStore

NOTE = "UX de agendamento apresenta erro em horas ímpares"


def _cfg(tmp_path: Path) -> Settings:
    return Settings(
        PROJECT_MEMORY_DIR=str(tmp_path / "projects"),
        IMPROVE_MODE_ENABLED=True,
        IMPROVE_MAX_FILES_TOUCHED=8,
        OBSERVE_FEEDBACK_ENABLED=True,
        OBSERVE_FEEDBACK_MAX_NOTE_CHARS=2000,
    )


class _Gen:
    def __init__(self, proposal: dict[str, str]) -> None:
        self._proposal = proposal

    def generate(self, item: ImprovePlanItem, bundle: dict[str, str]) -> dict[str, str]:
        return self._proposal


class _Gate:
    def __init__(self, passed: bool = True) -> None:
        self.passed = passed

    def run(self, files: dict[str, str]) -> Any:
        return SimpleNamespace(passed=self.passed, summary="gate")


class _TDD:
    def __init__(self, results: list[bool]) -> None:
        self._results = results
        self.calls = 0

    async def run(self, request: Any) -> Any:
        self.calls += 1
        ok = self._results[min(self.calls - 1, len(self._results) - 1)]
        return SimpleNamespace(success=ok, escalated=False, summary="tdd")


def test_feedback_to_improve_e2e(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="BarbeariaAgenda")

    # Bundle inicial p/ o improve patchar
    bundle_file = tmp_path / "code_bundle.json"
    bundle_file.write_text(json.dumps({
        "main.py": "def agenda(h): return h",
        "test_main.py": "def test_agenda(): assert agenda(1) == 1",
    }), encoding="utf-8")
    store.add_artifact_version(mem.project_id, ArtifactKind.CODE_BUNDLE, str(bundle_file))

    # 2 — feedback humano via FeedbackService
    svc = FeedbackService(config=cfg)
    res = svc.record_feedback(store, ProjectFeedbackRequest(
        project_id=mem.project_id, rating=2, note=NOTE, tags=["ux", "bug"],
    ))
    assert res.accepted is True

    # 3 — OBSERVED + learning human_feedback gravados
    m = store.get(mem.project_id)
    assert m is not None
    assert any(e.type == MemoryEventType.OBSERVED for e in m.events)
    assert any(l.source == "human_feedback" and NOTE in l.text for l in m.learnings)

    # 4 — IMPROVE acionado
    pipe = ImprovePipeline(
        store=store, config=cfg,
        patcher=ImprovePatcher(generator=_Gen({"main.py": "def agenda(h): return fix(h)"})),
        quality_runner=ImproveQualityRunner(static_gate=_Gate(True), tdd_loop=_TDD([True])),
    )
    result = asyncio.run(pipe.execute(ImproveRequest(
        project_id=mem.project_id, require_human_confirmation=False, auto_apply=True,
    )))

    # 5 — diagnoser detectou a observação humana
    assert any(NOTE in l for l in result.diagnosis.leveraged_learnings)
    assert any("Observação humana" in i and NOTE in i for i in result.diagnosis.top_issues)

    # 6 — plano/patch aborda a observação
    assert any("horas ímpares" in it.title.lower() or "observação humana" in it.title.lower()
               for it in result.plan.items)
    assert result.success is True
    assert result.changed_files == ["main.py"]

    # Memória evoluiu preservando histórico
    m2 = store.get(mem.project_id)
    assert m2 is not None
    types = [e.type for e in m2.events]
    assert MemoryEventType.OBSERVED in types
    assert MemoryEventType.IMPROVED in types