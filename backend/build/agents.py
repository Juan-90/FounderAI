"""
Agentes especializados do Modo BUILD (v5.5.2 — system prompt blindado).

v5.5.2: cada agente resolve o system prompt via safe_system_prompt(...), com
fallback para _SYSTEM quando o profile/config expõe um dict SEM a chave
'system_prompt' (elimina KeyError: 'system_prompt' em qualquer origem).

v4.5.0: RequirementsAgent aceita um BuildSeed opcional (contexto pré-validado
do VALIDATE) e injeta escopo MVP recomendado, restrições, riscos a mitigar e
não-objetivos nas instruções de especificação.

Retrocompatibilidade (v4.3): RequirementsAgent SEM profile usa WebAppProfile()
como default, preservando o comportamento e os testes da v4.3.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol

from backend.build.profiles import BaseProjectProfile, WebAppProfile
from backend.core.llm_client import LLMClient
from backend.utils.payload_guard import safe_system_prompt
from backend.validate_and_build.schemas import BuildSeed


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


def _resolve_system(profile: Optional[BaseProjectProfile]) -> str:
    """System prompt com fallback seguro (v5.5.2): nunca KeyError."""
    return safe_system_prompt(getattr(profile, "system_prompt", None), _SYSTEM)


def _as_str_dict(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            return None
        out[key] = item
    return out


def _seed_block(seed: Optional[BuildSeed]) -> str:
    """Bloco de contexto pré-validado a ser injetado no prompt."""
    if seed is None:
        return ""
    return (
        "\n\nCONTEXTO PRÉ-VALIDADO (BuildSeed) — incorpore ao especificar:\n"
        f"- Escopo MVP recomendado: {seed.recommended_mvp_scope or '(não informado)'}\n"
        f"- Restrições: {seed.constraints or '(não informadas)'}\n"
        f"- Riscos a mitigar: {seed.risks_to_mitigate or '(não informados)'}\n"
        f"- Não-objetivos: {seed.non_goals or '(não informados)'}\n"
        "Respeite os não-objetivos e mantenha o escopo dentro do MVP recomendado."
    )


class RequirementsAgent:
    """Transforma a intenção do fundador em requisitos (aceita BuildSeed)."""

    def __init__(
        self,
        client: LLMBuildClient | None = None,
        profile: BaseProjectProfile | None = None,
    ) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()
        self._profile: BaseProjectProfile = (
            profile if profile is not None else WebAppProfile()
        )
        self._system: str = _resolve_system(self._profile)

    async def generate(
        self, intent: str, seed: Optional[BuildSeed] = None
    ) -> str:
        user = self._profile.requirements_prompt(intent) + _seed_block(seed)
        return await self._client.complete(system_prompt=self._system, user_prompt=user)


class ArchitectureAgent:
    """Define a estrutura do sistema a partir dos requisitos."""

    def __init__(
        self,
        client: LLMBuildClient | None = None,
        profile: BaseProjectProfile | None = None,
    ) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()
        self._profile: BaseProjectProfile = (
            profile if profile is not None else WebAppProfile()
        )
        self._system: str = _resolve_system(self._profile)

    async def generate(self, requirements_md: str) -> str:
        user = self._profile.architecture_prompt(requirements_md)
        return await self._client.complete(system_prompt=self._system, user_prompt=user)


class ImplementationAgent:
    """Gera código + testes a partir da arquitetura."""

    def __init__(
        self,
        client: LLMBuildClient | None = None,
        profile: BaseProjectProfile | None = None,
    ) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()
        self._profile: BaseProjectProfile = (
            profile if profile is not None else WebAppProfile()
        )
        self._system: str = _resolve_system(self._profile)

    async def generate(
        self, architecture_md: str
    ) -> tuple[dict[str, str], dict[str, str]]:
        user = self._profile.implementation_prompt(architecture_md)
        data = await self._client.complete_json(system_prompt=self._system, user_prompt=user)
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
        self._system: str = _resolve_system(None)

    async def generate(self, context: dict[str, Any]) -> str:
        user = (
            "CONTEXTO DA BUILD:\n"
            f"{context}\n\n"
            "Produza um relatório Markdown (report.md) com EXATAMENTE estas seções:\n"
            "# O que foi construído\n# Resultado das Análises e Testes\n"
            "# Limitações\n# Próximos passos\n"
        )
        try:
            return await self._client.complete(system_prompt=self._system, user_prompt=user)
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