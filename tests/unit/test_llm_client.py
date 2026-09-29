"""
Testes unitários do LLM Client (Fase 2 + v4.3 resiliência).

Cobre: resolução de provedor, settings via env, fallback Cloud→Local (isolado
com LLM_HTTP_RETRIES=0), retry/backoff em HTTP transitório (429/5xx), timeout,
JSON inválido, observabilidade (LLMCallResult) e validação de configuração.
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
    LLMCallResult,
    LLMClient,
    LLMErrorKind,
    LLMProviderError,
    OllamaInvalidResponseError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    _clean_json,
)


def _make_settings(
    primary: ProviderName = "groq",
    fallback: ProviderName = "local",
    timeout: float = 5.0,
    architect: ProviderName | None = None,
    securitycoder: ProviderName | None = None,
    productstrategist: ProviderName | None = None,
    groq_api_key: str = "groq-test-key",
    local_base_url: str = "http://localhost:11434/v1",
    http_retries: int = 2,
    retry_backoff: float = 1.5,
) -> Settings:
    return Settings(
        PRIMARY_PROVIDER=primary,
        FALLBACK_PROVIDER=fallback,
        LLM_TIMEOUT_SECONDS=timeout,
        LLM_HTTP_RETRIES=http_retries,
        LLM_RETRY_BACKOFF_SECONDS=retry_backoff,
        ARCHITECT_PROVIDER=architect,
        SECURITYCODER_PROVIDER=securitycoder,
        PRODUCTSTRATEGIST_PROVIDER=productstrategist,
        GROQ_API_KEY=groq_api_key,
        OPENROUTER_API_KEY="or-test-key",
        OPENAI_API_KEY="oa-test-key",
        ollama_base_url=local_base_url,
    )


def _openai_response(content: str) -> httpx.Response:
    return httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": content}}]},
    )


def _run(scenario: Coroutine[Any, Any, None]) -> None:
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
    assert client.resolve_provider("ARCHITECT") == "openrouter"


def test_settings_carrega_overrides_de_env(monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert cfg.LLM_TIMEOUT_SECONDS == 12.5


def test_env_invalido_para_provider_raise_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    body: dict[str, Any] = json.loads(recorded[0].content)
    assert body["model"] == "openai/gpt-oss-20b"


def test_complete_retorna_texto_bruto() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _openai_response("olá, fundador!")

    async def scenario() -> None:
        client = LLMClient(_make_settings(), transport=httpx.MockTransport(handler))
        assert await client.complete("sys", "user") == "olá, fundador!"

    _run(scenario())


def test_fallback_automatico_cloud_para_local() -> None:
    """Fallback isolado (retries=0): groq 500 -> local imediato."""
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.host == "api.groq.com":
            return httpx.Response(500, json={"error": "boom"})
        return _openai_response('{"status": "FINAL"}')

    async def scenario() -> None:
        client = LLMClient(
            _make_settings(http_retries=0), transport=httpx.MockTransport(handler)
        )
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
        cfg = _make_settings(groq_api_key="")
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
    assert len(recorded) == 1


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


# ─────────────────────────────────────────────────────────────
# v4.3 — Retry com backoff em HTTP transitório
# ─────────────────────────────────────────────────────────────
def test_retry_em_http_500_antes_do_fallback() -> None:
    """groq 500 persistente: 1 chamada + 2 retries, depois fallback local."""
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.host == "api.groq.com":
            return httpx.Response(500, json={"error": "boom"})
        return _openai_response('{"ok": true}')

    async def scenario() -> None:
        client = LLMClient(
            _make_settings(http_retries=2, retry_backoff=0.01),
            transport=httpx.MockTransport(handler),
        )
        result = await client.complete_json("sys", "user")
        assert result == {"ok": True}

    _run(scenario())
    assert [r.url.host for r in recorded] == ["api.groq.com"] * 3 + ["localhost"]


def test_retry_recupera_em_segunda_tentativa_sem_fallback() -> None:
    """groq 500 na 1ª, 200 na 2ª: sucesso sem acionar fallback."""
    recorded: list[httpx.Request] = []
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        calls["n"] += 1
        if request.url.host == "api.groq.com":
            if calls["n"] == 1:
                return httpx.Response(500, json={"error": "boom"})
            return _openai_response('{"recuperado": true}')
        return _openai_response('{"local": true}')

    async def scenario() -> None:
        client = LLMClient(
            _make_settings(http_retries=2, retry_backoff=0.01),
            transport=httpx.MockTransport(handler),
        )
        result = await client.complete_json("sys", "user")
        assert result == {"recuperado": True}

    _run(scenario())
    assert [r.url.host for r in recorded] == ["api.groq.com", "api.groq.com"]


def test_resposta_vazia_triggera_fallback() -> None:
    """groq 200 com content vazio -> tratado como erro -> fallback local."""
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.host == "api.groq.com":
            return _openai_response("")
        return _openai_response('{"local": true}')

    async def scenario() -> None:
        client = LLMClient(
            _make_settings(http_retries=0), transport=httpx.MockTransport(handler)
        )
        result = await client.complete_json("sys", "user")
        assert result == {"local": True}

    _run(scenario())
    assert [r.url.host for r in recorded] == ["api.groq.com", "localhost"]


# ─────────────────────────────────────────────────────────────
# Observabilidade (Bloco 2)
# ─────────────────────────────────────────────────────────────
def test_complete_verbose_retorna_metadados_do_provedor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _openai_response("hello founder")

    async def scenario() -> None:
        client = LLMClient(_make_settings(), transport=httpx.MockTransport(handler))
        result = await client.complete_verbose("sys", "user")
        assert isinstance(result, LLMCallResult)
        assert result.content == "hello founder"
        assert result.provider_used == "groq"
        assert result.model_used == "openai/gpt-oss-20b"
        assert result.fallback_triggered is False
        assert result.original_provider is None

    _run(scenario())


def test_complete_verbose_sinaliza_fallback_em_cadeia() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.groq.com":
            return httpx.Response(500, json={"error": "boom"})
        return _openai_response("local response")

    async def scenario() -> None:
        client = LLMClient(
            _make_settings(http_retries=0), transport=httpx.MockTransport(handler)
        )
        result = await client.complete_verbose("sys", "user")
        assert isinstance(result, LLMCallResult)
        assert result.provider_used == "local"
        assert result.model_used == "gemma2:2b"
        assert result.fallback_triggered is True
        assert result.original_provider == "groq"

    _run(scenario())


def test_complete_retrocompativel_retorna_apenas_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _openai_response("texto bruto")

    async def scenario() -> None:
        client = LLMClient(_make_settings(), transport=httpx.MockTransport(handler))
        text = await client.complete("sys", "user")
        assert isinstance(text, str)
        assert text == "texto bruto"

    _run(scenario())


# ─────────────────────────────────────────────────────────────
# Validação de configuração (Settings)
# ─────────────────────────────────────────────────────────────
def test_validate_provider_config_sem_chave_gera_warning() -> None:
    cfg = _make_settings(primary="groq", groq_api_key="")
    warnings = cfg.validate_provider_config()
    assert len(warnings) >= 1
    assert any("groq" in w and "fallback" in w for w in warnings)


def test_validate_provider_config_local_sem_warning() -> None:
    cfg = _make_settings(primary="local", groq_api_key="")
    assert cfg.validate_provider_config() == []


def test_validate_provider_config_override_sem_chave_gera_warning() -> None:
    cfg = Settings(
        PRIMARY_PROVIDER="groq",
        FALLBACK_PROVIDER="local",
        LLM_TIMEOUT_SECONDS=5.0,
        ARCHITECT_PROVIDER="openrouter",
        GROQ_API_KEY="groq-key",
        OPENROUTER_API_KEY="",
        OPENAI_API_KEY="",
    )
    warnings = cfg.validate_provider_config()
    assert any("Architect" in w and "openrouter" in w for w in warnings)