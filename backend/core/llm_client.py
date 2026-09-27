"""
LLM Client — FounderAI v4.0 final.

Wrapper assíncrono agnóstico a provedor:
  • Cloud: groq | openrouter | openai (APIs compatíveis com OpenAI);
  • Local: ollama / vLLM expostos via endpoint OpenAI-compatible;
  • Fallback automático Cloud → Local em qualquer falha de API;
  • Overrides por papel (Architect, SecurityCoder, ProductStrategist);
  • Modelos customizáveis por provedor (GROQ_MODEL, etc.);
  • Observabilidade: `complete_verbose` retorna `LLMCallResult`;
  • Parse de JSON robusto com sanitização + reparo de JSON truncado (v4.0);
  • max_tokens=2048 em Cloud para evitar truncamento em respostas longas;
  • Tratamento defensivo global: nunca expõe stack trace (LLMProviderError).

Retrocompatibilidade Fase 1:
  • `call_ollama_json`, `LLMErrorKind`, `LLMProviderError` e aliases mantidos.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
from rich.console import Console

from backend.core.config import ProviderName, Settings, settings

console = Console(stderr=True)

# Limite de tokens de saída para provedores Cloud. Suficiente para geração
# de suítes de teste e patches no TDDLoop sem ser cortado pelo provider.
_CLOUD_MAX_TOKENS: int = 2048

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
# Fase 3 (Bloco 2) — Resultado com metadados de observabilidade
# ─────────────────────────────────────────

@dataclass(frozen=True)
class LLMCallResult:
    """
    Resultado de uma chamada ao LLM com metadados de observabilidade.

    Captura o provedor/modelo efetivamente usados e se houve fallback,
    permitindo rastreamento na CLI e persistência no histórico.
    """
    content: str
    provider_used: ProviderName
    model_used: str
    fallback_triggered: bool = False
    original_provider: ProviderName | None = None


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

# Regex para extrair o primeiro objeto JSON de um texto misto (último recurso)
_JSON_OBJECT_RE = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\}", re.DOTALL)


def _resolve_url() -> str:
    base = settings.ollama_base_url.rstrip("/").removesuffix("/v1")
    return f"{base}/api/generate"


def _clean_json(raw: str) -> str:
    """Remove fences ```json ... ``` (legado)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    return raw


