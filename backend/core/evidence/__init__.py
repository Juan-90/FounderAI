"""
Camada de evidências do FounderAI (v5.2.0).

Provedores plugáveis de busca + EvidenceService que orquestra coleta,
conversão para o domínio (Source/EvidenceItem/Claim) e montagem do
EvidenceGraph. Respeita FAIL_OPEN: falhas de provedor não quebram a missão.
"""

from backend.core.evidence.providers import (
    HttpSearchProvider,
    MockSearchProvider,
    SearchProvider,
    SearchProviderError,
    SearchResultItem,
)
from backend.core.evidence.service import EvidenceService, SearchQuery

__all__ = [
    "EvidenceService",
    "HttpSearchProvider",
    "MockSearchProvider",
    "SearchProvider",
    "SearchProviderError",
    "SearchQuery",
    "SearchResultItem",
]