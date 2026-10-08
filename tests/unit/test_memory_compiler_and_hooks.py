"""
Testes do MemoryContextCompiler + hooks de pipeline (v5.3.0).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.memory_compiler import MemoryContextCompiler
from backend.core.memory_hooks import (
    attach_memory_to_intent,
    record_build_completion,
    record_validate_completion,
    resolve_memory,
)
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus
from backend.domain.memory import ArtifactKind, MemoryEventType
from backend.domain.memory_store import DiskProjectMemoryStore
from backend.domain.models import MissionState
from backend.validate.pipeline import ValidatePipeline
from backend.validate.schemas import ValidateRequest


def _cfg(tmp_path: Path) -> Settings:
    return Settings(
        VALIDATE_ARTIFACTS_DIR=str(tmp_path / "validate"),
        BUILD_ARTIFACTS_DIR=str(tmp_path / "build"),
        PROJECT_MEMORY_DIR=str(tmp_path / "projects"),
        PROJECT_MEMORY_CONTEXT_MAX_CHARS=8000,
    )


class FakeValidateClient:
    def __init__(self) -> None:
        self._queue = [
            {"summary": "App", "assumptions": [], "gaps": [],
             "clarified_fields": {"name": "X", "target_audience": "PMEs",
                                  "problem": "dor", "solution": "web",
                                  "business_model": "SaaS", "constraints": "t"}},
            {"pain_description": "dor", "pain_severity": "high",
             "audience_segment": "PMEs", "evidence": [], "inferences": [],
             "market_size_hint": "R$1M"},
            {"direct_competitors": [], "indirect_alternatives": [],
             "status_quo": "papel", "our_differentiators": []},
            {"complexity": "medium", "data_requirements": [], "ai_risks": [],
             "technical_mvp_outline": "web", "effort_weeks_estimate": 6},
            {"regulatory_risks": [], "false_positive_risks": [],
             "hidden_costs": [], "reasons_to_kill": ["concorrência"],
             "skeptic_score": 6},
            {"experiments": [
                {"hypothesis": "H1", "method": "m1", "metric": "x1",
                 "go_threshold": "t1", "estimated_cost_days": 1},
                {"hypothesis": "H2", "method": "m2", "metric": "x2",
                 "go_threshold": "t2", "estimated_cost_days": 2},
                {"hypothesis": "H3", "method": "m3", "metric": "x3",
                 "go_threshold": "t3", "estimated_cost_days": 3},
            ]},
            {"verdict": "INVESTIGATE", "confidence": 0.7, "rationale": "r",
             "conditions": [], "final_report": "# Report"},
        ]

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        return self._queue.pop(0)


# ─────────────────────────────────────────────────────────────
# Compiler
# ─────────────────────────────────────────────────────────────

def test_compiler_respeita_limite_de_chars(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    for i in range(30):
        store.add_decision(mem.project_id, f"Decisão {i}", "r" * 80)
        store.add_learning(mem.project_id, f"Learning {i} " + "x" * 80, "qa_failure")

    compiler = MemoryContextCompiler(store=store, config=_cfg(tmp_path))
    out = compiler.compile(mem.project_id, max_chars=400)
    assert len(out) <= 400
    assert out  # não vazio


def test_compiler_prioriza_goal_e_decisoes(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    mem.current_goal = "Lançar MVP"
    store.save(mem)
    store.add_decision(mem.project_id, "Usar FastAPI", "performance")

    compiler = MemoryContextCompiler(store=store, config=_cfg(tmp_path))
    out = compiler.compile(mem.project_id)
    assert "## Memória do Projeto" in out
    assert "Lançar MVP" in out
    assert "Usar FastAPI" in out


def test_compiler_projeto_inexistente_retorna_vazio(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    compiler = MemoryContextCompiler(store=store, config=_cfg(tmp_path))
    assert compiler.compile("nao-existe") == ""


def test_attach_memory_to_intent(tmp_path: Path) -> None:
    out = attach_memory_to_intent("ideia base", "bloco")
    assert "ideia base" in out
    assert "--- MEMÓRIA DO PROJETO" in out
    assert "bloco" in out
    assert attach_memory_to_intent("ideia", "") == "ideia"


# ─────────────────────────────────────────────────────────────
# Hooks
# ─────────────────────────────────────────────────────────────

def _state(status: MissionStatus) -> MissionState:
    return MissionState(
        mission_id="m-1", project_id="p", mode=__import__(
            "backend.domain.enums", fromlist=["ProjectMode"]).ProjectMode.VALIDATE,
        status=status, current_stage="report",
        mode_payload={"contrarian_risk": {"reasons_to_kill": ["risco A"]},
                      "evidence_gaps": {"gaps": ["gap B"]}},
    )


def test_record_validate_completion_atualiza_memory(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    mission_dir = tmp_path / "mission"
    mission_dir.mkdir()
    (mission_dir / "validation_report.md").write_text("# R", encoding="utf-8")
    (mission_dir / "evidence").mkdir()
    (mission_dir / "evidence" / "evidence_graph.json").write_text("{}", encoding="utf-8")

    record_validate_completion(store, mem, _state(MissionStatus.COMPLETED), mission_dir)

    loaded = store.get(mem.project_id)
    assert loaded is not None
    assert any(e.type == MemoryEventType.VALIDATED for e in loaded.events)
    assert any(v.kind == ArtifactKind.VALIDATION_REPORT for v in loaded.artifact_versions)
    assert any(l.source == "validation_risk" for l in loaded.learnings)
    assert len(loaded.evidence_refs) == 1


def test_record_build_completion_eventos_e_versoes(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    mission_dir = tmp_path / "mission"
    mission_dir.mkdir()
    for f in ("requirements.md", "architecture.md", "report.md"):
        (mission_dir / f).write_text("# x", encoding="utf-8")

    record_build_completion(store, mem, _state(MissionStatus.COMPLETED), mission_dir)
    loaded = store.get(mem.project_id)
    assert loaded is not None
    assert any(e.type == MemoryEventType.BUILD_SUCCEEDED for e in loaded.events)
    kinds = {v.kind for v in loaded.artifact_versions}
    assert ArtifactKind.REQUIREMENTS in kinds
    assert ArtifactKind.ARCHITECTURE in kinds
    assert ArtifactKind.TEST_REPORT in kinds

    # Falha -> BUILD_FAILED
    record_build_completion(store, mem, _state(MissionStatus.FAILED), mission_dir)
    loaded2 = store.get(mem.project_id)
    assert loaded2 is not None
    assert any(e.type == MemoryEventType.BUILD_FAILED for e in loaded2.events)


# ─────────────────────────────────────────────────────────────
# Pipeline VALIDATE com memória
# ─────────────────────────────────────────────────────────────

def test_validate_pipeline_atualiza_memory_json(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    pipe = ValidatePipeline(
        client=FakeValidateClient(),
        artifact_manager=ArtifactManager(root=tmp_path / "validate"),
        config=cfg,
        memory_store=store,
        project_name="Projeto Memória",
    )
    state = asyncio.run(pipe.run(ValidateRequest(idea_text="ideia")))
    assert state.status == MissionStatus.COMPLETED

    projects = store.list_projects()
    assert len(projects) == 1
    mem = projects[0]
    assert mem.name == "Projeto Memória"
    assert any(e.type == MemoryEventType.VALIDATED for e in mem.events)
    assert any(v.kind == ArtifactKind.VALIDATION_REPORT for v in mem.artifact_versions)
    # memory.json persistido
    assert (tmp_path / "projects" / mem.project_id / "memory.json").exists()