def _sanitize_json_for_parse(raw: str) -> str:
    """
    Sanitização agressiva de respostas de LLM antes do json.loads.

    Tolerâncias implementadas (v4.0):
      1. BOM UTF-8;
      2. Fences de markdown na abertura e no fechamento;
      3. Blocos aninhados de aspas triplas (duplas ou simples), que modelos
         pequenos costumam injetar em valores de string — removidos antes do parse;
      4. Comentários de linha no início de linhas (hash Python e barras JS);
      5. Texto espúrio antes/depois do JSON — extração do primeiro objeto via regex.
    """
    text = raw

    # 1. BOM
    if text.startswith("\ufeff"):
        text = text[1:]

    # 2. Fences markdown (abertura e fechamento)
    text = re.sub(r"^\s*```(?:json|JSON)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```\s*$", "", text)

    # 3. Blocos de aspas triplas aninhados (duplas ou simples)
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    text = re.sub(r"'''[\s\S]*?'''", "", text)

    # 4. Comentários de linha no início de linhas
    text = re.sub(r"^\s*#.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)

    text = text.strip()

    # 5. Se ainda não começa com '{' ou '[', extrai o primeiro objeto JSON
    if text and not text.startswith(("{", "[")):
        match = _JSON_OBJECT_RE.search(text)
        if match:
            text = match.group(0)

    return text


def _try_repair_truncated_json(raw: str) -> str | None:
    """
    Tenta reparar um JSON truncado (cortado no meio por max_tokens).

    Algoritmo (state machine):
      - Percorre char a char rastreando se está dentro de uma string
        (respeitando escapes \\");
      - Mantém pilha de '{' e '[' abertos;
      - Ao final, fecha a string aberta (se houver) e adiciona os
        fechadores na ordem inversa da pilha;
      - Retorna o JSON reparado APENAS se ele passar em json.loads;
        caso contrário retorna None.

    Usado como último recurso antes de lançar LLMProviderError(INVALID_JSON).
    """
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

    # Construir o reparo
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
# Fase 2/3 — Cliente agnóstico a provedor
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
        """Texto bruto do modelo, com fallback automático (retrocompatível)."""
        result = await self.complete_verbose(system_prompt, user_prompt, model, role)
        return result.content

    async def complete_verbose(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        role: str | None = None,
    ) -> LLMCallResult:
        """
        Igual a `complete`, mas retorna `LLMCallResult` com metadados de
        observabilidade (provedor/modelo usados e fallback disparado).
        """
        chain = self._provider_chain(role)
        original_provider: ProviderName = chain[0]
        last_error: LLMProviderError | None = None

        for index, provider in enumerate(chain):
            try:
                content, model_used = await self._call_provider_verbose(
                    provider, system_prompt, user_prompt, model
                )
                triggered = provider != original_provider
                return LLMCallResult(
                    content=content,
                    provider_used=provider,
                    model_used=model_used,
                    fallback_triggered=triggered,
                    original_provider=original_provider if triggered else None,
                )
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
        """
        Texto do modelo parseado como JSON.

        Robusto (v4.0): aplica sanitização agressiva, e em caso de falha
        tenta REPARO de JSON truncado (_try_repair_truncated_json) —
        fecha strings/chaves/colchetes abertos para resgatar respostas
        cortadas por max_tokens em provedores Cloud.
        """
        raw = await self.complete(system_prompt, user_prompt, model, role)
        cleaned = _sanitize_json_for_parse(_clean_json(raw))
        try:
            parsed: dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError:
            # Resgate: tenta reparar JSON truncado (v4.0)
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

    # ── Internos ──

    def _http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._config.LLM_TIMEOUT_SECONDS,
            transport=self._transport,
        )

    async def _call_provider_verbose(
        self,
        provider: ProviderName,
        system_prompt: str,
        user_prompt: str,
        model: str | None,
    ) -> tuple[str, str]:
        """Chama um provedor e retorna (conteúdo, modelo_efetivamente_usado)."""
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
        payload: dict[str, Any] = {
            "model": effective_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        # Evita truncamento por max_tokens em provedores Cloud.
        # Ollama não tem limite baixo default e usa sintaxe diferente
        # (options.num_predict), então aplicamos apenas em Cloud.
        if provider != "local":
            payload["max_tokens"] = _CLOUD_MAX_TOKENS
        if provider == "local":
            payload["stream"] = False

        try:
            async with self._http_client() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                content = self._extract_content(provider, response)
                return content, effective_model
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
            hint = ""
            if provider == "groq" and exc.response.status_code == 404:
                hint = (
                    f"\nDica: 404 no Groq geralmente indica modelo '{effective_model}' "
                    f"não disponível na sua conta. Defina GROQ_MODEL no .env "
                    "com um identificador do seu catálogo ativo."
                )
            raise LLMProviderError(
                f"Provedor '{provider}' retornou HTTP {exc.response.status_code}.{hint}",
                kind=LLMErrorKind.HTTP_ERROR,
            ) from None
        except Exception as exc:  # defensivo por design: nunca vaza stack trace
            raise LLMProviderError(
                f"Erro inesperado no provedor '{provider}': "
                f"{type(exc).__name__}: {exc}",
                kind=LLMErrorKind.HTTP_ERROR,
            ) from None

    def _extract_content(self, provider: ProviderName, response: httpx.Response) -> str:
        """
        Extrai o conteúdo da resposta LLM.

        Aceita ambos os formatos (defensivo por design):
          • OpenAI-compatible: {"choices": [{"message": {"content": ...}}]}
          • Ollama nativo:     {"message": {"content": ...}}
        Mantém compatibilidade com mocks (OpenAI-format) e com Ollama real
        via /api/chat (formato nativo).
        """
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