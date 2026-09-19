"""
LLM Client — FounderAI v3.5 (Fase 2 — Arquitetura Híbrida).

Wrapper assíncrono agnóstico a provedor:
  • Cloud: groq | openrouter | openai (APIs compatíveis com OpenAI);
  • Local: ollama / vLLM expostos via endpoint OpenAI-compatible;
  • Fallback automático Cloud → Local em qualquer falha de API;
  • Overrides por papel (Architect, SecurityCoder, ProductStrategist);
  • Tratamento defensivo global: nunca expõe stack trace (LLMProviderError).

Retrocompatibilidade Fase 1:
  • `call_ollama_json`, `LLMErrorKind`, `LLMProviderError` e aliases mantidos.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

import httpx
from rich.console import Console

from backend.core.config import ProviderName, Settings, settings

console = Console(stderr=True)

# ─────────────────────────────────────────
# Exceções
# ─────────────────────────────────────────

class LLMErrorKind(str, Enum):
    UNAVAILABLE  = "UNAVAILABLE"
    TIMEOUT      = "TIMEOUT"
    INVALID_JSON = "INVALID_JSON"
    HTTP_ERROR   = "HTTP_ERROR"


class LLMProviderError(Exception):
    """Exceção unificada para todos os erros do provedor LLM."""

    def __init__(self, message: str, kind: LLMErrorKind) -> None:
        super().__init__(message)
        self.kind = kind

    def __str__(self) -> str:
        return f"[{self.kind.value}] {super().__str__()}"


# Aliases de retrocompatibilidade (Fase 1)
OllamaUnavailableError   = LLMProviderError
OllamaTimeoutError       = LLMProviderError
OllamaInvalidResponseError = LLMProviderError

# ─────────────────────────────────────────
# Schema JSON obrigatório (Fase 1)
# ─────────────────────────────────────────

_JUROR_JSON_SCHEMA: str = """
Você DEVE responder APENAS com um objeto JSON válido, sem texto adicional, sem markdown, sem backticks.
O JSON deve seguir EXATAMENTE esta estrutura:
{
  "juror_name": "string",
  "score": 7.5,
  "verdict": "APPROVE",
  "reasoning": "string com máximo 500 caracteres"
}
Valores válidos para verdict: "APPROVE" ou "VETO"
"""

# ─────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────

def _resolve_url() -> str:
    base = settings.ollama_base_url.rstrip("/").removesuffix("/v1")
    return f"{base}/api/generate"


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    return raw


async def _stream(url: str, payload: dict[str, Any], timeout: float) -> str:
    tokens: list[str] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                data: dict[str, Any] = json.loads(line)
                if token := data.get("response"):
                    tokens.append(token)
                if data.get("done"):
                    break
    return "".join(tokens).strip()


# ─────────────────────────────────────────
# Interface pública legada (Fase 1)
# ─────────────────────────────────────────

async def call_ollama_json(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Chama o Ollama via /api/generate com streaming e 1 retry.

    Raises:
        LLMProviderError: Para qualquer falha — nunca expõe stack trace.
    """
    target_model: str = model or settings.council_model
    timeout: float = settings.ollama_timeout
    url: str = _resolve_url()

    payload: dict[str, Any] = {
        "model": target_model,
        "prompt": (
            system_prompt + "\n\n" + _JUROR_JSON_SCHEMA + "\n\n" + user_prompt
        ),
        "stream": True,
        "options": {"temperature": 0.2, "num_ctx": 2048},
    }

    last_error: LLMProviderError | None = None

    for attempt in range(1, 3):
        try:
            raw = _clean_json(await _stream(url, payload, timeout))

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                raise LLMProviderError(
                    f"Modelo '{target_model}' não retornou JSON válido.\n"
                    f"Conteúdo recebido: {raw[:200]}",
                    kind=LLMErrorKind.INVALID_JSON,
                )

        except LLMProviderError as e:
            if e.kind == LLMErrorKind.INVALID_JSON:
                raise
            last_error = e
            if attempt == 1:
                console.print(
                    f"[yellow]⚠  Tentativa {attempt} falhou "
                    f"({e.kind.value}). Retentando...[/yellow]"
                )

        except httpx.ConnectError:
            last_error = LLMProviderError(
                f"Ollama não está acessível em '{settings.ollama_base_url}'.\n"
                "Inicie com: docker compose -f docker/docker-compose.yml up -d ollama",
                kind=LLMErrorKind.UNAVAILABLE,
            )
            if attempt == 1:
                console.print("[yellow]⚠  Tentativa 1 falhou (conexão). Retentando...[/yellow]")

        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout,
                httpx.TimeoutException):
            last_error = LLMProviderError(
                f"Inferência com '{target_model}' excedeu {timeout}s.\n"
                "Dica: aumente OLLAMA_TIMEOUT no .env ou use gemma2:2b.",
                kind=LLMErrorKind.TIMEOUT,
            )
            if attempt == 1:
                console.print("[yellow]⚠  Tentativa 1 falhou (timeout). Retentando...[/yellow]")

        except httpx.HTTPStatusError as e:
            raise LLMProviderError(
                f"Ollama retornou HTTP {e.response.status_code}.\n"
                f"Verifique se '{target_model}' está disponível: "
                "docker exec founderai-ollama ollama list",
                kind=LLMErrorKind.HTTP_ERROR,
            )

        except Exception as e:
            raise LLMProviderError(
                f"Erro inesperado na chamada ao Ollama: {type(e).__name__}: {e}",
                kind=LLMErrorKind.HTTP_ERROR,
            )

    if last_error is None:  # pragma: no cover — defensivo
        raise LLMProviderError(
            "Falha desconhecida ao chamar o Ollama.",
            kind=LLMErrorKind.UNAVAILABLE,
        )
    raise last_error


