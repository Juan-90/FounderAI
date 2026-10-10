"""
Tipos compartilhados do subsistema LLM (v5.5.4).

Módulo SEM dependências de llm_client/providers, criado para quebrar o ciclo
de importação (llm_client -> providers -> llm_client). Grafo resultante:
    llm_client -> providers -> llm_types
    llm_client -> llm_types
    providers  -> llm_types
llm_client re-exporta estes símbolos p/ retrocompatibilidade total
(`from backend.core.llm_client import LLMErrorKind` segue válido).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.core.config import ProviderName


class LLMErrorKind(str, Enum):
    UNAVAILABLE  = "UNAVAILABLE"
    TIMEOUT      = "TIMEOUT"
    INVALID_JSON = "INVALID_JSON"
    HTTP_ERROR   = "HTTP_ERROR"
    MISSING_KEY  = "MISSING_KEY"   # v5.5.4 — provider sem API key configurada


class LLMProviderError(Exception):
    def __init__(
        self, message: str, kind: LLMErrorKind, status_code: Optional[int] = None
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code  # v5.5.4: expõe status p/ orquestrador

    def __str__(self) -> str:
        return f"[{self.kind.value}] {super().__str__()}"


@dataclass(frozen=True)
class LLMCallResult:
    content: str
    provider_used: ProviderName
    model_used: str
    fallback_triggered: bool = False
    original_provider: ProviderName | None = None


# Alias p/ compatibilidade com providers/council (VerboseResponse == LLMCallResult)
VerboseResponse = LLMCallResult