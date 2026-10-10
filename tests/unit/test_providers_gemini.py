"""
Testes do GeminiProvider (v5.5.4) — sem rede real.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from backend.core.config import Settings
from backend.core.llm_client import LLMErrorKind, LLMProviderError
from backend.core.providers.gemini_provider import GeminiProvider


def _cfg(**over: Any) -> Settings:
    base = {
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-1.5-flash",
        "LLM_TIMEOUT_SECONDS": 10.0,
    }
    base.update(over)
    return Settings(**base)


def test_complete_retorna_conteudo() -> None:
    import backend.core.providers.gemini_provider as mod
    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, headers=None, json=None):
            return httpx.Response(200, json={
                "candidates": [{"content": {"parts": [{"text": "gemini ok"}]}}]
            }, request=httpx.Request("POST", url))
    mod.httpx.AsyncClient = _FakeClient
    provider = GeminiProvider(config=_cfg())
    out = asyncio.run(provider.complete("sys", "user"))
    assert out == "gemini ok"


def test_missing_key_levanta_missing_key() -> None:
    provider = GeminiProvider(config=_cfg(GEMINI_API_KEY=""))
    with pytest.raises(LLMProviderError) as exc:
        asyncio.run(provider.complete("sys", "user"))
    assert exc.value.kind == LLMErrorKind.MISSING_KEY


def test_payload_inesperado() -> None:
    import backend.core.providers.gemini_provider as mod
    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, headers=None, json=None):
            return httpx.Response(200, json={"unexpected": True},
                                  request=httpx.Request("POST", url))
    mod.httpx.AsyncClient = _FakeClient
    provider = GeminiProvider(config=_cfg())
    with pytest.raises(LLMProviderError) as exc:
        asyncio.run(provider.complete("sys", "user"))
    assert exc.value.kind == LLMErrorKind.INVALID_JSON