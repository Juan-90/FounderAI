"""
FeedbackService — grava feedback humano na Project Memory (v5.5.x).

record_feedback: valida (rating OU note) e grava MemoryLearning
(source="human_feedback") + evento OBSERVED em UMA ÚNICA operação atômica
(store.atomic_mutate -> temp + os.replace), evitando estado parcial.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.core.config import Settings, settings
from backend.domain.feedback import ProjectFeedbackRequest, ProjectFeedbackResult
from backend.domain.memory import MemoryEvent, MemoryEventType, MemoryLearning
from backend.domain.memory_store import DiskProjectMemoryStore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackService:
    def __init__(self, config: Optional[Settings] = None) -> None:
        self._config: Settings = config if config is not None else settings

    def record_feedback(
        self, store: DiskProjectMemoryStore, request: ProjectFeedbackRequest,
    ) -> ProjectFeedbackResult:
        if not self._config.OBSERVE_FEEDBACK_ENABLED:
            return ProjectFeedbackResult(
                accepted=False, summary="OBSERVE_FEEDBACK_ENABLED=false."
            )

        project_id = request.project_id
        if not project_id:
            return ProjectFeedbackResult(
                accepted=False, summary="project_id obrigatório."
            )

        has_rating = request.rating is not None
        note = (request.note or "").strip()
        if not has_rating and not note:
            return ProjectFeedbackResult(
                accepted=False, summary="Feedback vazio: informe rating ou note."
            )

        if store.get(project_id) is None:
            return ProjectFeedbackResult(
                accepted=False, summary="Projeto não encontrado."
            )

        max_chars = int(self._config.OBSERVE_FEEDBACK_MAX_NOTE_CHARS)
        if len(note) > max_chars:
            note = note[:max_chars]

        rating_txt = f"rating={request.rating}" if has_rating else "rating=n/a"
        tags_txt = f" tags=[{', '.join(request.tags)}]" if request.tags else ""
        text = f"Feedback humano: {rating_txt}{tags_txt}"
        if note:
            text += f" — {note}"

        now = _utcnow()
        learning = MemoryLearning(
            learning_id=uuid4().hex, text=text, source="human_feedback",
            mission_id=request.mission_id, created_at=now,
        )
        event = MemoryEvent(
            event_id=uuid4().hex, type=MemoryEventType.OBSERVED,
            mission_id=request.mission_id,
            message=f"Feedback observado ({rating_txt})",
            data={"rating": request.rating, "tags": list(request.tags)},
            created_at=now,
        )

        def _mutate(memory) -> None:
            memory.learnings.append(learning)
            memory.events.append(event)

        updated = store.atomic_mutate(project_id, _mutate)
        if updated is None:
            return ProjectFeedbackResult(
                accepted=False, summary="Projeto não encontrado."
            )
        return ProjectFeedbackResult(
            accepted=True, learning_id=learning.learning_id,
            event_id=event.event_id, summary=text,
        )