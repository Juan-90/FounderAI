"""
Modelos de domínio do sistema de evidências do FounderAI (v5.2.1 + métricas).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EvidenceOrigin(str, Enum):
    MODEL_OPINION = "model_opinion"
    USER_CONTEXT = "user_context"
    EXTERNAL = "external"


class Source(BaseModel):
    source_id: str
    title: Optional[str] = None
    url: Optional[str] = None
    publisher: Optional[str] = None
    retrieved_at: datetime
    raw_snippet: Optional[str] = None


class EvidenceItem(BaseModel):
    evidence_id: str
    source_id: str
    quote_or_summary: str
    origin: EvidenceOrigin = EvidenceOrigin.EXTERNAL
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    claim_id: str
    text: str
    origin: EvidenceOrigin
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    used_in_decision: bool = False


class EvidenceGraph(BaseModel):
    """Grafo de evidências + métricas de observabilidade (v5.2.1)."""

    mission_id: str
    claims: list[Claim] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Observabilidade: provider_used, cache_hits/misses, deduped_*",
    )