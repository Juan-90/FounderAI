"""
Testes unitários do LLM Client (Fase 2 — Arquitetura Híbrida).

Correções de tipagem aplicadas (Pylance strict → 0 problemas):
  1. Overrides de ambiente construídos como `dict[str, str]` e aplicados via
     `monkeypatch.setenv(...)` (variável de env é sempre string) — elimina os
     2 erros de `.update(dict[str, object])` (antiga Ln 49);
  2. Instanciação de `Settings` exclusivamente com o Literal `ProviderName` e
     `float` para `LLM_TIMEOUT_SECONDS` (factory `_make_settings`) — elimina
     os 6 erros de `str` incompatível com `ProviderName` / `float` (Ln 50);
  3. Rede simulada com `httpx.MockTransport` (determinístico, sem I/O real);
  4. Testes sync envolvendo `asyncio.run` — sem dependência de plugin async.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Coroutine

import httpx
import pytest
from pydantic import ValidationError

from backend.core.config import ProviderName, Settings
from backend.core.llm_client import (
    LLMClient,
    LLMErrorKind,
    LLMProviderError,
    OllamaInvalidResponseError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    _clean_json,
)


# ─────────────────────────────────────────────────────────────
# Factories tipadas (correção dos erros de Ln 50)
# ─────────────────────────────────────────────────────────────
def _make_settings(
    primary: ProviderName = "groq",
    fallback: ProviderName = "local",
    timeout: float = 5.0,
    architect: ProviderName | None = None,
    securitycoder: ProviderName | None = None,
    productstrategist: ProviderName | None = None,
    groq_api_key: str = "groq-test-key",
    local_base_url: str = "http://localhost:11434/v1",
) -> Settings:
    """Instancia `Settings` com tipos estritos: ProviderName (Literal) e float."""
    return Settings(
        PRIMARY_PROVIDER=primary,
        FALLBACK_PROVIDER=fallback,
        LLM_TIMEOUT_SECONDS=timeout,
        ARCHITECT_PROVIDER=architect,
        SECURITYCODER_PROVIDER=securitycoder,
        PRODUCTSTRATEGIST_PROVIDER=productstrategist,
        GROQ_API_KEY=groq_api_key,
        OPENROUTER_API_KEY="or-test-key",
        OPENAI_API_KEY="oa-test-key",
        ollama_base_url=local_base_url,
    )


def _openai_response(content: str) -> httpx.Response:
    """Envelope OpenAI-compatible válido."""
    return httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": content}}]},
    )


def _run(scenario: Coroutine[Any, Any, None]) -> None:
    """Executa um cenário async em teste sync (sem plugin de asyncio)."""
    asyncio.run(scenario)


# ─────────────────────────────────────────────────────────────
# Tipagem / Settings
# ─────────────────────────────────────────────────────────────
def test_resolve_provider_padrao_e_override_por_papel() -> None:
    cfg = _make_settings(architect="openrouter")
    client = LLMClient(cfg)
    assert client.resolve_provider() == "groq"
    assert client.resolve_provider("architect") == "openrouter"
    assert client.resolve_provider("securitycoder") == "groq"
    assert client.resolve_provider("ARCHITECT") == "openrouter"  # case-insensitive


def test_settings_carrega_overrides_de_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars são strings: dict[str, str] + monkeypatch.setenv (fix Ln 49)."""
    overrides: dict[str, str] = {
        "PRIMARY_PROVIDER": "openrouter",
        "FALLBACK_PROVIDER": "local",
        "LLM_TIMEOUT_SECONDS": "12.5",
        "ARCHITECT_PROVIDER": "groq",
    }
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)

    cfg = Settings()
    assert cfg.PRIMARY_PROVIDER == "openrouter"
    assert cfg.FALLBACK_PROVIDER == "local"
    assert cfg.ARCHITECT_PROVIDER == "groq"
    assert isinstance(cfg.LLM_TIMEOUT_SECONDS, float)
    assert cfg.LLM_TIMEOUT_SECONDS == 12.5


