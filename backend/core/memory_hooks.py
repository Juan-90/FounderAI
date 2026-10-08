"""
Hooks de memória para pipelines (v5.3.0).

Todas as funções são fail-open: erros de memória NUNCA quebram a missão
(os pipelines chamam dentro de try/except).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.core.memory_compiler import MemoryContextCompiler
from backend.domain.memory import (
    ArtifactKind,
    MemoryEventType,
    ProjectMemory,
)
from backend.domain.memory_store import DiskProjectMemoryStore
from backend.domain.models import MissionState

_MEMORY_HEADER = "--- MEMÓRIA DO PROJETO (contexto acumulado) ---"
_MEMORY_FOOTER = "--- FIM DA MEMÓRIA ---"


def resolve_memory(
    store: DiskProjectMemoryStore,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Optional[ProjectMemory]:
    """Carrega (ou cria) a memória do projeto por id ou nome."""
    if project_id:
        existing = store.get(project_id)
        if existing is not None:
            return existing
    if project_name:
        for m in store.list_projects():
            if m.name == project_name:
                return m
    # Cria nova
    if project_name:
        return store.create(name=project_name)
    if project_id:
        now = datetime.now(timezone.utc)
        memory = ProjectMemory(
            project_id=project_id, name=project_id,
            created_at=now, updated_at=now,
        )
        store.save(memory)
        return memory
    return None


def build_memory_block(compiler: MemoryContextCompiler, project_id: str) -> str:
    return compiler.compile(project_id)


def attach_memory_to_intent(intent: str, block: str) -> str:
    """Anexa o bloco de memória ao intent (base de todos os prompts)."""
    if not block:
        return intent
    return f"{intent}\n\n{_MEMORY_HEADER}\n{block}\n{_MEMORY_FOOTER}\n"


# ─────────────────────────────────────────────────────────────
# Gravadores por modo
# ─────────────────────────────────────────────────────────────

def record_validate_completion(
    store: DiskProjectMemoryStore,
    memory: ProjectMemory,
    state: MissionState,
    mission_dir: Path,
) -> None:
    """VALIDATE: evento VALIDATED + versiona report + learnings + evidence ref."""
    store.append_event(
        memory.project_id, MemoryEventType.VALIDATED,
        f"Validação concluída ({state.status.value})", mission_id=state.mission_id,
    )
    report = mission_dir / "validation_report.md"
    if report.exists():
        store.add_artifact_version(
            memory.project_id, ArtifactKind.VALIDATION_REPORT, str(report),
            mission_id=state.mission_id,
        )
    risks = state.mode_payload.get("contrarian_risk", {}) or {}
    for r in (risks.get("reasons_to_kill") or [])[:3]:
        store.add_learning(memory.project_id, str(r), "validation_risk",
                           mission_id=state.mission_id)
    gaps = state.mode_payload.get("evidence_gaps", {}) or {}
    for g in (gaps.get("gaps") or [])[:3]:
        store.add_learning(memory.project_id, str(g), "validation_risk",
                           mission_id=state.mission_id)
    ev = mission_dir / "evidence" / "evidence_graph.json"
    if ev.exists():
        current = store.get(memory.project_id)
        if current is not None and str(ev) not in current.evidence_refs:
            current.evidence_refs.append(str(ev))
            store.save(current)


def record_build_completion(
    store: DiskProjectMemoryStore,
    memory: ProjectMemory,
    state: MissionState,
    mission_dir: Path,
) -> None:
    """BUILD: evento SUCCEEDED/FAILED/ESCALATED + versiona artefatos-chave."""
    from backend.domain.enums import MissionStatus
    if state.status == MissionStatus.COMPLETED:
        evt = MemoryEventType.BUILD_SUCCEEDED
    elif state.status == MissionStatus.ESCALATED:
        evt = MemoryEventType.ESCALATED
    else:
        evt = MemoryEventType.BUILD_FAILED
    store.append_event(
        memory.project_id, evt, f"Build finalizado ({state.status.value})",
        mission_id=state.mission_id,
    )
    for kind, fname in (
        (ArtifactKind.REQUIREMENTS, "requirements.md"),
        (ArtifactKind.ARCHITECTURE, "architecture.md"),
        (ArtifactKind.TEST_REPORT, "report.md"),
    ):
        p = mission_dir / fname
        if p.exists():
            store.add_artifact_version(
                memory.project_id, kind, str(p), mission_id=state.mission_id,
            )
    bundle = mission_dir / "code_bundle.json"
    if bundle.exists():
        store.add_artifact_version(
            memory.project_id, ArtifactKind.CODE_BUNDLE, str(bundle),
            mission_id=state.mission_id,
        )


def record_vab_completion(
    store: DiskProjectMemoryStore,
    memory: ProjectMemory,
    state: MissionState,
    mission_dir: Path,
) -> None:
    """VALIDATE_AND_BUILD: registra ambas as fases na mesma memória."""
    record_validate_completion(store, memory, state, mission_dir)
    record_build_completion(store, memory, state, mission_dir)