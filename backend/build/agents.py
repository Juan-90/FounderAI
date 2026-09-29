"""
Agentes especializados do Modo BUILD (v4.2 + v4.3 profiles).

Cada agente aceita um `BaseProjectProfile` que define stack, estrutura de
arquivos e prompts específicos (Web/SaaS vs Game 2D). Sem profile, usa
`WebAppProfile` como default (retrocompatível com a v4.2).
"""

from __future__ import annotations

from typing import Any, Protocol

from backend.build.profiles import BaseProjectProfile, WebAppProfile
from backend.core.llm_client import LLMClient


class BuildAgentError(Exception):
    """Falha de contrato de um agente de build (JSON inválido/ausente)."""


class LLMBuildClient(Protocol):
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        role: str | None = None,
    ) -> str: ...

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]: ...


_SYSTEM: str = (
    "Você é um engenheiro de software sênior do FounderAI, construindo um MVP "
    "real e executável. Seja concreto, mínimo e consistente."
)


def _as_str_dict(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            return None
        out[key] = item
    return out


class RequirementsAgent:
    """Transforma a intenção do fundador em requisitos (específicos do profile)."""

    def __init__(
        self,
        client: LLMBuildClient | None = None,
        profile: BaseProjectProfile | None = None,
    ) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()
        self._profile: BaseProjectProfile = profile if profile is not None else WebAppProfile()

    async def generate(self, intent: str) -> str:
        return await self._client.complete(
            system_prompt=_SYSTEM,
            user_prompt=self._profile.requirements_prompt(intent),
        )


class ArchitectureAgent:
    """Define a estrutura do sistema a partir dos requisitos (por profile)."""

    def __init__(
        self,
        client: LLMBuildClient | None = None,
        profile: BaseProjectProfile | None = None,
    ) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()
        self._profile: BaseProjectProfile = profile if profile is not None else WebAppProfile()

    async def generate(self, requirements_md: str) -> str:
        return await self._client.complete(
            system_prompt=_SYSTEM,
            user_prompt=self._profile.architecture_prompt(requirements_md),
        )


class ImplementationAgent:
    """Gera código + testes a partir da arquitetura (por profile)."""

    def __init__(
        self,
        client: LLMBuildClient | None = None,
        profile: BaseProjectProfile | None = None,
    ) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()
        self._profile: BaseProjectProfile = profile if profile is not None else WebAppProfile()

    async def generate(
        self, architecture_md: str
    ) -> tuple[dict[str, str], dict[str, str]]:
        data = await self._client.complete_json(
            system_prompt=_SYSTEM,
            user_prompt=self._profile.implementation_prompt(architecture_md),
        )
        files = _as_str_dict(data.get("files"))
        if not files:
            raise BuildAgentError(
                "ImplementationAgent: LLM não retornou {'files': {...}} válido."
            )
        test_files = _as_str_dict(data.get("test_files")) or {}
        return files, test_files


class BuildReporter:
    """Gera o relatório final report.md (com fallback determinístico)."""

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def generate(self, context: dict[str, Any]) -> str:
        user = (
            "CONTEXTO DA BUILD:\n"
            f"{context}\n\n"
            "Produza um relatório Markdown (report.md) com EXATAMENTE estas seções:\n"
            "# O que foi construído\n# Resultado das Análises e Testes\n"
            "# Limitações\n# Próximos passos\n"
        )
        try:
            return await self._client.complete(system_prompt=_SYSTEM, user_prompt=user)
        except Exception:
            return self._fallback_report(context)

    @staticmethod
    def _fallback_report(context: dict[str, Any]) -> str:
        return (
            "# O que foi construído\n"
            f"Projeto: {context.get('project_name', 'n/a')}\n"
            f"Arquivos: {', '.join(context.get('files', [])) or 'nenhum'}\n\n"
            "# Resultado das Análises e Testes\n"
            f"Gate estático: {'OK' if context.get('static_gate_passed') else 'FALHOU'}\n"
            f"Testes: {'SUCESSO' if context.get('tests_success') else 'FALHA/ESCALADO'}\n\n"
            "# Limitações\n"
            "- Relatório gerado por template (LLM indisponível no estágio de report).\n\n"
            "# Próximos passos\n"
            "- Revisar limitações e iterar na próxima missão.\n"
        )