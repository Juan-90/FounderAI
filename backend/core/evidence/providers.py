"""
Provedores de busca plugáveis (v5.2.0).

• SearchProvider: protocolo estrutural (duck-typed, sem herança forçada).
• MockSearchProvider: determinístico, aceita fixtures ou gera por hash da query.
• HttpSearchProvider: REST configurável, timeout, captura de exceções.

Regra de não-invenção: provedores NUNCA inventam URLs ou fontes fictícias.
O que vier do provedor é o que vai para o grafo.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

import httpx


class SearchProviderError(Exception):
    """Falha controlada de um provedor de busca."""


@dataclass(frozen=True)
class SearchResultItem:
    """Um resultado cru retornado por um provedor de busca."""

    title: str
    snippet: str
    url: Optional[str] = None
    publisher: Optional[str] = None
    score: float = 1.0

    def stable_source_id(self) -> str:
        """ID estável derivado do conteúdo (para deduplicação no grafo)."""
        seed = f"{self.url or ''}|{self.title}|{self.snippet[:200]}"
        return "src-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


@runtime_checkable
class SearchProvider(Protocol):
    """Contrato de qualquer provedor de busca (duck-typed)."""

    def search(self, query: str, max_results: int = 5) -> list[SearchResultItem]: ...


class MockSearchProvider:
    """Provedor determinístico: aceita fixtures ou gera resultados por hash da query."""

    def __init__(self, fixtures: Optional[dict[str, list[SearchResultItem]]] = None) -> None:
        self._fixtures: dict[str, list[SearchResultItem]] = dict(fixtures or {})

    def add_fixture(self, query: str, results: list[SearchResultItem]) -> None:
        self._fixtures[query] = results

    def search(self, query: str, max_results: int = 5) -> list[SearchResultItem]:
        if query in self._fixtures:
            return list(self._fixtures[query])[:max_results]
        # Geração determinística baseada em hash da query
        digest = hashlib.sha1(query.encode("utf-8")).hexdigest()
        generated: list[SearchResultItem] = []
        for i in range(min(max_results, 3)):
            generated.append(SearchResultItem(
                title=f"Mock result {i+1} for '{query[:40]}'",
                snippet=f"Deterministic snippet {i+1} (digest prefix: {digest[:8]}).",
                url=f"https://mock.example/{digest[:8]}/{i+1}",
                publisher="mock-publisher",
                score=1.0 - (i * 0.1),
            ))
        return generated


class HttpSearchProvider:
    """Provedor REST configurável via endpoint + API key."""

    def __init__(
        self,
        endpoint: str,
        api_key: str = "",
        timeout_seconds: float = 10.0,
        headers: Optional[dict[str, str]] = None,
        query_param: str = "q",
        max_param: str = "limit",
        results_path: tuple[str, ...] = ("results",),
        field_map: Optional[dict[str, str]] = None,
    ) -> None:
        if not endpoint.strip():
            raise ValueError("HttpSearchProvider exige endpoint não-vazio.")
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._headers = dict(headers or {})
        if api_key:
            self._headers.setdefault("Authorization", f"Bearer {api_key}")
        self._query_param = query_param
        self._max_param = max_param
        self._results_path = results_path
        # Mapeia chaves do JSON -> campos de SearchResultItem
        self._field_map: dict[str, str] = dict(field_map or {
            "title": "title", "snippet": "snippet",
            "url": "url", "publisher": "publisher", "score": "score",
        })

    def _extract(self, data: Any, path: tuple[str, ...]) -> Any:
        current = data
        for segment in path:
            if isinstance(current, dict) and segment in current:
                current = current[segment]
            else:
                return None
        return current

    def _item_from(self, raw: Any) -> Optional[SearchResultItem]:
        if not isinstance(raw, dict):
            return None
        fm = self._field_map
        title = raw.get(fm.get("title", "title"))
        snippet = raw.get(fm.get("snippet", "snippet"))
        if not title and not snippet:
            return None
        url = raw.get(fm.get("url", "url"))
        publisher = raw.get(fm.get("publisher", "publisher"))
        score_raw = raw.get(fm.get("score", "score"))
        try:
            score = float(score_raw) if score_raw is not None else 1.0
        except (TypeError, ValueError):
            score = 1.0
        return SearchResultItem(
            title=str(title or ""),
            snippet=str(snippet or ""),
            url=str(url) if url else None,
            publisher=str(publisher) if publisher else None,
            score=score,
        )

    def search(self, query: str, max_results: int = 5) -> list[SearchResultItem]:
        params = {self._query_param: query, self._max_param: max_results}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(self._endpoint, params=params, headers=self._headers)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise SearchProviderError(
                f"HttpSearchProvider: timeout após {self._timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise SearchProviderError(
                f"HttpSearchProvider: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError(
                f"HttpSearchProvider: {type(exc).__name__}: {exc}"
            ) from exc
        except ValueError as exc:
            raise SearchProviderError(
                f"HttpSearchProvider: resposta não-JSON: {exc}"
            ) from exc

        payload = self._extract(data, self._results_path)
        if not isinstance(payload, list):
            raise SearchProviderError(
                f"HttpSearchProvider: caminho {self._results_path} não é lista."
            )
        results: list[SearchResultItem] = []
        for raw in payload[:max_results]:
            item = self._item_from(raw)
            if item is not None:
                results.append(item)
        return results