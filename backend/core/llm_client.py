"""
LLM Client — Wrapper assíncrono para o Ollama local.
Sprint 3: Exceção unificada LLMProviderError para todos os erros de inferência.

Localização: backend/core/llm_client.py
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

import httpx
from rich.console import Console

from backend.core.config import settings

console = Console(stderr=True)


# ─────────────────────────────────────────
# Exceções
# ─────────────────────────────────────────

class LLMErrorKind(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT     = "TIMEOUT"
    INVALID_JSON = "INVALID_JSON"
    HTTP_ERROR  = "HTTP_ERROR"


class LLMProviderError(Exception):
    """
    Exceção unificada para erros do provedor LLM (Ollama).
    Carrega kind para permitir tratamento diferenciado no chamador.
    """

    def __init__(self, message: str, kind: LLMErrorKind) -> None:
        super().__init__(message)
        self.kind = kind

    def __str__(self) -> str:
        return f"[{self.kind.value}] {super().__str__()}"


# Aliases para retrocompatibilidade com council.py (Sprint 2)
OllamaUnavailableError  = LLMProviderError
OllamaTimeoutError      = LLMProviderError
OllamaInvalidResponseError = LLMProviderError


# ─────────────────────────────────────────
# Schema JSON obrigatório
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
        lines = raw.splitlines()
        raw = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()
    return raw


async def _stream(url: str, payload: dict[str, Any], timeout: float) -> str:
    """Executa streaming e acumula tokens."""
    tokens: list[str] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                data: dict = json.loads(line)
                if token := data.get("response"):
                    tokens.append(token)
                if data.get("done"):
                    break
    return "".join(tokens).strip()


# ─────────────────────────────────────────
# Interface pública
# ─────────────────────────────────────────

async def call_ollama_json(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Chama o Ollama via /api/generate com streaming.
    1 retry automático em falhas transitórias.

    Raises:
        LLMProviderError: Para qualquer falha — conexão, timeout ou JSON inválido.
                          Inspecione .kind para tratamento diferenciado.
    """
    target_model: str = model or settings.council_model
    timeout: float = settings.ollama_timeout
    url: str = _resolve_url()

    payload: dict[str, Any] = {
        "model": target_model,
        "prompt": system_prompt + "\n\n" + _JUROR_JSON_SCHEMA + "\n\n" + user_prompt,
        "stream": True,
        "options": {"temperature": 0.2, "num_ctx": 2048},
    }

    last_error: LLMProviderError | None = None

    for attempt in range(1, 3):
        try:
            raw = await _stream(url, payload, timeout)
            raw = _clean_json(raw)

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                raise LLMProviderError(
                    f"Modelo '{target_model}' não retornou JSON válido.\n"
                    f"Conteúdo recebido: {raw[:300]}",
                    kind=LLMErrorKind.INVALID_JSON,
                )

        except LLMProviderError as e:
            if e.kind == LLMErrorKind.INVALID_JSON:
                raise  # JSON inválido não se recupera com retry
            last_error = e
            if attempt == 1:
                console.print(
                    f"[yellow]⚠ Tentativa {attempt} falhou "
                    f"({e.kind.value}). Retentando...[/yellow]"
                )

        except httpx.ConnectError:
            last_error = LLMProviderError(
                f"Ollama não está acessível em '{settings.ollama_base_url}'.\n"
                "Inicie com: docker compose -f docker/docker-compose.yml up -d ollama",
                kind=LLMErrorKind.UNAVAILABLE,
            )
            if attempt == 1:
                console.print("[yellow]⚠ Tentativa 1 falhou (conexão). Retentando...[/yellow]")

        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout):
            last_error = LLMProviderError(
                f"Inferência com '{target_model}' excedeu {timeout}s.\n"
                "Dica: aumente OLLAMA_TIMEOUT no .env ou use um modelo menor (gemma2:2b).",
                kind=LLMErrorKind.TIMEOUT,
            )
            if attempt == 1:
                console.print("[yellow]⚠ Tentativa 1 falhou (timeout). Retentando...[/yellow]")

        except httpx.HTTPStatusError as e:
            raise LLMProviderError(
                f"Ollama retornou HTTP {e.response.status_code}.\n"
                f"Verifique se o modelo '{target_model}' está disponível: "
                "docker exec founderai-ollama ollama list",
                kind=LLMErrorKind.HTTP_ERROR,
            )

    raise last_error  # type: ignore[misc]