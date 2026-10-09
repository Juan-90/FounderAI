"""
Contratos de feedback humano (v5.5.0 — OBSERVE mínimo).

Feedback (rating 1-5 e/ou nota + tags) é convertido em MemoryLearning
(source="human_feedback") + evento OBSERVED na timeline do projeto.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProjectFeedbackRequest(BaseModel):
    """Pedido de registro de feedback humano sobre um projeto."""
    project_id: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    note: Optional[str] = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list)
    mission_id: Optional[str] = None
    source: Literal["human_feedback"] = "human_feedback"


class ProjectFeedbackResult(BaseModel):
    """Resultado da gravação do feedback."""

    accepted: bool
    learning_id: Optional[str] = None
    event_id: Optional[str] = None
    summary: str