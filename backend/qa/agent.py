"""
QAAgent — Agente de QA do Loop TDD (v4.0 Fase B — Bloco 1).

Usa o LLMClient híbrido (Cloud → Local com fallback) para:
  • generate_tests:  sintetiza suíte pytest quando `test_files` vem vazio;
  • analyze_failure: diagnostica falhas a partir do SandboxOutput;
  • generate_fix:    produz código corrigido (arquivos completos) + patch_summary.

Contrato de saída do LLM: JSON estrito, com 1 retry de correção (padrão C1).
Assincronia: o cliente LLM é async (Awaitable), portanto todos os métodos
públicos do agente são `async def`.
Testabilidade: aceita qualquer cliente compatível via Protocol `LLMJsonClient`.
"""

from __future__ import annotations

from typing import Any, Awaitable, Optional, Protocol

from backend.core.llm_client import LLMClient
from backend.sandbox.models import SandboxOutput

_SYSTEM_QA: str = (
    "Você é o QAAgent do FounderAI, um engenheiro de QA sênior. "
    "Responda SOMENTE com um objeto JSON válido, sem markdown, sem backticks, "
    "sem texto extra."
)

_CLIP_LIMIT: int = 4_000


class QAAgentError(Exception):
    """Falha do QAAgent (JSON inválido após retry ou contrato violado)."""


class LLMJsonClient(Protocol):
    """
    Contrato mínimo de cliente LLM usado pelo QAAgent.

    Retorno `Awaitable[dict[str, Any]]` casa exatamente com o
    `LLMClient.complete_json` (async) e com fakes `async def` de teste.
    """

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        role: str | None = None,
    ) -> Awaitable[dict[str, Any]]: ...


def _as_str_dict(value: object) -> dict[str, str] | None:
    """Converte valor desconhecido em dict[str, str] ou None se inválido."""
    if not isinstance(value, dict):
        return None
    out: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            return None
        out[key] = item
    return out


def _format_files(files: dict[str, str]) -> str:
    if not files:
        return "(nenhum arquivo)"
    blocks = [f"--- {path} ---\n{content}" for path, content in files.items()]
    return "\n\n".join(blocks)


def _clip(text: str, limit: int = _CLIP_LIMIT) -> str:
    return text if len(text) <= limit else text[:limit] + "\n[...truncado...]"


class QAAgent:
    """Geração de testes, diagnóstico de falhas e síntese de patches."""

    def __init__(self, client: LLMJsonClient | None = None) -> None:
        self._client: LLMJsonClient = client if client is not None else LLMClient()

    # ── Interno: JSON estrito com 1 retry de correção (padrão C1) ──
    async def _call_json(self, user_prompt: str) -> dict[str, Any]:
        try:
            return await self._client.complete_json(
                system_prompt=_SYSTEM_QA, user_prompt=user_prompt
            )
        except Exception as first_error:
            correction = (
                "Sua resposta anterior não atendeu ao contrato JSON:\n"
                f"{first_error}\n\n"
                "Regras obrigatórias:\n"
                "  - Responda APENAS um objeto JSON válido\n"
                "  - Sem markdown, sem backticks, sem comentários\n\n"
                f"Pedido original:\n{user_prompt}"
            )
            return await self._client.complete_json(
                system_prompt=_SYSTEM_QA, user_prompt=correction
            )

    # ── Interface pública (async) ──
    async def generate_tests(
        self,
        source_files: dict[str, str],
        goal: Optional[str] = None,
    ) -> dict[str, str]:
        """Gera uma suíte pytest determinística para o código-fonte."""
        goal_line = f"\nINTENÇÃO DECLARADA: {goal}\n" if goal else "\n"
        user = (
            "Gere uma suíte de testes Pytest enxuta e determinística para o código abaixo.\n"
            f"{goal_line}\n"
            f"ARQUIVOS DE CÓDIGO:\n{_format_files(source_files)}\n\n"
            'Formato da resposta: {"files": {"test_main.py": "<conteúdo completo>"}}\n'
            "Regras: imports compatíveis com os módulos listados; sem rede; sem I/O externo."
        )
        data = await self._call_json(user)
        files = _as_str_dict(data.get("files"))
        if not files:
            raise QAAgentError("generate_tests: LLM não retornou {'files': {...}} válido.")
        return files

    async def analyze_failure(
        self,
        source_files: dict[str, str],
        test_files: dict[str, str],
        sandbox_result: SandboxOutput,
    ) -> str:
        """Diagnóstico objetivo a partir de stdout/stderr/exit_code."""
        user = (
            "Analise a falha de execução abaixo e produza um diagnóstico objetivo.\n\n"
            f"EXIT CODE: {sandbox_result.exit_code}\n"
            f"TIMED OUT: {sandbox_result.timed_out}\n"
            f"STDOUT:\n{_clip(sandbox_result.stdout)}\n\n"
            f"STDERR:\n{_clip(sandbox_result.stderr)}\n\n"
            f"CÓDIGO:\n{_format_files(source_files)}\n\n"
            f"TESTES:\n{_format_files(test_files)}\n\n"
            'Formato da resposta: {"analysis": "<diagnóstico em até 500 caracteres>"}'
        )
        data = await self._call_json(user)
        analysis = data.get("analysis")
        if not isinstance(analysis, str) or not analysis.strip():
            raise QAAgentError("analyze_failure: LLM não retornou {'analysis': str} válido.")
        return analysis[:500]

    async def generate_fix(
        self,
        source_files: dict[str, str],
        test_files: dict[str, str],
        analysis: str,
    ) -> tuple[dict[str, str], dict[str, str], str]:
        """
        Produz (source_corrigido, testes_ajustados, patch_summary).

        Retorna arquivos COMPLETOS; ausências no JSON do LLM preservam os
        arquivos originais (falha de contrato nunca apaga código).
        """
        user = (
            "Corrija o código para que os testes passem.\n\n"
            f"DIAGNÓSTICO: {analysis}\n\n"
            f"CÓDIGO ATUAL:\n{_format_files(source_files)}\n\n"
            f"TESTES ATUAIS:\n{_format_files(test_files)}\n\n"
            'Formato da resposta: {"source_files": {caminho: conteudo}, '
            '"test_files": {caminho: conteudo}, "patch_summary": "<resumo>"}\n'
            "Regras: retorne os arquivos COMPLETOS alterados (ou os originais se intactos); "
            "os testes são a especificação — só os altere se a falha estiver no próprio teste."
        )
        data = await self._call_json(user)
        new_source = _as_str_dict(data.get("source_files")) or dict(source_files)
        new_tests = _as_str_dict(data.get("test_files")) or dict(test_files)
        summary = data.get("patch_summary")
        patch_summary = (
            summary
            if isinstance(summary, str) and summary.strip()
            else "Patch sem resumo fornecido."
        )
        return new_source, new_tests, patch_summary