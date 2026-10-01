"""
Modelos de domínio do sistema de evidências do FounderAI (v5.2.0).

Camada de base agnóstica de provedor/origem: modela fontes, itens de
evidência, alegações (claims) e o grafo que os conecta por missão.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EvidenceOrigin(str, Enum):
    """Origem de uma evidência ou alegação."""

    MODEL_OPINION = "model_opinion"
    USER_CONTEXT = "user_context"
    EXTERNAL = "external"


class Source(BaseModel):
    """Fonte externa de evidência (documento, página, dataset, etc.)."""

    source_id: str
    title: Optional[str] = None
    url: Optional[str] = None
    publisher: Optional[str] = None
    retrieved_at: datetime
    raw_snippet: Optional[str] = None


class EvidenceItem(BaseModel):
    """Um item de evidência extraído de uma fonte específica."""

    evidence_id: str
    source_id: str
    quote_or_summary: str
    origin: EvidenceOrigin = EvidenceOrigin.EXTERNAL
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    """Alegação fundamentada por evidências."""

    claim_id: str
    text: str
    origin: EvidenceOrigin
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    used_in_decision: bool = False


class EvidenceGraph(BaseModel):
    """Grafo de evidências associado a uma missão."""

    mission_id: str
    claims: list[Claim] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)