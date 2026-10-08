"""
Deduplicação e relevância básica para evidências (v5.2.1).

- deduplicate_sources: URL canônica (lowercase, sem trailing slash, normaliza
  http->https, remove www.) com fallback para (title+publisher) normalizado.
- deduplicate_evidence: hash de (quote_or_summary, source_id).
- deduplicate_claims: texto normalizado (lowercase, pontuação básica removida,
  espaços colapsados).
- score_relevance(query, title, snippet): overlap lexical (Jaccard) com
  penalidade para snippets curtos (<15 chars).

Todas as funções retornam (lista_limpa, count_removidos).
"""

from __future__ import annotations

import re
from typing import Iterable, Optional
from urllib.parse import urlparse, urlunparse

from backend.domain.evidence import Claim, EvidenceItem, Source


# ─────────────────────────────────────────────────────────────
# Normalização
# ─────────────────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    """Lowercase + remove pontuação básica + colapsa espaços."""
    if not text:
        return ""
    t = text.lower()
    t = _PUNCT_RE.sub(" ", t)
    return _SPACE_RE.sub(" ", t).strip()


def _tokenize(text: str) -> frozenset[str]:
    norm = _normalize_text(text)
    return frozenset(t for t in norm.split() if t)


def _canonical_url(url: Optional[str]) -> Optional[str]:
    """Normaliza URL para deduplicação.

    Regras: lowercase scheme+netloc+path; http->https; remove trailing slash
    (exceto raiz /); remove www.; remove fragment; preserva query.
    """
    if not url or not url.strip():
        return None
    u = url.strip()
    if "://" not in u:
        u = "https://" + u
    try:
        parsed = urlparse(u)
    except ValueError:
        return None
    scheme = (parsed.scheme or "https").lower()
    if scheme == "http":
        scheme = "https"
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    normalized = urlunparse((scheme, host, path, parsed.params, parsed.query, ""))
    return normalized or None


# ─────────────────────────────────────────────────────────────
# Deduplicação
# ─────────────────────────────────────────────────────────────

def deduplicate_sources(sources: list[Source]) -> tuple[list[Source], int]:
    """Deduplica fontes por URL canônica; fallback por (title+publisher)."""
    seen_url: set[str] = set()
    seen_fallback: set[str] = set()
    kept: list[Source] = []
    removed = 0
    for s in sources:
        key = _canonical_url(s.url)
        if key is not None:
            if key in seen_url:
                removed += 1
                continue
            seen_url.add(key)
        else:
            # Fallback: título + publisher normalizados
            fb = f"{_normalize_text(s.title or '')}|{_normalize_text(s.publisher or '')}"
            if not fb or fb == "|":
                # Sem URL e sem fallback útil: mantém (não descarta arbitrariamente)
                pass
            elif fb in seen_fallback:
                removed += 1
                continue
            else:
                seen_fallback.add(fb)
        kept.append(s)
    return kept, removed


def deduplicate_evidence(
    items: list[EvidenceItem],
) -> tuple[list[EvidenceItem], int]:
    """Deduplica evidências por hash(quote_or_summary, source_id)."""
    seen: set[str] = set()
    kept: list[EvidenceItem] = []
    removed = 0
    for ev in items:
        key = f"{_normalize_text(ev.quote_or_summary)}|{ev.source_id}"
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        kept.append(ev)
    return kept, removed


def deduplicate_claims(claims: list[Claim]) -> tuple[list[Claim], int]:
    """Deduplica claims por texto normalizado (preserva claim_id do primeiro)."""
    seen: set[str] = set()
    kept: list[Claim] = []
    removed = 0
    for c in claims:
        key = _normalize_text(c.text)
        if not key:
            kept.append(c)  # sem texto: não descarta
            continue
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        kept.append(c)
    return kept, removed


# ─────────────────────────────────────────────────────────────
# Relevância
# ─────────────────────────────────────────────────────────────

def score_relevance(
    query: str,
    title: str = "",
    snippet: str = "",
    short_penalty_threshold: int = 15,
    short_penalty_factor: float = 0.5,
) -> float:
    """Score de relevância lexical [0.0, 1.0].

    Jaccard(query_tokens, title_tokens ∪ snippet_tokens), com penalidade
    se o snippet tiver menos de `short_penalty_threshold` caracteres.
    """
    q_tokens = _tokenize(query)
    if not q_tokens:
        return 0.0
    content_tokens = _tokenize(title) | _tokenize(snippet)
    if not content_tokens:
        return 0.0
    inter = len(q_tokens & content_tokens)
    union = len(q_tokens | content_tokens)
    jaccard = inter / union if union > 0 else 0.0
    score = max(0.0, min(1.0, jaccard))
    if len((snippet or "").strip()) < short_penalty_threshold:
        score *= short_penalty_factor
    return round(score, 4)


def apply_relevance_to_items(
    items: Iterable[EvidenceItem],
    query: str,
    min_score: float = 0.0,
) -> list[EvidenceItem]:
    """Reordena itens por relevância descendente; filtra os abaixo de min_score."""
    scored: list[tuple[float, EvidenceItem]] = []
    for it in items:
        s = score_relevance(query, title=it.quote_or_summary, snippet=it.quote_or_summary)
        if s >= min_score:
            scored.append((s, it))
    scored.sort(key=lambda kv: kv[0], reverse=True)
    return [it for _, it in scored]