"""
Módulo de Contexto Expandido (Fase 3 — Bloco 1).

Evolui `backend/tools/file_tools.prepare_context_payload` para:
  • Suporte a múltiplos arquivos com priorização;
  • Limites configuráveis via Settings (MAX_FILE_CHARS, MAX_TOTAL_CONTEXT_CHARS);
  • Proteção contra path traversal;
  • Schema Pydantic V2 (ContextPayload) tipado estritamente;
  • Delegação segura para `file_tools` (retrocompatibilidade).

Retrocompatibilidade:
  • `backend/tools/file_tools.ContextPayload` (dataclass) continua funcionando;
  • `backend/tools/file_tools.prepare_context_payload` delega para este módulo.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from backend.core.config import settings
from backend.core.schemas import ContextPayload

if TYPE_CHECKING:
    from collections.abc import Sequence


# ─────────────────────────────────────────────────────────────
# Segurança
# ─────────────────────────────────────────────────────────────

_PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.resolve()


def _is_safe_path(file_path: str) -> tuple[bool, Path]:
    """
    Valida que o caminho está dentro da raiz do projeto.
    Protege contra Path Traversal (../../etc/passwd).
    """
    try:
        resolved = (_PROJECT_ROOT / file_path).resolve()
        return resolved.is_relative_to(_PROJECT_ROOT), resolved
    except Exception:
        return False, Path()


def _read_file_safe(resolved: Path, max_chars: int) -> tuple[str, bool]:
    """
    Lê arquivo com truncamento.

    Returns:
        (conteúdo, foi_truncado)
    """
    try:
        raw = resolved.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, PermissionError, OSError):
        raise

    was_truncated = len(raw) > max_chars
    content = (
        raw[:max_chars] + "\n[Conteúdo truncado por limite de tamanho]"
        if was_truncated
        else raw
    )
    return content, was_truncated


# ─────────────────────────────────────────────────────────────
# Interface pública
# ─────────────────────────────────────────────────────────────

def prepare_context_payload(
    file_paths: Sequence[str],
    max_file_chars: int | None = None,
    max_total_chars: int | None = None,
) -> ContextPayload:
    """
    Prepara o bloco de contexto para injeção nos prompts dos jurados.

    Para cada arquivo:
      1. Valida caminho (path traversal protection);
      2. Lê até `max_file_chars` (truncando se necessário);
      3. Acumula o total; se ultrapassar `max_total_chars`, omite os seguintes.

    Args:
        file_paths: Lista de caminhos relativos à raiz do projeto.
        max_file_chars: Limite por arquivo (default: settings.MAX_FILE_CHARS).
        max_total_chars: Limite total (default: settings.MAX_TOTAL_CONTEXT_CHARS).

    Returns:
        ContextPayload com conteúdo formatado, listas de incluídos/truncados/omitidos
        e avisos.
    """
    max_file_chars = max_file_chars if max_file_chars is not None else settings.MAX_FILE_CHARS
    max_total_chars = max_total_chars if max_total_chars is not None else settings.MAX_TOTAL_CONTEXT_CHARS

    included: list[str] = []
    truncated: list[str] = []
    omitted: list[str] = []
    warnings: list[str] = []
    blocks: list[str] = ["--- CONTEXTO DO PROJETO (Arquivos Anexados) ---"]
    total_chars: int = 0
    limit_reached: bool = False

    for file_path in file_paths:
        if limit_reached:
            omitted.append(file_path)
            continue

        is_safe, resolved = _is_safe_path(file_path)

        # Arquivo inválido ou fora do projeto
        if not is_safe or not resolved.exists():
            warnings.append(f"Ignorado: '{file_path}' — não encontrado ou fora do projeto.")
            omitted.append(file_path)
            continue

        # Tenta ler
        try:
            content, was_truncated = _read_file_safe(resolved, max_file_chars)
        except (FileNotFoundError, PermissionError, OSError) as e:
            warnings.append(f"Ignorado: '{file_path}' — erro de leitura: {e}")
            omitted.append(file_path)
            continue

        # Verifica se ainda cabe no total
        if total_chars + len(content) > max_total_chars:
            remaining = max_total_chars - total_chars
            if remaining > 200:  # Vale incluir parcialmente
                content = (
                    content[:remaining]
                    + "\n[Conteúdo omitido: limite total de contexto atingido]"
                )
                truncated.append(file_path)
                included.append(file_path)
                total_chars = max_total_chars
                blocks.append(f"\n[{Path(file_path).name}]:\n{content}\n---")
                warnings.append(
                    f"Limite total de {max_total_chars:,} caracteres atingido. "
                    f"Arquivos seguintes serão omitidos."
                )
            else:
                omitted.append(file_path)
            limit_reached = True
            continue

        # Cabe no total
        total_chars += len(content)
        included.append(file_path)
        if was_truncated:
            truncated.append(file_path)
            warnings.append(
                f"'{Path(file_path).name}' truncado em {max_file_chars:,} caracteres."
            )
        blocks.append(f"\n[{Path(file_path).name}]:\n{content}\n---")

    formatted_content = "\n".join(blocks) if len(blocks) > 1 else ""

    return ContextPayload(
        included=included,
        truncated=truncated,
        omitted=omitted,
        formatted_content=formatted_content,
        total_chars=total_chars,
        warnings=warnings,
    )