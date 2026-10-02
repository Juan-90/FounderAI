"""
Testes unitários dos providers reais (Tavily, Serper) + factory (v5.2.1).

Usa httpx.MockTransport para mockar respostas HTTP — zero rede na CI.
Cobre sucesso, erro HTTP, timeout e fallback para MockSearchProvider.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest

from backend.core.config import Settings
from backend.core.evidence.providers import (
    HttpSearchProvider,
    MockSearchProvider,
    SearchProviderError,
    SerperSearchProvider,
    TavilySearchProvider,
    get_search_provider,
)


def _cfg(**overrides: Any) -> Settings:
    base = {
        "EVIDENCE_ENABLED": True,
        "EVIDENCE_PROVIDER": "mock",
        "EVIDENCE_HTTP_ENDPOINT": "https://example.test/search",
        "EVIDENCE_HTTP_API_KEY": "",
        "EVIDENCE_TIMEOUT_SECONDS": 2.0,
        "EVIDENCE_FAIL_OPEN": True,
        "TAVILY_API_KEY": "",
        "SERPER_API_KEY": "",
    }
    base.update(overrides)
    return Settings(**base)


# ─────────────────────────────────────────────────────────────
# TavilySearchProvider
# ─────────────────────────────────────────────────────────────

def test_tavily_success_parses_results() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/search"
        assert req.method == "POST"
        body = req.read()  # API pública: lê o body do request
        assert b"test query" in body
        return httpx.Response(200, json={
            "results": [
                {"title": "T1", "url": "https://a/1", "content": "Snippet 1", "score": 0.95},
                {"title": "T2", "url": "https://a/2", "content": "Snippet 2", "score": 0.8},
                {"title": "", "url": None, "content": "", "score": 0.5},  # descartado
            ],
        })

    transport = httpx.MockTransport(handler)
    provider = TavilySearchProvider(api_key="tav-key", timeout=2.0, transport=transport)
    items = provider.search("test query", max_results=5)
    assert len(items) == 2
    assert items[0].title == "T1"
    assert items[0].url == "https://a/1"
    assert items[0].snippet == "Snippet 1"
    assert items[0].publisher == "tavily"
    assert items[0].score == 0.95
    assert items[1].score == 0.8

    transport = httpx.MockTransport(handler)
    provider = TavilySearchProvider(api_key="tav-key", timeout=2.0, transport=transport)
    items = provider.search("test query", max_results=5)
    assert len(items) == 2
    assert items[0].title == "T1"
    assert items[0].url == "https://a/1"
    assert items[0].snippet == "Snippet 1"
    assert items[0].publisher == "tavily"
    assert items[0].score == 0.95
    assert items[1].score == 0.8


def test_tavily_http_error_raises_search_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    transport = httpx.MockTransport(handler)
    provider = TavilySearchProvider(api_key="tav-key", transport=transport)
    with pytest.raises(SearchProviderError, match="HTTP 401"):
        provider.search("x", max_results=2)


def test_tavily_timeout_raises_search_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento")

    transport = httpx.MockTransport(handler)
    provider = TavilySearchProvider(api_key="tav-key", timeout=0.1, transport=transport)
    with pytest.raises(SearchProviderError, match="timeout"):
        provider.search("x", max_results=1)


def test_tavily_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key"):
        TavilySearchProvider(api_key=None)
    with pytest.raises(ValueError, match="api_key"):
        TavilySearchProvider(api_key="   ")


def test_tavily_invalid_response_shape_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    transport = httpx.MockTransport(handler)
    provider = TavilySearchProvider(api_key="tav-key", transport=transport)
    with pytest.raises(SearchProviderError, match="results"):
        provider.search("x")


# ─────────────────────────────────────────────────────────────
# SerperSearchProvider
# ─────────────────────────────────────────────────────────────

def test_serper_success_parses_organic() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/search"
        assert req.headers.get("X-API-KEY") == "serp-key"
        return httpx.Response(200, json={
            "organic": [
                {"title": "S1", "link": "https://s/1", "snippet": "Snippet S1"},
                {"title": "S2", "link": "https://s/2", "snippet": "Snippet S2"},
            ],
            "knowledgeGraph": {"title": "KG ignorado"},
        })

    transport = httpx.MockTransport(handler)
    provider = SerperSearchProvider(api_key="serp-key", timeout=2.0, transport=transport)
    items = provider.search("qualquer coisa", max_results=5)
    assert len(items) == 2
    assert items[0].title == "S1"
    assert items[0].url == "https://s/1"
    assert items[0].snippet == "Snippet S1"
    assert items[0].publisher == "serper"
    assert items[0].score == 1.0  # Serper não dá score; proxy = 1.0


def test_serper_http_error_raises_search_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    transport = httpx.MockTransport(handler)
    provider = SerperSearchProvider(api_key="serp-key", transport=transport)
    with pytest.raises(SearchProviderError, match="HTTP 403"):
        provider.search("x")


def test_serper_timeout_raises_search_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("off-line")

    transport = httpx.MockTransport(handler)
    provider = SerperSearchProvider(api_key="serp-key", timeout=0.1, transport=transport)
    with pytest.raises(SearchProviderError, match="timeout"):
        provider.search("x")


def test_serper_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key"):
        SerperSearchProvider(api_key=None)


def test_serper_invalid_response_shape_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"noOrganic": []})

    transport = httpx.MockTransport(handler)
    provider = SerperSearchProvider(api_key="serp-key", transport=transport)
    with pytest.raises(SearchProviderError, match="organic"):
        provider.search("x")


# ─────────────────────────────────────────────────────────────
# Factory: get_search_provider
# ─────────────────────────────────────────────────────────────

def test_factory_mock() -> None:
    p = get_search_provider("mock")
    assert isinstance(p, MockSearchProvider)


def test_factory_http_sem_endpoint_falls_back_to_mock(caplog: pytest.LogCaptureFixture) -> None:
    cfg = _cfg(EVIDENCE_HTTP_ENDPOINT="")
    with caplog.at_level(logging.WARNING):
        p = get_search_provider("http", config=cfg)
    assert isinstance(p, MockSearchProvider)
    assert any("EVIDENCE_HTTP_ENDPOINT vazio" in r.message for r in caplog.records)


def test_factory_http_com_endpoint() -> None:
    cfg = _cfg(EVIDENCE_HTTP_ENDPOINT="https://x.test/search")
    p = get_search_provider("http", config=cfg)
    assert isinstance(p, HttpSearchProvider)


def test_factory_tavily_sem_key_falls_back_to_mock(caplog: pytest.LogCaptureFixture) -> None:
    cfg = _cfg(TAVILY_API_KEY="")
    with caplog.at_level(logging.WARNING):
        p = get_search_provider("tavily", config=cfg)
    assert isinstance(p, MockSearchProvider)
    assert any("TAVILY_API_KEY" in r.message for r in caplog.records)


def test_factory_tavily_com_key() -> None:
    cfg = _cfg(TAVILY_API_KEY="tav-real-key")
    p = get_search_provider("tavily", config=cfg)
    assert isinstance(p, TavilySearchProvider)


def test_factory_serper_sem_key_falls_back_to_mock(caplog: pytest.LogCaptureFixture) -> None:
    cfg = _cfg(SERPER_API_KEY="")
    with caplog.at_level(logging.WARNING):
        p = get_search_provider("serper", config=cfg)
    assert isinstance(p, MockSearchProvider)
    assert any("SERPER_API_KEY" in r.message for r in caplog.records)


def test_factory_serper_com_key() -> None:
    cfg = _cfg(SERPER_API_KEY="serp-real-key")
    p = get_search_provider("serper", config=cfg)
    assert isinstance(p, SerperSearchProvider)


def test_factory_nome_invalido() -> None:
    with pytest.raises(ValueError, match="Provedor desconhecido"):
        get_search_provider("openai")


def test_factory_case_insensitive() -> None:
    cfg = _cfg(TAVILY_API_KEY="tav-key")
    p = get_search_provider("TAVILY", config=cfg)
    assert isinstance(p, TavilySearchProvider)