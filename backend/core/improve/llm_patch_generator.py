"""
LLMPatchGenerator — gerador LLM real para o ImprovePatcher (v5.5.7).

Usa o LLMClient ativo (Groq/OpenRouter/Gemini/Local conforme .env) para
produzir patches de código a partir de um ImprovePlanItem + bundle atual.

Contrato com ImprovePatcher:
  class PatchGenerator(Protocol):
      def generate(self, item: ImprovePlanItem, bundle: dict[str, str]) -> dict[str, str]: ...

Retorna dict[filepath -> new_content] para os arquivos afetados pelo item.
Retorna {} vazio quando o LLM decide que não há mudança (NO_PATCH_GENERATED).

v5.5.7: o parâmetro `client` aceita qualquer objeto que satisfaça o Protocol
  LLMCompleter (duck-typing), permitindo injeção de fakes em testes sem
  quebrar o type-checker.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Protocol, runtime_checkable

from backend.core.llm_client import LLMClient
from backend.domain.improve import ImprovePlanItem

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


@runtime_checkable
class LLMCompleter(Protocol):
    """Contrato mínimo de um cliente LLM (satisfeito por LLMClient e fakes)."""

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        role: Optional[str] = None,
    ) -> str: ...


class PatchGenerator(Protocol):
    def generate(self, item: ImprovePlanItem, bundle: dict[str, str]) -> dict[str, str]: ...


_SYSTEM = (
    "Você é um engenheiro sênior aplicando melhorias cirúrgicas em código Python.\n"
    "Receberá: (1) o item do plano, (2) o conteúdo atual dos arquivos.\n"
    "Responda APENAS com JSON válido, sem fences, com a estrutura:\n"
    '{"files": {"caminho/relativo.py": "conteúdo completo novo"}}\n'
    "Regras:\n"
    "• Retorne APENAS os arquivos que REALMENTE mudam.\n"
    "• Mantenha imports e tipagens existentes; adicione o mínimo necessário.\n"
    "• Nunca invente requisitos além do item.\n"
    "• Se não houver mudança necessária, retorne {\"files\": {}}.\n"
    "• Código em português nos comentários quando o original já estiver."
)


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Extrai o primeiro objeto JSON válido do texto do LLM."""
    raw = raw.strip()
    # tenta direto
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    # tenta regex
    m = _JSON_BLOCK_RE.search(raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


class LLMPatchGenerator:
    """Gerador LLM real para o ImprovePatcher (v5.5.7).

    `client` aceita qualquer LLMCompleter (LLMClient real ou fake de teste).
    Se None, instancia LLMClient() (usa o provider ativo do .env).
    """

    def __init__(self, client: Optional[LLMCompleter] = None) -> None:
        self._client: LLMCompleter = client if client is not None else LLMClient()

    async def generate_async(
        self, item: ImprovePlanItem, bundle: dict[str, str]
    ) -> dict[str, str]:
        """Versão assíncrona (usa LLMClient real com retry/fallback)."""
        relevant = {
            k: v for k, v in bundle.items()
            if any(t in k for t in item.target_files) or not item.target_files
        }
        user = (
            f"ITEM DO PLANO:\n"
            f"  título: {item.title}\n"
            f"  rationale: {item.rationale}\n"
            f"  impacto esperado: {item.expected_impact}\n"
            f"  arquivos-alvo: {item.target_files}\n\n"
            f"CONTEÚDO ATUAL:\n{json.dumps(relevant, indent=2, ensure_ascii=False)}\n\n"
            "Retorne JSON: {\"files\": {\"caminho.py\": \"conteúdo novo\"}}"
        )
        try:
            raw = await self._client.complete(
                system_prompt=_SYSTEM,
                user_prompt=user,
                role="architect",
            )
        except Exception:
            return {}
        parsed = _extract_json(raw)
        if not isinstance(parsed, dict):
            return {}
        files = parsed.get("files")
        if not isinstance(files, dict):
            return {}
        return {str(k): str(v) for k, v in files.items() if isinstance(v, str)}

    def generate(self, item: ImprovePlanItem, bundle: dict[str, str]) -> dict[str, str]:
        """Síncrona (wrapper para o Protocol do ImprovePatcher)."""
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.generate_async(item, bundle))
        # Se já há loop (dentro de pipeline assíncrona), criamos tarefa em thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, self.generate_async(item, bundle))
            return future.result()