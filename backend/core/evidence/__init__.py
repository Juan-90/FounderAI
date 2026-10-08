"""
Camada de evidências do FounderAI (v5.2.1).
"""

from backend.core.evidence.cache import FileEvidenceCache
from backend.core.evidence.dedup import (
    apply_relevance_to_items,
    deduplicate_claims,
    deduplicate_evidence,
    deduplicate_sources,
    score_relevance,
)
from backend.core.evidence.providers import (
    HttpSearchProvider,
    MockSearchProvider,
    SearchProvider,
    SearchProviderError,
    SearchResultItem,
    SerperSearchProvider,
    TavilySearchProvider,
    get_search_provider,
)
from backend.core.evidence.service import EvidenceService, SearchQuery

__all__ = [
    "EvidenceService",
    "FileEvidenceCache",
    "HttpSearchProvider",
    "MockSearchProvider",
    "SearchProvider",
    "SearchProviderError",
    "SearchQuery",
    "SearchResultItem",
    "SerperSearchProvider",
    "TavilySearchProvider",
    "apply_relevance_to_items",
    "deduplicate_claims",
    "deduplicate_evidence",
    "deduplicate_sources",
    "get_search_provider",
    "score_relevance",
]