def test_env_invalido_para_provider_raise_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O Literal ProviderName rejeita valores fora do conjunto na borda."""
    monkeypatch.setenv("PRIMARY_PROVIDER", "azure")
    with pytest.raises(ValidationError):
        Settings()


# ─────────────────────────────────────────────────────────────
# Helpers legados
# ─────────────────────────────────────────────────────────────
def test_clean_json_remove_fences_de_markdown() -> None:
    raw = '```json\n{"verdict": "APPROVE"}\n```'
    assert _clean_json(raw) == '{"verdict": "APPROVE"}'


def test_aliases_de_retrocompatibilidade_fase1() -> None:
    assert OllamaUnavailableError is LLMProviderError
    assert OllamaTimeoutError is LLMProviderError
    assert OllamaInvalidResponseError is LLMProviderError
    error = LLMProviderError("falha de teste", kind=LLMErrorKind.UNAVAILABLE)
    assert str(error) == "[UNAVAILABLE] falha de teste"


# ─────────────────────────────────────────────────────────────
# LLMClient — Fase 2
# ─────────────────────────────────────────────────────────────
def test_complete_json_sucesso_no_provedor_primario() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return _openai_response(json.dumps({"verdict": "APPROVE", "score": 8.0}))

    async def scenario() -> None:
        client = LLMClient(_make_settings(), transport=httpx.MockTransport(handler))
        result = await client.complete_json("sys", "user")
        assert result == {"verdict": "APPROVE", "score": 8.0}

    _run(scenario())
    assert len(recorded) == 1
    assert recorded[0].url.host == "api.groq.com"
    assert recorded[0].headers["authorization"] == "Bearer groq-test-key"
    body: dict[str, Any] = json.loads(recorded[0].content)
    assert body["model"] == "llama-3.3-70b-versatile"


def test_complete_retorna_texto_bruto() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _openai_response("olá, fundador!")

    async def scenario() -> None:
        client = LLMClient(_make_settings(), transport=httpx.MockTransport(handler))
        assert await client.complete("sys", "user") == "olá, fundador!"

    _run(scenario())


def test_fallback_automatico_cloud_para_local() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.host == "api.groq.com":
            return httpx.Response(500, json={"error": "boom"})
        return _openai_response('{"status": "FINAL"}')

    async def scenario() -> None:
        client = LLMClient(_make_settings(), transport=httpx.MockTransport(handler))
        result = await client.complete_json("sys", "user")
        assert result == {"status": "FINAL"}

    _run(scenario())
    assert [r.url.host for r in recorded] == ["api.groq.com", "localhost"]


def test_sem_api_key_ativa_fallback_sem_chamada_cloud() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return _openai_response('{"ok": true}')

    async def scenario() -> None:
        cfg = _make_settings(groq_api_key="")  # cloud sem credencial
        client = LLMClient(cfg, transport=httpx.MockTransport(handler))
        assert await client.complete_json("sys", "user") == {"ok": True}

    _run(scenario())
    assert [r.url.host for r in recorded] == ["localhost"]


def test_timeout_propaga_kind_timeout_apos_cadeia() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento demais")

    async def scenario() -> None:
        client = LLMClient(_make_settings(), transport=httpx.MockTransport(handler))
        with pytest.raises(LLMProviderError) as exc_info:
            await client.complete("sys", "user")
        assert exc_info.value.kind is LLMErrorKind.TIMEOUT

    _run(scenario())


def test_json_invalido_raise_invalid_json() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return _openai_response("isto não é json")

    async def scenario() -> None:
        client = LLMClient(_make_settings(), transport=httpx.MockTransport(handler))
        with pytest.raises(LLMProviderError) as exc_info:
            await client.complete_json("sys", "user")
        assert exc_info.value.kind is LLMErrorKind.INVALID_JSON

    _run(scenario())
    assert len(recorded) == 1  # parse ocorre após a cadeia de fallback


def test_override_por_papel_roteia_provedor() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return _openai_response('{"plan": "ok"}')

    async def scenario() -> None:
        cfg = _make_settings(architect="openrouter")
        client = LLMClient(cfg, transport=httpx.MockTransport(handler))
        assert await client.complete_json("sys", "user", role="architect") == {"plan": "ok"}

    _run(scenario())
    assert recorded[0].url.host == "openrouter.ai"
    assert recorded[0].headers["authorization"] == "Bearer or-test-key"


def test_primary_local_nao_duplica_chamadas() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return _openai_response('{"local": true}')

    async def scenario() -> None:
        cfg = _make_settings(primary="local", fallback="local")
        client = LLMClient(cfg, transport=httpx.MockTransport(handler))
        assert await client.complete_json("sys", "user") == {"local": True}

    _run(scenario())
    assert [r.url.host for r in recorded] == ["localhost"]