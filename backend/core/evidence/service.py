"""
EvidenceService — coleta, cache, dedup, métricas e montagem do EvidenceGraph (v5.2.1).

Fluxo de search(): 1) normaliza query -> 2) consulta cache -> 3) se miss, chama
provider -> 4) salva cache. Métricas capturadas: provider_used, cache_hits,
cache_misses, deduped_sources_count, deduped_evidence_count, deduped_claims_count.

Regras rígidas: nunca inventa URL/fonte; FAIL_OPEN; descarta item vazio.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.core.config import Settings, settings
from backend.core.evidence.cache import FileEvidenceCache
from backend.core.evidence.dedup import (
    deduplicate_claims,
    deduplicate_evidence,
    deduplicate_sources,
)
from backend.core.evidence.providers import (
    SearchProvider,
    SearchProviderError,
    SearchResultItem,
    get_search_provider,
)
from backend.domain.evidence import (
    Claim,
    EvidenceGraph,
    EvidenceItem,
    EvidenceOrigin,
    Source,
)


@dataclass
class SearchQuery:
    query: str
    max_results: int
    hints: list[str] = field(default_factory=list)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_evidence_id(source_id: str, snippet: str) -> str:
    seed = f"{source_id}|{snippet[:200]}"
    return "ev-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


_STOPWORDS = frozenset({
    "de", "da", "do", "das", "dos", "para", "com", "em", "no", "na", "um",
    "uma", "que", "e", "ou", "por", "the", "a", "an", "and", "or", "of",
    "for", "with", "in", "on", "to",
})


def _keywords(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


class EvidenceService:
    """Planeja buscas, coleta (com cache), converte, dedupa e monta o grafo."""

    def __init__(
        self,
        config: Settings | None = None,
        provider: Optional[SearchProvider] = None,
        cache: Optional[FileEvidenceCache] = None,
        provider_name: Optional[str] = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._provider_name = (
            provider_name or self._config.EVIDENCE_PROVIDER or "mock"
        ).lower()
        # Factory com fallback seguro (Mock) quando falta key/endpoint
        self._provider: SearchProvider = (
            provider or get_search_provider(self._provider_name, config=self._config)
        )
        self._cache = cache if cache is not None else FileEvidenceCache(config=self._config)
        self.warnings: list[str] = []
        self.metrics: dict[str, Any] = {
            "provider_used": self._provider_name,
            "cache_hits": 0,
            "cache_misses": 0,
            "deduped_sources_count": 0,
            "deduped_evidence_count": 0,
            "deduped_claims_count": 0,
        }

    @property
    def enabled(self) -> bool:
        return self._config.EVIDENCE_ENABLED

    # ── Plan ──
    def plan_queries(self, mode: str, payload: dict[str, Any]) -> list[SearchQuery]:
        if not self.enabled:
            return []
        queries: list[str] = []
        if mode in ("discover", "DISCOVER"):
            theme = (payload.get("theme") or "").strip()
            audience = (payload.get("audience") or "").strip()
            geography = (payload.get("geography") or "").strip()
            if theme:
                q = theme
                if audience:
                    q += f" para {audience}"
                if geography:
                    q += f" em {geography}"
                queries.append(q)
                queries.append(f"tendências de mercado {theme}")
        elif mode in ("validate", "VALIDATE", "validate_and_build", "VALIDATE_AND_BUILD"):
            problem = (payload.get("problem") or "").strip()
            audience = (payload.get("audience") or payload.get("target_audience") or "").strip()
            if problem:
                queries.append(f"{problem} {audience}".strip())
                queries.append(f"concorrentes {problem}")
        elif mode in ("build", "BUILD"):
            intent = (payload.get("intent") or payload.get("theme") or "").strip()
            if intent:
                queries.append(f"melhores práticas {intent[:80]}")
        if not queries:
            return []

        per_query = max(1, self._config.EVIDENCE_MAX_RESULTS_PER_QUERY)
        cap = max(1, self._config.EVIDENCE_MAX_QUERIES_PER_MISSION)
        return [
            SearchQuery(query=q, max_results=per_query, hints=[mode])
            for q in queries[:cap]
        ]

    # ── Search (cache -> provider -> cache) ──
    def search(self, queries: list[SearchQuery]) -> list[SearchResultItem]:
        if not self.enabled:
            return []
        fail_open = self._config.EVIDENCE_FAIL_OPEN
        collected: list[SearchResultItem] = []
        cap = max(1, self._config.EVIDENCE_MAX_QUERIES_PER_MISSION)
        for sq in queries[:cap]:
            # 1+2) normaliza (dentro do cache) + consulta cache
            cached = self._cache.get(self._provider_name, sq.query)
            if cached is not None:
                self.metrics["cache_hits"] += 1
                collected.extend(cached[: sq.max_results])
                continue
            # 3) miss -> provider
            self.metrics["cache_misses"] += 1
            try:
                results = self._provider.search(sq.query, max_results=sq.max_results)
            except SearchProviderError as exc:
                self.warnings.append(
                    f"EvidenceService: provider falhou em '{sq.query[:40]}': {exc}"
                )
                if not fail_open:
                    raise
                continue
            except Exception as exc:
                self.warnings.append(
                    f"EvidenceService: erro inesperado em '{sq.query[:40]}': {exc}"
                )
                if not fail_open:
                    raise
                continue
            # 4) salva cache (fail-open interno)
            self._cache.set(self._provider_name, sq.query, results)
            collected.extend(results)
        return collected

    # ── To evidence (regra rígida + dedup) ──
    def to_evidence(
        self, results: list[SearchResultItem]
    ) -> tuple[list[Source], list[EvidenceItem]]:
        sources_by_id: dict[str, Source] = {}
        items: list[EvidenceItem] = []
        retrieved_at = _utcnow()

        for r in results:
            if not (r.title or r.snippet or r.publisher):
                self.warnings.append(
                    "EvidenceService.to_evidence: descartado item sem título/snippet/publisher."
                )
                continue
            source_id = r.stable_source_id()
            if source_id not in sources_by_id:
                sources_by_id[source_id] = Source(
                    source_id=source_id, title=r.title or None, url=r.url,
                    publisher=r.publisher, retrieved_at=retrieved_at,
                    raw_snippet=r.snippet or None,
                )
            items.append(EvidenceItem(
                evidence_id=_stable_evidence_id(source_id, r.snippet),
                source_id=source_id, quote_or_summary=r.snippet or r.title,
                origin=EvidenceOrigin.EXTERNAL,
                confidence=max(0.0, min(1.0, r.score)), tags=[],
            ))

        sources_dedup, src_removed = deduplicate_sources(list(sources_by_id.values()))
        items_dedup, ev_removed = deduplicate_evidence(items)
        self.metrics["deduped_sources_count"] += src_removed
        self.metrics["deduped_evidence_count"] += ev_removed
        if src_removed:
            self.warnings.append(f"EvidenceService: {src_removed} fonte(s) duplicada(s) removida(s).")
        if ev_removed:
            self.warnings.append(f"EvidenceService: {ev_removed} evidência(s) duplicada(s) removida(s).")
        return sources_dedup, items_dedup

    # ── Bind claims ──
    def bind_claims(self, claims: list[Claim], evidence: list[EvidenceItem]) -> list[Claim]:
        updated: list[Claim] = []
        for c in claims:
            c_kw = _keywords(c.text)
            if not c_kw:
                updated.append(c)
                continue
            matched = [
                ev.evidence_id for ev in evidence
                if c_kw & _keywords(ev.quote_or_summary)
            ]
            merged = list(dict.fromkeys(list(c.evidence_ids) + matched))
            updated.append(c.model_copy(update={"evidence_ids": merged}))
        return updated

    # ── Build graph (dedup completo + métricas persistidas) ──
    def build_graph(
        self, mission_id: str, claims: list[Claim],
        evidence: list[EvidenceItem], sources: list[Source],
    ) -> EvidenceGraph:
        sources_d, src_removed = deduplicate_sources(sources)
        evidence_d, ev_removed = deduplicate_evidence(evidence)
        claims_d, cl_removed = deduplicate_claims(claims)
        self.metrics["deduped_sources_count"] += src_removed
        self.metrics["deduped_evidence_count"] += ev_removed
        self.metrics["deduped_claims_count"] += cl_removed
        if src_removed:
            self.warnings.append(f"EvidenceService: {src_removed} fonte(s) duplicada(s) removida(s).")
        if ev_removed:
            self.warnings.append(f"EvidenceService: {ev_removed} evidência(s) duplicada(s) removida(s).")
        if cl_removed:
            self.warnings.append(f"EvidenceService: {cl_removed} claim(s) duplicado(s) removido(s).")
        return EvidenceGraph(
            mission_id=mission_id, claims=list(claims_d),
            evidence_items=list(evidence_d), sources=list(sources_d),
            notes=list(self.warnings), metrics=dict(self.metrics),
        )