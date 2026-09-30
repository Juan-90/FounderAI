"""
Módulo DISCOVER (v4.7.0 — Mapeamento Estruturado de Oportunidades).

Pipeline encadeado: ScopeFramer → Ideation → Normalizer → Ranker → Critic,
produzindo um DiscoverResult ranqueado e criticado (contrarian leve).
"""

from backend.discover.agents import (
    DiscoverPipeline,
    OpportunityCritic,
    OpportunityIdeationAgent,
    OpportunityNormalizer,
    OpportunityRanker,
    ScopeFramerAgent,
)
from backend.discover.schemas import (
    DiscoverRequest,
    DiscoverResult,
    OpportunityProfile,
)

__all__ = [
    "DiscoverPipeline",
    "DiscoverRequest",
    "DiscoverResult",
    "OpportunityCritic",
    "OpportunityIdeationAgent",
    "OpportunityNormalizer",
    "OpportunityRanker",
    "OpportunityProfile",
    "ScopeFramerAgent",
]