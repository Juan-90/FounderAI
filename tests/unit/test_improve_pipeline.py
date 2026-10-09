"""
Testes do ImprovePipeline (v5.4.0) — fluxo simulado (sem LLM/Docker).
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
from backend.domain.improve import ImprovePlanItem
from backend.domain.memory import MemoryEventType
from backend.domain.memory_store import DiskProjectMemoryStore


def _cfg(tmp_path: Path) -> Settings:
    return Settings(PROJECT_MEMORY_DIR=str(tmp_path / "projects"))


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


def _pipe(tmp_path: Path, store: DiskProjectMemoryStore, tdd: list[bool],
          gate: bool = True) -> ImprovePipeline:
    return ImprovePipeline(
        store=store, config=_cfg(tmp_path),
        patcher=ImprovePatcher(generator=_Gen({"main.py": "novo"})),
        quality_runner=ImproveQualityRunner(static_gate=_Gate(gate), tdd_loop=_TDD(tdd)),
        initial_bundle={"main.py": "velho", "test_main.py": "t"},
    )


def test_fluxo_completo_aplica_e_grava_memoria(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")

    from backend.domain.improve import ImproveRequest
    pipe = _pipe(tmp_path, store, tdd=[True])
    result = asyncio.run(pipe.execute(ImproveRequest(
        project_id=mem.project_id, require_human_confirmation=False, auto_apply=True,
    )))

    assert result.success is True
    assert result.waiting_human is False
    assert result.changed_files == ["main.py"]
    assert result.report_path is not None
    assert Path(result.report_path).exists()

    mem2 = store.get(mem.project_id)
    assert mem2 is not None
    assert any(e.type == MemoryEventType.IMPROVED for e in mem2.events)
    assert any(l.source == "other" for l in mem2.learnings)
    kinds = {v.kind for v in mem2.artifact_versions}
    from backend.domain.memory import ArtifactKind
    assert ArtifactKind.CODE_BUNDLE in kinds
    assert ArtifactKind.COMPOSITE_REPORT in kinds
    assert ArtifactKind.TEST_REPORT in kinds

    # memory.json atualizado em disco
    raw = (tmp_path / "projects" / mem.project_id / "memory.json").read_text(encoding="utf-8")
    assert "improved" in raw


def test_interrompe_em_waiting_human(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")

    from backend.domain.improve import ImproveRequest
    pipe = _pipe(tmp_path, store, tdd=[True])
    result = asyncio.run(pipe.execute(ImproveRequest(
        project_id=mem.project_id, require_human_confirmation=True, auto_apply=False,
    )))

    assert result.waiting_human is True
    assert result.success is False
    assert result.changed_files == []
    assert result.report_path is not None  # rascunho do plano salvo
    assert "NÃO APLICADO" in Path(result.report_path).read_text(encoding="utf-8")

    mem2 = store.get(mem.project_id)
    assert mem2 is not None
    assert not any(e.type == MemoryEventType.IMPROVED for e in mem2.events)


def test_falha_escalada_grava_evento_e_learning(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")

    from backend.domain.improve import ImproveRequest
    pipe = _pipe(tmp_path, store, tdd=[False])  # sempre falha -> escalated
    result = asyncio.run(pipe.execute(ImproveRequest(
        project_id=mem.project_id, require_human_confirmation=False, auto_apply=True,
    )))

    assert result.success is False
    assert result.escalated is True

    mem2 = store.get(mem.project_id)
    assert mem2 is not None
    assert any(e.type == MemoryEventType.ESCALATED for e in mem2.events)
    assert any(l.source == "qa_failure" and "Falha na melhoria" in l.text for l in mem2.learnings)


def test_projeto_inexistente_retorna_falha_graciosa(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    pipe = _pipe(tmp_path, store, tdd=[True])

    from backend.domain.improve import ImproveRequest
    result = asyncio.run(pipe.execute(ImproveRequest(project_id="nao-existe")))
    assert result.success is False
    assert "não encontrado" in result.summary