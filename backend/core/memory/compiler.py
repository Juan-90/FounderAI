"""
MemoryContextCompiler — resume a memória do projeto para prompts de LLM (v5.5.0).

Local canônico (v5.5.0): backend/core/memory/compiler.py
(backend/core/memory_compiler.py é shim de compatibilidade).

Ordem de prioridade:
  1. Goal atual + metadados do projeto.
  2. Decisões ativas aceitas.
  3. Aprendizados recentes — **human_feedback tem prioridade máxima**
     (até 4 mais recentes), depois demais learnings (até 2).
  4. Versões mais recentes de artefatos-chave.
  5. Falhas recentes de build/QA (BUILD_FAILED / ESCALATED).

Truncamento determinístico por budget (PROJECT_MEMORY_CONTEXT_MAX_CHARS).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.core.config import Settings, settings
from backend.domain.memory import ArtifactKind, MemoryEventType
from backend.domain.memory_store import DiskProjectMemoryStore

_KEY_ARTIFACT_KINDS = (
    ArtifactKind.REQUIREMENTS,
    ArtifactKind.ARCHITECTURE,
    ArtifactKind.CODE_BUNDLE,
    ArtifactKind.TEST_REPORT,
)

_TRUNC_MARK = "\n…[truncado por limite de contexto]"


class MemoryContextCompiler:
    def __init__(
        self,
        store: Optional[DiskProjectMemoryStore] = None,
        config: Optional[Settings] = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._store = store or DiskProjectMemoryStore(
            base_dir=Path(self._config.PROJECT_MEMORY_DIR)
        )

    def compile(self, project_id: str, max_chars: Optional[int] = None) -> str:
        budget = int(max_chars or self._config.PROJECT_MEMORY_CONTEXT_MAX_CHARS)
        memory = self._store.get(project_id)
        if memory is None:
            return ""

        sections: list[str] = []

        # 1 — Goal + metadados
        meta = [
            "## Memória do Projeto",
            f"- Nome: {memory.name}",
            f"- Tipo: {memory.project_type.value if memory.project_type else 'n/a'}",
            f"- Status: {memory.status}",
        ]
        if memory.current_goal:
            meta.append(f"- Goal atual: {memory.current_goal}")
        sections.append("\n".join(meta))

        # 2 — Decisões aceitas
        accepted = [d for d in memory.decisions if d.status == "accepted"]
        if accepted:
            lines = ["## Decisões ativas"]
            for d in accepted[-6:]:
                lines.append(f"- {d.title}: {d.rationale}")
            sections.append("\n".join(lines))

        # 3 — Aprendizados: human_feedback SEMPRE primeiro (alta prioridade p/ IMPROVE)
        human = [l for l in memory.learnings if l.source == "human_feedback"]
        human_ids = {l.learning_id for l in human}
        rest = [l for l in memory.learnings if l.learning_id not in human_ids]
        prioritized = human[-4:] + rest[-2:]
        if prioritized:
            lines = ["## Aprendizados recentes (feedback humano primeiro)"]
            for l in prioritized:
                lines.append(f"- [{l.source}] {l.text}")
            sections.append("\n".join(lines))

        # 4 — Versões recentes de artefatos-chave
        art_lines = ["## Artefatos-chave (versões mais recentes)"]
        for kind in _KEY_ARTIFACT_KINDS:
            latest = max(
                (v for v in memory.artifact_versions if v.kind == kind),
                key=lambda v: v.created_at,
                default=None,
            )
            if latest is not None:
                art_lines.append(
                    f"- {kind.value}: {latest.path}"
                    + (f" ({latest.summary})" if latest.summary else "")
                )
        if len(art_lines) > 1:
            sections.append("\n".join(art_lines))

        # 5 — Falhas recentes de build/QA
        failures = [
            e for e in memory.events
            if e.type in (MemoryEventType.BUILD_FAILED, MemoryEventType.ESCALATED)
        ][-3:]
        if failures:
            lines = ["## Falhas recentes"]
            for e in failures:
                lines.append(f"- {e.type.value}: {e.message}")
            sections.append("\n".join(lines))

        # Truncamento determinístico respeitando o budget
        out: list[str] = []
        for sec in sections:
            candidate = "\n\n".join(out + [sec])
            if len(candidate) <= budget:
                out.append(sec)
            else:
                remaining = budget - len("\n\n".join(out)) - 2
                if remaining > len(_TRUNC_MARK) + 10:
                    out.append(sec[: remaining - len(_TRUNC_MARK)] + _TRUNC_MARK)
                break
        return "\n\n".join(out)