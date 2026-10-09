"""
E2E de continuidade do modo IMPROVE (v5.4.0).

BUILD falho registrado na memória -> IMPROVE identifica a falha passada,
planeja, patcha, valida no TDD e grava IMPROVED, preservando o histórico.
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
from backend.domain.improve import ImprovePlanItem, ImproveRequest
from backend.domain.memory import ArtifactKind, MemoryEventType
from backend.domain.memory_store import DiskProjectMemoryStore


def _cfg(tmp_path: Path) -> Settings:
    return Settings(
        PROJECT_MEMORY_DIR=str(tmp_path / "projects"),
        BUILD_ARTIFACTS_DIR=str(tmp_path / "build"),
        IMPROVE_MODE_ENABLED=True,
        IMPROVE_MAX_FILES_TOUCHED=8,
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


def test_improve_continuidade_e2e(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="EcoTrack")

    # 1 — BUILD com falha/insuficiência simulada registrada na memória
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    bundle_file = bundle_dir / "code_bundle.json"
    bundle_file.write_text(json.dumps({
        "main.py": "def f(): return 1  # bugado",
        "test_main.py": "def test_f(): assert f() == 1",
    }), encoding="utf-8")
    store.append_event(mem.project_id, MemoryEventType.BUILD_FAILED,
                       "Build finalizado (FAILED)", mission_id="mb-1")
    store.add_learning(mem.project_id, "Testes falharam por asserção incorreta",
                       "qa_failure", mission_id="mb-1")
    store.add_artifact_version(mem.project_id, ArtifactKind.CODE_BUNDLE,
                               str(bundle_file), mission_id="mb-1")

    # 2 — IMPROVE acionado sobre o project_id
    pipe = ImprovePipeline(
        store=store, config=cfg,
        patcher=ImprovePatcher(generator=_Gen({"main.py": "def f(): return 2  # melhorado"})),
        quality_runner=ImproveQualityRunner(static_gate=_Gate(True), tdd_loop=_TDD([True])),
    )
    result = asyncio.run(pipe.execute(ImproveRequest(
        project_id=mem.project_id, require_human_confirmation=False, auto_apply=True,
    )))

    # 3 — diagnoser identificou a falha passada; planner+patcher+TDD ok
    assert result.success is True
    assert any("QA:" in i or "Falha" in i for i in result.diagnosis.top_issues)
    assert any("asserção incorreta" in l for l in result.diagnosis.leveraged_learnings)
    assert result.changed_files == ["main.py"]

    # 4 — memória evoluiu E preservou histórico
    mem2 = store.get(mem.project_id)
    assert mem2 is not None
    types = [e.type for e in mem2.events]
    assert MemoryEventType.BUILD_FAILED in types   # histórico preservado
    assert MemoryEventType.IMPROVED in types       # evolução
    kinds = [v.kind for v in mem2.artifact_versions]
    assert kinds.count(ArtifactKind.CODE_BUNDLE) == 2  # bundle antigo + novo
    assert any(l.source == "other" for l in mem2.learnings)