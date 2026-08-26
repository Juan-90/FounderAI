"""
LLM Client — Wrapper assíncrono para o Ollama local.
Sprint 2: Resiliência, retry, exceções customizadas e saída limpa via rich.

Localização: backend/core/llm_client.py
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from rich.console import Console

from backend.core.config import settings

console = Console(stderr=True)


# ─────────────────────────────────────────
# Exceções customizadas
# ─────────────────────────────────────────

class OllamaUnavailableError(Exception):
    """Ollama não está acessível no endereço configurado."""


class OllamaTimeoutError(Exception):
    """A inferência excedeu o tempo limite configurado."""


class OllamaInvalidResponseError(Exception):
    """O modelo não retornou um JSON válido conforme o schema esperado."""


# ─────────────────────────────────────────
# Prompt de schema JSON obrigatório
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

def _build_payload(model: str, prompt: str) -> dict[str, Any]:
    base_url: str = settings.ollama_base_url.rstrip("/").removesuffix("/v1")
    return {
        "url": f"{base_url}/api/generate",
        "payload": {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": 0.2,
                "num_ctx": 2048,
            },
        },
    }


def _clean_json(raw: str) -> str:
    """Remove blocos de markdown que o modelo possa inserir ao redor do JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()
    return raw


async def _stream_generate(url: str, payload: dict[str, Any], timeout: float) -> str:
    """Executa streaming do Ollama e retorna o texto completo acumulado."""
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
    Chama o Ollama via /api/generate com streaming e retorna dict JSON.

    Resiliência:
    - 1 retry automático em falhas transitórias (conexão / timeout)
    - Exceções customizadas sem stack traces assustadores
    - Timeout configurável via settings.ollama_timeout

    Raises:
        OllamaUnavailableError: Ollama não está rodando.
        OllamaTimeoutError: Inferência excedeu o timeout.
        OllamaInvalidResponseError: Resposta não é JSON válido.
    """
    target_model: str = model or settings.council_model
    timeout: float = settings.ollama_timeout

    full_prompt: str = (
        system_prompt
        + "\n\n"
        + _JUROR_JSON_SCHEMA
        + "\n\n"
        + user_prompt
    )

    build = _build_payload(target_model, full_prompt)
    url: str = build["url"]
    payload: dict = build["payload"]

    # ── Tenta até 2 vezes (1 retry) ──────────────────
    last_error: Exception | None = None

    for attempt in range(1, 3):
        try:
            raw: str = await _stream_generate(url, payload, timeout)
            raw = _clean_json(raw)

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                raise OllamaInvalidResponseError(
                    f"O modelo '{target_model}' não retornou JSON válido.\n"
                    f"Conteúdo recebido: {raw[:300]}"
                )

        except OllamaInvalidResponseError:
            raise  # Não faz retry em resposta inválida — é falha do modelo

        except httpx.ConnectError as e:
            last_error = OllamaUnavailableError(
                f"Ollama não está acessível em '{settings.ollama_base_url}'.\n"
                f"Inicie o serviço com: docker compose -f docker/docker-compose.yml up -d ollama"
            )
            if attempt == 1:
                console.print(
                    f"[yellow]⚠ Tentativa {attempt} falhou (conexão). Retentando...[/yellow]"
                )

        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as e:
            last_error = OllamaTimeoutError(
                f"A inferência com '{target_model}' excedeu {timeout}s.\n"
                f"Dica: aumente OLLAMA_TIMEOUT no .env ou use um modelo menor (ex: gemma2:2b)."
            )
            if attempt == 1:
                console.print(
                    f"[yellow]⚠ Tentativa {attempt} falhou (timeout). Retentando...[/yellow]"
                )

        except httpx.HTTPStatusError as e:
            raise OllamaUnavailableError(
                f"Ollama retornou erro HTTP {e.response.status_code}.\n"
                f"Verifique se o modelo '{target_model}' está disponível: "
                f"docker exec founderai-ollama ollama list"
            )

    # Esgotou as tentativas
    raise last_error  # type: ignore[misc]