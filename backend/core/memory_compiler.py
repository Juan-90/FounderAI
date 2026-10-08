"""
MemoryContextCompiler — resume a memória do projeto para prompts de LLM (v5.3.0).

Ordem de prioridade (do mais para o menos importante):
  1. Goal atual + metadados do projeto.
  2. Decisões ativas aceitas.
  3. Aprendizados recentes (QA / riscos de validação).
  4. Versões mais recentes de artefatos-chave.
  5. Falhas recentes de build/QA (eventos BUILD_FAILED / ESCALATED).

Truncamento determinístico: seções são adicionadas inteiras enquanto couberem
no budget; a primeira que não couber é cortada no limite com marcador.
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

        # 3 — Aprendizados recentes (QA / riscos)
        qa_risk = [
            l for l in memory.learnings
            if l.source in ("qa_failure", "validation_risk")
        ]
        recent = (qa_risk or memory.learnings)[-5:]
        if recent:
            lines = ["## Aprendizados recentes"]
            for l in recent:
                lines.append(f"- [{l.source}] {l.text}")
            sections.append("\n".join(lines))

        # 4 — Versões recentes de artefatos-chave
        art_lines = ["## Artefatos-chave (versões mais recentes)"]
        for kind in _KEY_ARTIFACT_KINDS:
            latest = self._store.latest_artifact(project_id, kind)
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
                remaining = budget - len("\n\n".join(out)) - 2  # -2 para o separador "\n\n"
                if remaining > len(_TRUNC_MARK) + 10:
                    out.append(sec[: remaining - len(_TRUNC_MARK)] + _TRUNC_MARK)
                break
        return "\n\n".join(out)