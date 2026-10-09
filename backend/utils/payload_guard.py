"""
Guardas defensivas de payload LLM (v5.5.2).

Evitam KeyError / ValidateAgentError quando a LLM omite campos esperados:
  • safe_system_prompt(prompts, fallback): acessa dict de prompts com fallback
    seguro (elimina KeyError: 'system_prompt').
  • require_clarified_fields(payload): garante clarified_fields como dict
    (elimina ValidateAgentError por campo omitido).
  • require_list(payload, key): garante lista p/ campos opcionais.

Uso nos agentes (substituição de 1 linha):
  system_prompt = safe_system_prompt(self._prompts)
  clarified     = require_clarified_fields(payload)
"""

from __future__ import annotations

from typing import Any, Mapping

DEFAULT_ARCHITECT_SYSTEM_PROMPT = (
    "Você é o ArchitectAgent do FounderAI. Projete arquiteturas claras, "
    "testáveis e mínimas, em português, sem inventar requisitos."
)

DEFAULT_INTAKE_SYSTEM_PROMPT = (
    "Você é o IdeaIntakeAgent do FounderAI. Normalize a ideia do fundador em "
    "campos claros; não invente informações não fornecidas."
)


def safe_system_prompt(
    prompts: Any, fallback: str = DEFAULT_ARCHITECT_SYSTEM_PROMPT
) -> str:
    """Retorna o system_prompt de um dict/config, com fallback seguro."""
    if isinstance(prompts, Mapping):
        value = prompts.get("system_prompt")
        if isinstance(value, str) and value.strip():
            return value
    if isinstance(prompts, str) and prompts.strip():
        return prompts
    return fallback


def require_clarified_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Garante clarified_fields como dict (vazio se omitido ou inválido)."""
    raw = payload.get("clarified_fields") if isinstance(payload, Mapping) else None
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def require_list(payload: Mapping[str, Any], key: str) -> list[Any]:
    """Garante uma lista p/ campos opcionais (vazia se omitido ou inválido)."""
    raw = payload.get(key) if isinstance(payload, Mapping) else None
    if isinstance(raw, list):
        return raw
    return []


def require_str(payload: Mapping[str, Any], key: str, default: str = "") -> str:
    """Garante str p/ campos opcionais."""
    raw = payload.get(key) if isinstance(payload, Mapping) else None
    if isinstance(raw, str):
        return raw
    return default