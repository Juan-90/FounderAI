"""
Módulo DISCOVER (v4.7.0 — Mapeamento Estruturado de Oportunidades).
"""

from backend.discover.agents import (
    OpportunityCritic,
    OpportunityIdeationAgent,
    OpportunityNormalizer,
    OpportunityRanker,
    ScopeFramerAgent,
)
from backend.discover.pipeline import DiscoverPipeline, DiscoverSynthesizer
from backend.discover.schemas import (
    DiscoverRequest,
    DiscoverResult,
    OpportunityProfile,
)

__all__ = [
    "DiscoverPipeline",
    "DiscoverRequest",
    "DiscoverResult",
    "DiscoverSynthesizer",
    "OpportunityCritic",
    "OpportunityIdeationAgent",
    "OpportunityNormalizer",
    "OpportunityRanker",
    "OpportunityProfile",
    "ScopeFramerAgent",
]