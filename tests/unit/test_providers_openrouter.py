"""
Testes do OpenRouterProvider (v5.5.4) — sem rede real (MockTransport httpx).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from backend.core.config import Settings
from backend.core.llm_client import LLMErrorKind, LLMProviderError
from backend.core.providers.openrouter_provider import OpenRouterProvider


def _cfg(**over: Any) -> Settings:
    base = {
        "OPENROUTER_API_KEY": "test-key",
        "OPENROUTER_MODEL": "openai/gpt-4o-mini",
        "LLM_TIMEOUT_SECONDS": 10.0,
    }
    base.update(over)
    return Settings(**base)


class _MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, status: int = 200, body: Any = None) -> None:
        self._status = status
        self._body = body or {
            "choices": [{"message": {"content": "resposta mockada"}}]
        }
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            status_code=self._status,
            json=self._body,
            request=request,
        )


def test_complete_retorna_conteudo() -> None:
    transport = _MockTransport()
    async def _run():
        provider = OpenRouterProvider(config=_cfg())
        # injeta transport mockado
        import backend.core.providers.openrouter_provider as mod
        original = httpx.AsyncClient
        async with original(transport=transport, timeout=10.0) as client:
            # patcha inline: criamos client diretamente
            pass
        # abordagem direta: mockar httpx.AsyncClient
        return await provider.complete("sys", "user")
    # forma mais simples: substituir httpx.AsyncClient no módulo
    import backend.core.providers.openrouter_provider as mod
    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, headers=None, json=None):
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}}]
            }, request=httpx.Request("POST", url))
    mod.httpx.AsyncClient = _FakeClient
    provider = OpenRouterProvider(config=_cfg())
    out = asyncio.run(provider.complete("sys", "user"))
    assert out == "ok"


def test_missing_key_levanta_missing_key() -> None:
    provider = OpenRouterProvider(config=_cfg(OPENROUTER_API_KEY=""))
    with pytest.raises(LLMProviderError) as exc:
        asyncio.run(provider.complete("sys", "user"))
    assert exc.value.kind == LLMErrorKind.MISSING_KEY


def test_http_error_propagado() -> None:
    import backend.core.providers.openrouter_provider as mod
    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, headers=None, json=None):
            req = httpx.Request("POST", url)
            return httpx.Response(429, text="rate limit", request=req)
    mod.httpx.AsyncClient = _FakeClient
    provider = OpenRouterProvider(config=_cfg())
    with pytest.raises(LLMProviderError) as exc:
        asyncio.run(provider.complete("sys", "user"))
    assert exc.value.kind == LLMErrorKind.HTTP_ERROR
    assert "429" in str(exc.value)