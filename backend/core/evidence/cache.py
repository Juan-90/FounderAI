"""
Cache persistente de evidências (v5.2.1).

FileEvidenceCache salva resultados de busca em artifacts/.evidence_cache/,
evitando re-chamadas idênticas ao provedor em missões distintas.

Chave: SHA256(provider_name + normalized_query)
Payload: {results: [...], stored_at: ISO-8601, ttl_seconds: int}
Flags via Settings: EVIDENCE_CACHE_ENABLED, EVIDENCE_CACHE_TTL_SECONDS,
                    EVIDENCE_CACHE_BYPASS (força miss).

Fail-open: erros de I/O, JSON ou schema são logados como warning e o cache
se comporta como miss (retorna None / não salva).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.core.config import Settings, settings
from backend.core.evidence.providers import SearchResultItem

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_query(query: str) -> str:
    """Normaliza a query para chave estável (case-fold, sem diacríticos, colapsa espaços)."""
    if not query:
        return ""
    nfkd = unicodedata.normalize("NFKD", query.lower())
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_only).strip()


def _cache_key(provider: str, query: str) -> str:
    seed = f"{(provider or 'unknown').lower()}|{_normalize_query(query)}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _item_to_dict(item: SearchResultItem) -> dict:
    return {
        "title": item.title,
        "snippet": item.snippet,
        "url": item.url,
        "publisher": item.publisher,
        "score": item.score,
    }


def _item_from_dict(d: dict) -> Optional[SearchResultItem]:
    try:
        return SearchResultItem(
            title=str(d.get("title") or ""),
            snippet=str(d.get("snippet") or ""),
            url=d.get("url"),
            publisher=d.get("publisher"),
            score=float(d.get("score", 1.0)),
        )
    except Exception:
        return None


class FileEvidenceCache:
    """Cache em disco de resultados de busca (fail-open)."""

    def __init__(
        self,
        root: Optional[Path] = None,
        config: Optional[Settings] = None,
    ) -> None:
        self._config = config if config is not None else settings
        self._root = Path(
            root if root is not None
            else Path(self._config.BUILD_ARTIFACTS_DIR).parent / ".evidence_cache"
        )

    @property
    def enabled(self) -> bool:
        return bool(self._config.EVIDENCE_CACHE_ENABLED)

    @property
    def ttl_seconds(self) -> int:
        return int(self._config.EVIDENCE_CACHE_TTL_SECONDS)

    @property
    def bypass(self) -> bool:
        return bool(self._config.EVIDENCE_CACHE_BYPASS)

    def _path_for(self, provider: str, query: str) -> Path:
        return self._root / f"{_cache_key(provider, query)}.json"

    def get(self, provider: str, query: str) -> Optional[list[SearchResultItem]]:
        """Retorna os resultados se existirem e estiverem dentro do TTL; senão None."""
        if not self.enabled or self.bypass:
            return None
        path = self._path_for(provider, query)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            stored_at_str = raw.get("stored_at")
            ttl = int(raw.get("ttl_seconds", self.ttl_seconds))
            payload = raw.get("results")
            if not isinstance(payload, list) or not isinstance(stored_at_str, str):
                logger.warning("EvidenceCache: payload inválido em %s", path.name)
                return None
            stored_at = datetime.fromisoformat(stored_at_str)
            if stored_at.tzinfo is None:
                stored_at = stored_at.replace(tzinfo=timezone.utc)
            age = (_now() - stored_at).total_seconds()
            if age < 0 or age > ttl:
                # Expirado: limpa e retorna miss
                try:
                    path.unlink()
                except OSError:
                    pass
                return None
            items: list[SearchResultItem] = []
            for d in payload:
                if not isinstance(d, dict):
                    continue
                it = _item_from_dict(d)
                if it is not None:
                    items.append(it)
            return items
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("EvidenceCache.get falhou: %s", exc)
            return None

    def set(
        self,
        provider: str,
        query: str,
        results: list[SearchResultItem],
        ttl: Optional[int] = None,
    ) -> None:
        """Salva resultados no cache. Fail-open: erros de I/O não quebram."""
        if not self.enabled or self.bypass:
            return
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            payload = {
                "provider": (provider or "unknown").lower(),
                "query": query,
                "normalized_query": _normalize_query(query),
                "results": [_item_to_dict(it) for it in results],
                "stored_at": _now().isoformat(),
                "ttl_seconds": int(ttl) if ttl is not None else self.ttl_seconds,
            }
            path = self._path_for(provider, query)
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("EvidenceCache.set falhou: %s", exc)

    def invalidate(self, provider: str, query: str) -> bool:
        """Remove entrada do cache; retorna True se existia."""
        path = self._path_for(provider, query)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError:
            return False