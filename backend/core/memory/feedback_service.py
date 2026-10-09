"""
FeedbackService — grava feedback humano na Project Memory (v5.5.0).

record_feedback: valida (rating OU note), cria MemoryLearning
(source="human_feedback") + evento OBSERVED, persistindo atomicamente
via DiskProjectMemoryStore (temp + os.replace).
"""

from __future__ import annotations

from typing import Optional

from backend.core.config import Settings, settings
from backend.domain.feedback import ProjectFeedbackRequest, ProjectFeedbackResult
from backend.domain.memory import MemoryEventType
from backend.domain.memory_store import DiskProjectMemoryStore


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

        has_rating = request.rating is not None
        note = (request.note or "").strip()
        if not has_rating and not note:
            return ProjectFeedbackResult(
                accepted=False, summary="Feedback vazio: informe rating ou note."
            )

        memory = store.get(request.project_id)
        if memory is None:
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

        learning = store.add_learning(
            request.project_id, text, "human_feedback", mission_id=request.mission_id,
        )
        event = store.append_event(
            request.project_id, MemoryEventType.OBSERVED,
            f"Feedback observado ({rating_txt})", mission_id=request.mission_id,
            data={"rating": request.rating, "tags": list(request.tags)},
        )
        return ProjectFeedbackResult(
            accepted=True, learning_id=learning.learning_id,
            event_id=event.event_id, summary=text,
        )