"""
Agentes especializados do Modo BUILD (v4.2.0).

Cada agente encapsula uma chamada ao LLMClient com prompt estruturado:
  • RequirementsAgent:    intenção → requirements.md (objetivo, usuários, MVP,
                          restrições, não-objetivos)
  • ArchitectureAgent:    requisitos → architecture.md (stack + arquivos)
  • ImplementationAgent:  arquitetura → files{} + test_files{}
  • BuildReporter:        contexto → report.md (com fallback determinístico)

Testabilidade: aceitam qualquer cliente compatível via Protocol LLMBuildClient.
"""

from __future__ import annotations

from typing import Any, Protocol

from backend.core.llm_client import LLMClient


class BuildAgentError(Exception):
    """Falha de contrato de um agente de build (JSON inválido/ausente)."""


class LLMBuildClient(Protocol):
    """Contrato mínimo de cliente LLM usado pelos agentes de build."""

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
    """Transforma a intenção do fundador em requisitos estruturados."""

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def generate(self, intent: str) -> str:
        user = (
            f"INTENÇÃO DO FUNDADOR:\n{intent}\n\n"
            "Produza um documento Markdown de requisitos com EXATAMENTE estas seções:\n"
            "# Objetivo\n# Usuários\n# MVP\n"
            "  - Serviços\n  - Agendamento\n  - Listagem\n  - Cancelamento\n"
            "# Restrições\n# Não-objetivos\n\n"
            "Seja específico e mínimo (MVP). Não invente escopo fora das seções."
        )
        return await self._client.complete(system_prompt=_SYSTEM, user_prompt=user)


class ArchitectureAgent:
    """Define a estrutura do sistema a partir dos requisitos."""

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def generate(self, requirements_md: str) -> str:
        user = (
            "REQUISITOS:\n"
            f"{requirements_md}\n\n"
            "Produza um documento Markdown de arquitetura com EXATAMENTE estas seções:\n"
            "# Stack\n (use FastAPI + SQLite)\n"
            "# Arquivos Necessários\n"
            "  Liste obrigatoriamente: main.py, models.py, schemas.py, database.py, test_main.py\n"
            "# Responsabilidades por Arquivo\n# Fluxo de Dados\n"
        )
        return await self._client.complete(system_prompt=_SYSTEM, user_prompt=user)


class ImplementationAgent:
    """Gera o código-fonte e os testes a partir da arquitetura."""

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def generate(
        self, architecture_md: str
    ) -> tuple[dict[str, str], dict[str, str]]:
        user = (
            "ARQUITETURA:\n"
            f"{architecture_md}\n\n"
            "Gere o código completo e executável (FastAPI + SQLite) e os testes pytest.\n"
            'Formato da resposta: {"files": {"main.py": "...", ...}, '
            '"test_files": {"test_main.py": "..."}}\n'
            "Regras: código completo (sem trechos), imports coerentes, testes determinísticos."
        )
        data = await self._client.complete_json(system_prompt=_SYSTEM, user_prompt=user)
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