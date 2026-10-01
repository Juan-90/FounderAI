"""
EvidenceService — orquestra coleta, conversão e montagem do EvidenceGraph (v5.2.0).

Regras rígidas:
  • FAIL_OPEN=True (default): falhas/timeout do provider gravam aviso e retornam
    lista vazia sem quebrar a missão.
  • to_evidence NUNCA inventa URLs ou fontes fictícias: só cria Source a partir
    do que o provider retornou; sem URL -> Source com url=None (legítimo).
  • Resultados sem title E sem snippet E sem publisher são descartados.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.core.config import Settings, settings
from backend.core.evidence.providers import (
    HttpSearchProvider,
    MockSearchProvider,
    SearchProvider,
    SearchProviderError,
    SearchResultItem,
)
from backend.domain.evidence import (
    Claim,
    EvidenceGraph,
    EvidenceItem,
    EvidenceOrigin,
    Source,
)
from datetime import datetime, timezone


@dataclass
class SearchQuery:
    """Consulta planejada pelo serviço."""

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
    """Planeja buscas, coleta, converte para o domínio e monta o grafo."""

    def __init__(
        self,
        config: Settings | None = None,
        provider: Optional[SearchProvider] = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._provider: SearchProvider = provider or self._default_provider()
        self.warnings: list[str] = []

    @property
    def enabled(self) -> bool:
        return self._config.EVIDENCE_ENABLED

    def _default_provider(self) -> SearchProvider:
        prov = (self._config.EVIDENCE_PROVIDER or "mock").lower()
        if prov == "http":
            return HttpSearchProvider(
                endpoint=self._config.EVIDENCE_HTTP_ENDPOINT or "",
                api_key=self._config.EVIDENCE_HTTP_API_KEY,
                timeout_seconds=self._config.EVIDENCE_TIMEOUT_SECONDS,
            )
        return MockSearchProvider()

    # ── Plan ──
    def plan_queries(self, mode: str, payload: dict[str, Any]) -> list[SearchQuery]:
        """Gera queries a partir do modo + payload (heurística determinística)."""
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

        per_query = min(
            self._config.EVIDENCE_MAX_RESULTS_PER_QUERY,
            max(1, self._config.EVIDENCE_MAX_RESULTS_PER_QUERY),
        )
        cap = max(1, self._config.EVIDENCE_MAX_QUERIES_PER_MISSION)
        planned: list[SearchQuery] = []
        for q in queries[:cap]:
            planned.append(SearchQuery(query=q, max_results=per_query, hints=[mode]))
        return planned

    # ── Search ──
    def search(self, queries: list[SearchQuery]) -> list[SearchResultItem]:
        """Executa queries respeitando limites e FAIL_OPEN."""
        if not self.enabled:
            return []
        fail_open = self._config.EVIDENCE_FAIL_OPEN
        collected: list[SearchResultItem] = []
        cap = max(1, self._config.EVIDENCE_MAX_QUERIES_PER_MISSION)
        for sq in queries[:cap]:
            try:
                results = self._provider.search(sq.query, max_results=sq.max_results)
            except SearchProviderError as exc:
                msg = f"EvidenceService: provider falhou em '{sq.query[:40]}': {exc}"
                self.warnings.append(msg)
                if not fail_open:
                    raise
                continue
            except Exception as exc:
                msg = f"EvidenceService: erro inesperado em '{sq.query[:40]}': {exc}"
                self.warnings.append(msg)
                if not fail_open:
                    raise
                continue
            collected.extend(results)
        return collected

    # ── To evidence (regra rígida) ──
    def to_evidence(
        self, results: list[SearchResultItem]
    ) -> tuple[list[Source], list[EvidenceItem]]:
        """Converte SearchResultItem em (Source[], EvidenceItem[]) sem inventar nada."""
        sources_by_id: dict[str, Source] = {}
        items: list[EvidenceItem] = []
        retrieved_at = _utcnow()

        for r in results:
            # Regra: descartar itens sem nenhum conteúdo aproveitável.
            if not (r.title or r.snippet or r.publisher):
                self.warnings.append(
                    f"EvidenceService.to_evidence: descartado item sem título/snippet/publisher."
                )
                continue
            source_id = r.stable_source_id()
            if source_id not in sources_by_id:
                # Regra rígida: nunca inventar URL. Se provider não trouxe, url=None.
                sources_by_id[source_id] = Source(
                    source_id=source_id,
                    title=r.title or None,
                    url=r.url,               # pode ser None — legítimo
                    publisher=r.publisher,
                    retrieved_at=retrieved_at,
                    raw_snippet=r.snippet or None,
                )
            evidence_id = _stable_evidence_id(source_id, r.snippet)
            items.append(EvidenceItem(
                evidence_id=evidence_id,
                source_id=source_id,
                quote_or_summary=r.snippet or r.title,
                origin=EvidenceOrigin.EXTERNAL,
                confidence=max(0.0, min(1.0, r.score)),
                tags=[],
            ))
        return list(sources_by_id.values()), items

    # ── Bind claims ──
    def bind_claims(
        self, claims: list[Claim], evidence: list[EvidenceItem]
    ) -> list[Claim]:
        """Liga cada claim às evidências cujo snippet tem overlap de keywords."""
        updated: list[Claim] = []
        for c in claims:
            c_kw = _keywords(c.text)
            if not c_kw:
                updated.append(c)
                continue
            matched: list[str] = []
            for ev in evidence:
                e_kw = _keywords(ev.quote_or_summary)
                if c_kw & e_kw:  # interseção não vazia
                    matched.append(ev.evidence_id)
            # Mantém IDs originais + adiciona os ligados (deduplicado)
            merged = list(dict.fromkeys(list(c.evidence_ids) + matched))
            updated.append(c.model_copy(update={"evidence_ids": merged}))
        return updated

    # ── Build graph ──
    def build_graph(
        self,
        mission_id: str,
        claims: list[Claim],
        evidence: list[EvidenceItem],
        sources: list[Source],
    ) -> EvidenceGraph:
        return EvidenceGraph(
            mission_id=mission_id,
            claims=list(claims),
            evidence_items=list(evidence),
            sources=list(sources),
            notes=list(self.warnings),
        )