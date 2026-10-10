"""
OpenRouterProvider — wrapper sobre a API compatível com OpenAI (v5.5.4).

Endpoint: https://openrouter.ai/api/v1/chat/completions
Headers: Authorization Bearer + HTTP-Referer/X-Title (recomendados).
Importa tipos de backend.core.llm_types (sem ciclo com llm_client).
"""

from __future__ import annotations

import json
from typing import Optional

import httpx

from backend.core.config import Settings, settings
from backend.core.llm_types import (
    LLMErrorKind,
    LLMProviderError,
    VerboseResponse,
)

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "openai/gpt-4o-mini"
_PROVIDER_NAME = "openrouter"


class OpenRouterProvider:
    """Provider OpenRouter via API compatível com OpenAI."""

    name: str = _PROVIDER_NAME

    def __init__(
        self,
        config: Optional[Settings] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._base = _DEFAULT_BASE_URL
        self._timeout = float(self._config.LLM_TIMEOUT_SECONDS)
        self._transport = transport

    def _http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://founderai.local",
            "X-Title": "FounderAI",
        }

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        role: Optional[str] = None,
    ) -> str:
        response = await self.complete_verbose(system_prompt, user_prompt, model, role=role)
        return response.content

    async def complete_verbose(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        role: Optional[str] = None,
    ) -> VerboseResponse:
        if not self._config.OPENROUTER_API_KEY:
            raise LLMProviderError(
                "OPENROUTER_API_KEY não configurada.",
                kind=LLMErrorKind.MISSING_KEY,
            )
        effective_model = model or self._config.OPENROUTER_MODEL or _DEFAULT_MODEL
        body = {
            "model": effective_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        try:
            async with self._http_client() as client:
                resp = await client.post(
                    f"{self._base}/chat/completions",
                    headers=self._headers(),
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"OpenRouter HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                kind=LLMErrorKind.HTTP_ERROR,
                status_code=exc.response.status_code,
            ) from None
        except (httpx.RequestError, json.JSONDecodeError) as exc:
            raise LLMProviderError(
                f"OpenRouter indisponível: {type(exc).__name__}",
                kind=LLMErrorKind.TIMEOUT
                if isinstance(exc, httpx.TimeoutException)
                else LLMErrorKind.HTTP_ERROR,
            ) from None

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                f"OpenRouter retornou payload inesperado: {json.dumps(data)[:200]}",
                kind=LLMErrorKind.INVALID_JSON,
            ) from exc

        return VerboseResponse(
            content=content,
            provider_used=_PROVIDER_NAME,  # type: ignore[arg-type]
            model_used=effective_model,
            fallback_triggered=False,
            original_provider=None,
        )