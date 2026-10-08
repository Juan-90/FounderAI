"""
Continuidade E2E entre missões (v5.3.0).

Prova que:
  1. A 1ª missão (VALIDATE) cria a memória com evento VALIDATED + learnings.
  2. A 2ª missão no MESMO projeto recebe no contexto as decisões/aprendizados
     da 1ª (injeção verificada via prompt capturado).
  3. A timeline é estendida SEM sobrescrever artefatos/versões anteriores.
  4. Um BUILD subsequente (hook real) estende a mesma memória.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.memory_compiler import MemoryContextCompiler
from backend.core.memory_hooks import record_build_completion
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode
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


class RecordingFakeValidateClient:
    """FakeValidateClient que registra os prompts recebidos."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self._queue = [
            {"summary": "App", "assumptions": [], "gaps": [],
             "clarified_fields": {"name": "Eco", "target_audience": "PMEs",
                                  "problem": "carbono", "solution": "dash",
                                  "business_model": "SaaS", "constraints": "t"}},
            {"pain_description": "pegada de carbono", "pain_severity": "high",
             "audience_segment": "PMEs", "evidence": [], "inferences": [],
             "market_size_hint": "R$1M"},
            {"direct_competitors": [], "indirect_alternatives": [],
             "status_quo": "planilha", "our_differentiators": []},
            {"complexity": "medium", "data_requirements": [], "ai_risks": [],
             "technical_mvp_outline": "dash", "effort_weeks_estimate": 6},
            {"regulatory_risks": [], "false_positive_risks": [],
             "hidden_costs": [], "reasons_to_kill": ["concorrência forte XPTO"],
             "skeptic_score": 6},
            {"experiments": [
                {"hypothesis": "H1", "method": "m", "metric": "x",
                 "go_threshold": "t", "estimated_cost_days": 1},
                {"hypothesis": "H2", "method": "m", "metric": "x",
                 "go_threshold": "t", "estimated_cost_days": 2},
                {"hypothesis": "H3", "method": "m", "metric": "x",
                 "go_threshold": "t", "estimated_cost_days": 3},
            ]},
            {"verdict": "INVESTIGATE", "confidence": 0.7, "rationale": "r",
             "conditions": [], "final_report": "# Report"},
        ]

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        self.prompts.append(f"{system_prompt}\n{user_prompt}")
        return self._queue.pop(0)


def _pipe(tmp_path: Path, store: DiskProjectMemoryStore, client: Any) -> ValidatePipeline:
    return ValidatePipeline(
        client=client,
        artifact_manager=ArtifactManager(root=tmp_path / "validate"),
        config=_cfg(tmp_path),
        memory_store=store,
        project_name="EcoTrack-IA",
    )


def test_continuidade_entre_missoes(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")

    # Missão 1: VALIDATE
    client1 = RecordingFakeValidateClient()
    pipe1 = _pipe(tmp_path, store, client1)
    s1 = asyncio.run(pipe1.run(ValidateRequest(idea_text="Validar EcoTrack-IA")))
    assert s1.status == MissionStatus.COMPLETED
    mid1 = pipe1.last_mission_id
    assert mid1 is not None

    projects = store.list_projects()
    assert len(projects) == 1
    mem = projects[0]
    assert mem.name == "EcoTrack-IA"
    assert any(e.type == MemoryEventType.VALIDATED for e in mem.events)
    assert any(l.source == "validation_risk" and "XPTO" in l.text for l in mem.learnings)
    assert any(v.kind == ArtifactKind.VALIDATION_REPORT for v in mem.artifact_versions)

    # Missão 2: VALIDATE no MESMO projeto
    client2 = RecordingFakeValidateClient()
    pipe2 = _pipe(tmp_path, store, client2)
    s2 = asyncio.run(pipe2.run(ValidateRequest(idea_text="Segunda ideia EcoTrack")))
    assert s2.status == MissionStatus.COMPLETED

    # Injeção de contexto: a 2ª missão recebeu a memória da 1ª
    joined = "\n".join(client2.prompts)
    assert "MEMÓRIA DO PROJETO" in joined
    assert "XPTO" in joined

    # Timeline estendida, não sobrescrita
    mem2 = store.get(mem.project_id)
    assert mem2 is not None
    validated = [e for e in mem2.events if e.type == MemoryEventType.VALIDATED]
    assert len(validated) == 2
    reports = [v for v in mem2.artifact_versions if v.kind == ArtifactKind.VALIDATION_REPORT]
    assert len(reports) == 2

    # Artefatos da missão 1 intactos
    assert (tmp_path / "validate" / mid1 / "validation_report.md").exists()


def test_build_estende_memoria(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")

    # Missão 1: VALIDATE
    client1 = RecordingFakeValidateClient()
    pipe1 = _pipe(tmp_path, store, client1)
    asyncio.run(pipe1.run(ValidateRequest(idea_text="Validar EcoTrack-IA")))
    mem = store.list_projects()[0]

    # O compiler (usado pelo BUILD) já vê o contexto da missão 1
    compiler = MemoryContextCompiler(store=store, config=cfg)
    block = compiler.compile(mem.project_id)
    assert "## Memória do Projeto" in block
    assert "XPTO" in block

    # Missão 2: BUILD (hook real record_build_completion)
    mission_dir = tmp_path / "build-mission"
    mission_dir.mkdir()
    for f in ("requirements.md", "architecture.md", "report.md"):
        (mission_dir / f).write_text("# x", encoding="utf-8")
    build_state = MissionState(
        mission_id="mb-1", project_id="p", mode=ProjectMode.BUILD,
        status=MissionStatus.COMPLETED, current_stage="report", mode_payload={},
    )
    record_build_completion(store, mem, build_state, mission_dir)

    mem2 = store.get(mem.project_id)
    assert mem2 is not None
    types = {e.type for e in mem2.events}
    assert MemoryEventType.VALIDATED in types
    assert MemoryEventType.BUILD_SUCCEEDED in types
    kinds = {v.kind for v in mem2.artifact_versions}
    assert ArtifactKind.VALIDATION_REPORT in kinds
    assert ArtifactKind.REQUIREMENTS in kinds