# ─────────────────────────────────────────
# Fase 2 — Cliente agnóstico a provedor
# ─────────────────────────────────────────

class LLMClient:
    """
    Cliente LLM agnóstico a provedor com fallback automático Cloud → Local.

    Todos os provedores falam o protocolo OpenAI-compatible
    (`POST {base_url}/chat/completions`), incluindo Ollama/vLLM locais,
    o que permite injetar `httpx.MockTransport` nos testes (zero I/O real).
    """

    def __init__(
        self,
        config: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._transport: httpx.AsyncBaseTransport | None = transport

    # ── Resolução de provedor ──

    def resolve_provider(self, role: str | None = None) -> ProviderName:
        """Provedor efetivo: override por papel > PRIMARY_PROVIDER."""
        if role is not None:
            override = self._role_override(role)
            if override is not None:
                return override
        return self._config.PRIMARY_PROVIDER

    def _role_override(self, role: str) -> ProviderName | None:
        normalized = role.strip().lower()
        overrides: dict[str, ProviderName | None] = {
            "architect": self._config.ARCHITECT_PROVIDER,
            "securitycoder": self._config.SECURITYCODER_PROVIDER,
            "security_coder": self._config.SECURITYCODER_PROVIDER,
            "productstrategist": self._config.PRODUCTSTRATEGIST_PROVIDER,
            "product_strategist": self._config.PRODUCTSTRATEGIST_PROVIDER,
        }
        return overrides.get(normalized)

    def _provider_chain(self, role: str | None = None) -> list[ProviderName]:
        """Cadeia de tentativa: [primário, fallback] (sem duplicados)."""
        primary = self.resolve_provider(role)
        fallback = self._config.FALLBACK_PROVIDER
        if fallback == primary:
            return [primary]
        return [primary, fallback]

    # ── Interface pública ──

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        role: str | None = None,
    ) -> str:
        """Texto bruto do modelo, com fallback automático entre provedores."""
        chain = self._provider_chain(role)
        last_error: LLMProviderError | None = None

        for index, provider in enumerate(chain):
            try:
                return await self._call_provider(provider, system_prompt, user_prompt, model)
            except LLMProviderError as exc:
                last_error = exc
                is_last = index == len(chain) - 1
                if not is_last:
                    console.print(
                        f"[yellow]⚠  Provedor '{provider}' falhou ({exc.kind.value}). "
                        f"Ativando fallback '{chain[index + 1]}'...[/yellow]"
                    )

        if last_error is None:  # pragma: no cover — defensivo
            raise LLMProviderError(
                "Nenhum provedor LLM disponível.",
                kind=LLMErrorKind.UNAVAILABLE,
            )
        raise last_error

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        """Texto do modelo parseado como JSON (com limpeza de markdown)."""
        raw = await self.complete(system_prompt, user_prompt, model, role)
        cleaned = _clean_json(raw)
        try:
            parsed: dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError:
            raise LLMProviderError(
                f"Modelo não retornou JSON válido.\nConteúdo recebido: {cleaned[:200]}",
                kind=LLMErrorKind.INVALID_JSON,
            ) from None
        if not isinstance(parsed, dict):
            raise LLMProviderError(
                f"JSON retornado não é um objeto: {cleaned[:200]}",
                kind=LLMErrorKind.INVALID_JSON,
            )
        return parsed

    # ── Internos ──

    def _http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._config.LLM_TIMEOUT_SECONDS,
            transport=self._transport,
        )

    async def _call_provider(
        self,
        provider: ProviderName,
        system_prompt: str,
        user_prompt: str,
        model: str | None,
    ) -> str:
        api_key = self._config.api_key_for(provider)
        if provider != "local" and not api_key:
            raise LLMProviderError(
                f"Provedor '{provider}' sem API key configurada "
                f"(defina {provider.upper()}_API_KEY no .env).",
                kind=LLMErrorKind.UNAVAILABLE,
            )

        base = self._config.base_url_for(provider).rstrip("/")
        url = f"{base}/chat/completions"
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload: dict[str, Any] = {
            "model": model or self._config.default_model_for(provider),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        try:
            async with self._http_client() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return self._extract_content(provider, response)
        except LLMProviderError:
            raise
        except httpx.ConnectError:
            raise LLMProviderError(
                f"Provedor '{provider}' inacessível em '{base}'.",
                kind=LLMErrorKind.UNAVAILABLE,
            ) from None
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout,
                httpx.TimeoutException):
            raise LLMProviderError(
                f"Inferência em '{provider}' excedeu "
                f"{self._config.LLM_TIMEOUT_SECONDS}s.",
                kind=LLMErrorKind.TIMEOUT,
            ) from None
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Provedor '{provider}' retornou HTTP {exc.response.status_code}.",
                kind=LLMErrorKind.HTTP_ERROR,
            ) from None
        except Exception as exc:  # defensivo por design: nunca vaza stack trace
            raise LLMProviderError(
                f"Erro inesperado no provedor '{provider}': "
                f"{type(exc).__name__}: {exc}",
                kind=LLMErrorKind.HTTP_ERROR,
            ) from None

    def _extract_content(self, provider: ProviderName, response: httpx.Response) -> str:
        try:
            data: dict[str, Any] = response.json()
            content: str = data["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                f"Resposta malformada do provedor '{provider}'.",
                kind=LLMErrorKind.INVALID_JSON,
            ) from exc
        return content