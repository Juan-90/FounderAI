"""
Provedores de busca plugáveis (v5.2.1 + Real Search Providers).

• SearchProvider: protocolo estrutural (duck-typed, sem herança forçada).
• MockSearchProvider: determinístico (testes/fallback seguro).
• HttpSearchProvider: REST genérico configurável.
• TavilySearchProvider: Tavily AI Search API (https://api.tavily.com/search).
• SerperSearchProvider: Serper.dev Google Search API (https://google.serper.dev/search).
• get_search_provider(name): fábrica com fallback para MockSearchProvider
  quando a API key correspondente não está configurada.

Regra de não-invenção: provedores NUNCA inventam URLs ou fontes fictícias.
O que vier do provedor é o que vai para o grafo.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

import httpx

from backend.core.config import Settings, settings

logger = logging.getLogger(__name__)


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


# ─────────────────────────────────────────────────────────────
# MockSearchProvider (fallback seguro)
# ─────────────────────────────────────────────────────────────

class MockSearchProvider:
    """Provedor determinístico: aceita fixtures ou gera resultados por hash da query."""

    def __init__(self, fixtures: Optional[dict[str, list[SearchResultItem]]] = None) -> None:
        self._fixtures: dict[str, list[SearchResultItem]] = dict(fixtures or {})

    def add_fixture(self, query: str, results: list[SearchResultItem]) -> None:
        self._fixtures[query] = results

    def search(self, query: str, max_results: int = 5) -> list[SearchResultItem]:
        if query in self._fixtures:
            return list(self._fixtures[query])[:max_results]
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


# ─────────────────────────────────────────────────────────────
# HttpSearchProvider (REST genérico)
# ─────────────────────────────────────────────────────────────

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
            title=str(title or ""), snippet=str(snippet or ""),
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


# ─────────────────────────────────────────────────────────────
# TavilySearchProvider (Tavily AI Search)
# ─────────────────────────────────────────────────────────────

class TavilySearchProvider:
    """Tavily AI Search API (https://api.tavily.com/search).

    Resposta mapeada: results[i] → title, url, content (snippet), score.
    """

    ENDPOINT = "https://api.tavily.com/search"
    DEFAULT_PUBLISHER = "tavily"

    def __init__(
        self,
        api_key: str | None,
        timeout: float = 10.0,
        include_answer: bool = False,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not (api_key or "").strip():
            raise ValueError("TavilySearchProvider exige api_key não-vazia.")
        self._api_key = api_key
        self._timeout = timeout
        self._include_answer = include_answer
        self._transport = transport  # permite injeção de MockTransport em testes

    def search(self, query: str, max_results: int = 5) -> list[SearchResultItem]:
        body: dict[str, Any] = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": self._include_answer,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        client_kwargs: dict[str, Any] = {"timeout": self._timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        try:
            with httpx.Client(**client_kwargs) as client:
                response = client.post(self.ENDPOINT, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise SearchProviderError(
                f"TavilySearchProvider: timeout após {self._timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise SearchProviderError(
                f"TavilySearchProvider: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError(
                f"TavilySearchProvider: {type(exc).__name__}: {exc}"
            ) from exc
        except ValueError as exc:
            raise SearchProviderError(
                f"TavilySearchProvider: resposta não-JSON: {exc}"
            ) from exc

        raw_results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(raw_results, list):
            raise SearchProviderError(
                "TavilySearchProvider: campo 'results' não é lista."
            )

        items: list[SearchResultItem] = []
        for r in raw_results[:max_results]:
            if not isinstance(r, dict):
                continue
            title = r.get("title")
            content = r.get("content") or r.get("snippet") or ""
            if not title and not content:
                continue
            url = r.get("url")
            score_raw = r.get("score")
            try:
                score = float(score_raw) if score_raw is not None else 1.0
            except (TypeError, ValueError):
                score = 1.0
            items.append(SearchResultItem(
                title=str(title or ""),
                snippet=str(content or ""),
                url=str(url) if url else None,
                publisher=self.DEFAULT_PUBLISHER,
                score=max(0.0, min(1.0, score)),
            ))
        return items


# ─────────────────────────────────────────────────────────────
# SerperSearchProvider (Serper.dev Google Search)
# ─────────────────────────────────────────────────────────────

class SerperSearchProvider:
    """Serper.dev Google Search API (https://google.serper.dev/search).

    Resposta mapeada: organic[i] → title, link (url), snippet.
    """

    ENDPOINT = "https://google.serper.dev/search"
    DEFAULT_PUBLISHER = "serper"

    def __init__(
        self,
        api_key: str | None,
        timeout: float = 10.0,
        gl: Optional[str] = "br",
        hl: Optional[str] = "pt-br",
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not (api_key or "").strip():
            raise ValueError("SerperSearchProvider exige api_key não-vazia.")
        self._api_key = api_key
        self._timeout = timeout
        self._gl = gl
        self._hl = hl
        self._transport = transport

    def search(self, query: str, max_results: int = 5) -> list[SearchResultItem]:
        body: dict[str, Any] = {"q": query, "num": max_results}
        if self._gl:
            body["gl"] = self._gl
        if self._hl:
            body["hl"] = self._hl
        headers = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        client_kwargs: dict[str, Any] = {"timeout": self._timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        try:
            with httpx.Client(**client_kwargs) as client:
                response = client.post(self.ENDPOINT, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise SearchProviderError(
                f"SerperSearchProvider: timeout após {self._timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise SearchProviderError(
                f"SerperSearchProvider: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError(
                f"SerperSearchProvider: {type(exc).__name__}: {exc}"
            ) from exc
        except ValueError as exc:
            raise SearchProviderError(
                f"SerperSearchProvider: resposta não-JSON: {exc}"
            ) from exc

        raw_results = data.get("organic") if isinstance(data, dict) else None
        if not isinstance(raw_results, list):
            raise SearchProviderError(
                "SerperSearchProvider: campo 'organic' não é lista."
            )

        items: list[SearchResultItem] = []
        for r in raw_results[:max_results]:
            if not isinstance(r, dict):
                continue
            title = r.get("title")
            snippet = r.get("snippet") or ""
            if not title and not snippet:
                continue
            url = r.get("link")
            items.append(SearchResultItem(
                title=str(title or ""),
                snippet=str(snippet or ""),
                url=str(url) if url else None,
                publisher=self.DEFAULT_PUBLISHER,
                score=1.0,  # Serper não fornece score; usa posição como proxy
            ))
        return items


# ─────────────────────────────────────────────────────────────
# Fábrica
# ─────────────────────────────────────────────────────────────

_VALID_NAMES = frozenset({"mock", "http", "tavily", "serper"})


def get_search_provider(
    name: str,
    config: Settings | None = None,
) -> SearchProvider:
    """Retorna o provedor pelo nome, com fallback seguro para Mock.

    Se a API key correspondente estiver ausente/vazia, registra aviso e
    retorna MockSearchProvider (fail-safe). Names inválidos lançam ValueError.
    """
    cfg = config if config is not None else settings
    n = (name or "").strip().lower()
    if n not in _VALID_NAMES:
        raise ValueError(
            f"Provedor desconhecido: '{name}'. Válidos: {sorted(_VALID_NAMES)}"
        )

    if n == "mock":
        return MockSearchProvider()

    if n == "http":
        endpoint = cfg.EVIDENCE_HTTP_ENDPOINT or ""
        if not endpoint.strip():
            logger.warning(
                "EvidenceService: EVIDENCE_HTTP_ENDPOINT vazio; "
                "usando MockSearchProvider como fallback."
            )
            return MockSearchProvider()
        return HttpSearchProvider(
            endpoint=endpoint,
            api_key=cfg.EVIDENCE_HTTP_API_KEY,
            timeout_seconds=cfg.EVIDENCE_TIMEOUT_SECONDS,
        )

    if n == "tavily":
        key = (cfg.TAVILY_API_KEY or "").strip()
        if not key:
            logger.warning(
                "EvidenceService: TAVILY_API_KEY não configurada; "
                "usando MockSearchProvider como fallback."
            )
            return MockSearchProvider()
        return TavilySearchProvider(api_key=key, timeout=cfg.EVIDENCE_TIMEOUT_SECONDS)

    # n == "serper"
    key = (cfg.SERPER_API_KEY or "").strip()
    if not key:
        logger.warning(
            "EvidenceService: SERPER_API_KEY não configurada; "
            "usando MockSearchProvider como fallback."
        )
        return MockSearchProvider()
    return SerperSearchProvider(api_key=key, timeout=cfg.EVIDENCE_TIMEOUT_SECONDS)