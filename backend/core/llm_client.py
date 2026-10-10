"""
LLM Client — FounderAI v4.3.0 (resiliência: retry/backoff + resposta vazia=fallback).

Novidades deste hotfix:
  • Retry com backoff exponencial para HTTP transitório (429/500/502/503/504)
    ANTES de ativar o fallback de provedor (mitiga rate-limit do Groq).
  • Resposta com content vazio é tratada como erro de provider (INVALID_JSON),
    triggerando o fallback para o próximo da cadeia (antes retornava "" e
    quebrava o complete_json sem fallback).
  • Timeout por provedor: local usa LLM_LOCAL_TIMEOUT_SECONDS (>=120s, default 180s).
  • Log detalhado de TODOS os provedores quando a cadeia inteira falha.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

import httpx
from rich.console import Console

from backend.core.config import ProviderName, Settings, settings
from backend.utils.retry_policy import backoff_seconds

console = Console(stderr=True)

_CLOUD_MAX_TOKENS: int = 2048

# Status HTTP transitórios que merecem retry com backoff (rate-limit/indisponibilidade)
_RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})


class LLMErrorKind(str, Enum):
    UNAVAILABLE  = "UNAVAILABLE"
    TIMEOUT      = "TIMEOUT"
    INVALID_JSON = "INVALID_JSON"
    HTTP_ERROR   = "HTTP_ERROR"


class LLMProviderError(Exception):
    def __init__(self, message: str, kind: LLMErrorKind) -> None:
        super().__init__(message)
        self.kind = kind

    def __str__(self) -> str:
        return f"[{self.kind.value}] {super().__str__()}"


OllamaUnavailableError   = LLMProviderError
OllamaTimeoutError       = LLMProviderError
OllamaInvalidResponseError = LLMProviderError


@dataclass(frozen=True)
class LLMCallResult:
    content: str
    provider_used: ProviderName
    model_used: str
    fallback_triggered: bool = False
    original_provider: ProviderName | None = None


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

_JSON_OBJECT_RE = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\}", re.DOTALL)


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


def _sanitize_json_for_parse(raw: str) -> str:
    """Sanitização agressiva (BOM, fences, aspas triplas, comentários, extração)."""
    text = raw
    if text.startswith("\ufeff"):
        text = text[1:]
    text = re.sub(r"^\s*```(?:json|JSON)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```\s*$", "", text)
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    text = re.sub(r"'''[\s\S]*?'''", "", text)
    text = re.sub(r"^\s*#.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    text = text.strip()
    if text and not text.startswith(("{", "[")):
        match = _JSON_OBJECT_RE.search(text)
        if match:
            text = match.group(0)
    return text


def _try_repair_truncated_json(raw: str) -> str | None:
    """Repara JSON truncado fechando strings/chaves/colchetes abertos."""
    if not raw or not raw.lstrip().startswith(("{", "[")):
        return None
    in_string = False
    escape = False
    stack: list[str] = []
    for char in raw:
        if escape:
            escape = False
            continue
        if in_string:
            if char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif char == "]":
            if stack and stack[-1] == "[":
                stack.pop()
    repair = raw
    if in_string:
        repair += '"'
    for opener in reversed(stack):
        repair += "}" if opener == "{" else "]"
    try:
        json.loads(repair)
        return repair
    except json.JSONDecodeError:
        return None


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


async def call_ollama_json(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    target_model: str = model or settings.council_model
    timeout: float = settings.ollama_timeout
    url: str = _resolve_url()
    payload: dict[str, Any] = {
        "model": target_model,
        "prompt": (system_prompt + "\n\n" + _JUROR_JSON_SCHEMA + "\n\n" + user_prompt),
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
                console.print(f"[yellow]⚠  Tentativa {attempt} falhou ({e.kind.value}). Retentando...[/yellow]")
        except httpx.ConnectError:
            last_error = LLMProviderError(
                f"Ollama não está acessível em '{settings.ollama_base_url}' (conexão recusada).",
                kind=LLMErrorKind.UNAVAILABLE,
            )
            if attempt == 1:
                console.print("[yellow]⚠  Tentativa 1 falhou (conexão). Retentando...[/yellow]")
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout, httpx.TimeoutException):
            last_error = LLMProviderError(
                f"Inferência com '{target_model}' excedeu {timeout}s (timeout).",
                kind=LLMErrorKind.TIMEOUT,
            )
            if attempt == 1:
                console.print("[yellow]⚠  Tentativa 1 falhou (timeout). Retentando...[/yellow]")
        except httpx.HTTPStatusError as e:
            raise LLMProviderError(
                f"Ollama retornou HTTP {e.response.status_code}.",
                kind=LLMErrorKind.HTTP_ERROR,
            )
        except Exception as e:
            raise LLMProviderError(
                f"Erro inesperado na chamada ao Ollama: {type(e).__name__}: {e}",
                kind=LLMErrorKind.HTTP_ERROR,
            )
    if last_error is None:
        raise LLMProviderError("Falha desconhecida ao chamar o Ollama.", kind=LLMErrorKind.UNAVAILABLE)
    raise last_error


class LLMClient:
    """Cliente LLM agnóstico com fallback, retry/backoff e diagnósticos."""

    def __init__(
        self,
        config: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._transport: httpx.AsyncBaseTransport | None = transport

    def resolve_provider(self, role: str | None = None) -> ProviderName:
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
        primary = self.resolve_provider(role)
        fallback = self._config.FALLBACK_PROVIDER
        if fallback == primary:
            return [primary]
        return [primary, fallback]

    async def complete(self, system_prompt, user_prompt, model=None, role=None) -> str:
        result = await self.complete_verbose(system_prompt, user_prompt, model, role)
        return result.content

    async def complete_verbose(self, system_prompt, user_prompt, model=None, role=None) -> LLMCallResult:
        chain = self._provider_chain(role)
        original_provider: ProviderName = chain[0]
        errors: list[tuple[ProviderName, LLMProviderError]] = []

        for index, provider in enumerate(chain):
            try:
                content, model_used = await self._call_provider_verbose(
                    provider, system_prompt, user_prompt, model
                )
                triggered = provider != original_provider
                return LLMCallResult(
                    content=content, provider_used=provider, model_used=model_used,
                    fallback_triggered=triggered,
                    original_provider=original_provider if triggered else None,
                )
            except LLMProviderError as exc:
                errors.append((provider, exc))
                is_last = index == len(chain) - 1
                if not is_last:
                    console.print(
                        f"[yellow]⚠  Provedor '{provider}' falhou ({exc.kind.value}). "
                        f"Ativando fallback '{chain[index + 1]}'...[/yellow]"
                    )

        console.print("[bold red]✗ Todos os provedores falharam:[/bold red]")
        for prov, err in errors:
            console.print(f"   [dim]→[/dim] {prov}: {err}")
        raise errors[-1][1] if errors else LLMProviderError(
            "Nenhum provedor LLM disponível.", kind=LLMErrorKind.UNAVAILABLE
        )

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None) -> dict[str, Any]:
        raw = await self.complete(system_prompt, user_prompt, model, role)
        cleaned = _sanitize_json_for_parse(_clean_json(raw))
        try:
            parsed: dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError:
            repaired = _try_repair_truncated_json(cleaned)
            if repaired is not None:
                parsed = json.loads(repaired)
            else:
                raise LLMProviderError(
                    f"Modelo não retornou JSON válido (nem após reparo).\n"
                    f"Conteúdo recebido: {cleaned[:200]}",
                    kind=LLMErrorKind.INVALID_JSON,
                ) from None
        if not isinstance(parsed, dict):
            raise LLMProviderError(
                f"JSON retornado não é um objeto: {cleaned[:200]}",
                kind=LLMErrorKind.INVALID_JSON,
            )
        return parsed

        # ── Aliases explícitos (v4.4.0) ─────────────────────────────────────────
    # Deixam claro que complete/complete_json JÁ incluem fallback Cloud→Local,
    # retry/backoff em HTTP transitório e timeout por provedor (local ≥ 120s).
    async def complete_with_fallback(
        self, system_prompt, user_prompt, model=None, role=None
    ) -> str:
        return await self.complete(system_prompt, user_prompt, model, role)

    async def complete_json_with_fallback(
        self, system_prompt, user_prompt, model=None, role=None
    ) -> dict[str, Any]:
        return await self.complete_json(system_prompt, user_prompt, model, role)

    def _http_client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self._transport)

    async def _call_provider_verbose(self, provider, system_prompt, user_prompt, model) -> tuple[str, str]:
        api_key = self._config.api_key_for(provider)
        if provider != "local" and not api_key:
            raise LLMProviderError(
                f"Provedor '{provider}' sem API key configurada "
                f"(defina {provider.upper()}_API_KEY no .env).",
                kind=LLMErrorKind.UNAVAILABLE,
            )

        base = self._config.base_url_for(provider).rstrip("/")
        if provider == "local":
            if base.endswith("/v1"):
                base = base[:-3]
            url = f"{base}/api/chat"
        else:
            url = f"{base}/chat/completions"

        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        effective_model = model or self._config.default_model_for(provider)
        timeout = self._config.timeout_for(provider)
        payload: dict[str, Any] = {
            "model": effective_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        if provider != "local":
            payload["max_tokens"] = _CLOUD_MAX_TOKENS
        if provider == "local":
            payload["stream"] = False

        max_retries = self._config.LLM_HTTP_RETRIES
        for attempt in range(max_retries + 1):
            try:
                async with self._http_client(timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    content = self._extract_content(provider, response)
                    if not content.strip():
                        # Resposta vazia = falha do provider → trigger fallback
                        raise LLMProviderError(
                            f"Provedor '{provider}' retornou resposta vazia.",
                            kind=LLMErrorKind.INVALID_JSON,
                        )
                    return content, effective_model

            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if code in _RETRYABLE_STATUS and attempt < max_retries:
                    # v5.5.3: backoff exponencial unificado (base maior p/ 429)
                    delay = backoff_seconds(
                        attempt + 1,
                        status_code=code,
                        base=self._config.LLM_RETRY_BACKOFF_SECONDS,
                    )
                    console.print(
                        f"[yellow]⚠  {provider} HTTP {code} (transiente). "
                        f"Retry {attempt + 1}/{max_retries} em {delay:.1f}s...[/yellow]"
                    )
                    await asyncio.sleep(delay)
                    continue
                hint = ""
                if code == 404:
                    if provider == "local":
                        hint = (
                            f"\nDica: 404 no Ollama = modelo '{effective_model}' não baixado "
                            f"('ollama pull {effective_model}') ou rota inexistente."
                        )
                    else:
                        hint = (
                            f"\nDica: 404 no '{provider}' = modelo '{effective_model}' fora do "
                            f"catálogo da sua chave. Ajuste {provider.upper()}_MODEL no .env."
                        )
                elif code == 429:
                    hint = (
                        f"\nDica: 429 = rate-limit do '{provider}'. Aguarde ou reduza a "
                        "frequência de chamadas; o fallback local será usado."
                    )
                raise LLMProviderError(
                    f"Provedor '{provider}' retornou HTTP {code}.{hint}",
                    kind=LLMErrorKind.HTTP_ERROR,
                ) from None

            except httpx.ConnectError:
                raise LLMProviderError(
                    f"Provedor '{provider}' inacessível em '{base}' "
                    "(conexão recusada / serviço não está ouvindo; "
                    "se for local, verifique se Ollama/Docker estão rodando).",
                    kind=LLMErrorKind.UNAVAILABLE,
                ) from None

            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout, httpx.TimeoutException):
                raise LLMProviderError(
                    f"Inferência em '{provider}' (modelo '{effective_model}') excedeu "
                    f"{timeout}s (timeout). Para código longo, aumente "
                    "LLM_LOCAL_TIMEOUT_SECONDS / LLM_TIMEOUT_SECONDS no .env.",
                    kind=LLMErrorKind.TIMEOUT,
                ) from None

            except LLMProviderError:
                raise  # resposta vazia → propaga para fallback

            except Exception as exc:
                raise LLMProviderError(
                    f"Erro inesperado no provedor '{provider}': {type(exc).__name__}: {exc}",
                    kind=LLMErrorKind.HTTP_ERROR,
                ) from None

        raise LLMProviderError(
            f"Provedor '{provider}' esgotou retries de HTTP transitório.",
            kind=LLMErrorKind.HTTP_ERROR,
        )

    def _extract_content(self, provider: ProviderName, response: httpx.Response) -> str:
        try:
            data: dict[str, Any] = response.json()
            if "choices" in data and data["choices"]:
                content: str = data["choices"][0]["message"]["content"]
            elif "message" in data:
                content = data["message"]["content"]
            else:
                raise LLMProviderError(
                    f"Resposta sem 'choices' ou 'message' do provedor '{provider}'.",
                    kind=LLMErrorKind.INVALID_JSON,
                )
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"Resposta não-JSON do provedor '{provider}'.",
                kind=LLMErrorKind.INVALID_JSON,
            ) from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                f"Resposta malformada do provedor '{provider}'.",
                kind=LLMErrorKind.INVALID_JSON,
            ) from exc
        return content