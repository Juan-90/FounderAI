"""
File Tools — Utilitários seguros para leitura de arquivos do projeto.

Sprint 3: Limites configuráveis de contexto e prepare_context_payload.
Fase 3: Delegação para `backend.core.context` (retrocompatibilidade).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.core.config import settings

# ─────────────────────────────────────────────────────────────
# Constantes configuráveis (retrocompatibilidade Sprint 3)
# ─────────────────────────────────────────────────────────────

MAX_FILE_CHARS: int = settings.MAX_FILE_CHARS
MAX_TOTAL_CONTEXT_CHARS: int = settings.MAX_TOTAL_CONTEXT_CHARS

# Pastas ignoradas na listagem
_IGNORED_DIRS: frozenset[str] = frozenset({
    ".venv", "venv", "__pycache__", ".git",
    ".mypy_cache", ".pytest_cache", "node_modules",
    ".ruff_cache", "dist", "build",
})

# Raiz absoluta do projeto
_PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.resolve()


# ─────────────────────────────────────────────────────────────
# Resultado estruturado do prepare (dataclass legado)
# ─────────────────────────────────────────────────────────────

@dataclass
class ContextPayload:
    """
    Resultado de prepare_context_payload (dataclass legado Sprint 3).

    **Preferência:** use `backend.core.schemas.ContextPayload` (Pydantic V2).
    Esta classe existe apenas para retrocompatibilidade com testes da Fase 1.
    """
    block: str                          # Bloco de texto pronto para injeção no prompt
    included_files: list[str]           # Arquivos efetivamente incluídos
    truncated_files: list[str]          # Arquivos truncados por MAX_FILE_CHARS
    omitted_files: list[str]            # Arquivos omitidos por MAX_TOTAL_CONTEXT_CHARS
    warnings: list[str] = field(default_factory=list)  # Mensagens de aviso


# ─────────────────────────────────────────────────────────────
# Segurança
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# Leitura individual
# ─────────────────────────────────────────────────────────────

def read_project_file(file_path: str, max_chars: int = MAX_FILE_CHARS) -> str:
    """
    Lê o conteúdo de um arquivo com segurança e truncamento.

    Returns:
        Conteúdo do arquivo (truncado se necessário) ou mensagem de erro.
    """
    is_safe, resolved = _is_safe_path(file_path)

    if not is_safe:
        return f"[ERRO] Acesso negado: '{file_path}' está fora da raiz do projeto."

    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return f"[ERRO] Arquivo não encontrado: '{file_path}'"
    except PermissionError:
        return f"[ERRO] Permissão negada ao ler: '{file_path}'"
    except Exception as e:
        return f"[ERRO] Falha ao ler '{file_path}': {e}"

    if len(content) > max_chars:
        content = content[:max_chars] + "\n[Conteúdo truncado por limite de tamanho]"

    return content


# ─────────────────────────────────────────────────────────────
# Listagem do projeto
# ─────────────────────────────────────────────────────────────

def list_project_files(
    base_path: str = ".",
    extensions: list[str] | None = None,
) -> list[str]:
    """Lista arquivos do projeto filtrando pastas de ambiente e cache."""
    if extensions is None:
        extensions = [".md", ".py", ".json"]

    is_safe, resolved_base = _is_safe_path(base_path)
    if not is_safe or not resolved_base.exists():
        return []

    result: list[str] = []
    for path in sorted(resolved_base.rglob("*")):
        if any(part in _IGNORED_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix not in extensions:
            continue
        try:
            result.append(str(path.relative_to(_PROJECT_ROOT)))
        except ValueError:
            continue

    return result


# ─────────────────────────────────────────────────────────────
# Payload de contexto com limites (delega para backend.core.context)
# ─────────────────────────────────────────────────────────────

def prepare_context_payload(
    file_paths: list[str],
    max_file_chars: int = MAX_FILE_CHARS,
    max_total_chars: int = MAX_TOTAL_CONTEXT_CHARS,
) -> ContextPayload:
    """
    Prepara o bloco de contexto para injeção nos prompts dos jurados.

    **Delega para** `backend.core.context.prepare_context_payload` e converte
    o resultado Pydantic V2 para o dataclass legado (retrocompatibilidade).

    Para cada arquivo:
    - Lê até max_file_chars (truncando se necessário).
    - Acumula o total. Se ultrapassar max_total_chars, omite os arquivos seguintes.

    Returns:
        ContextPayload (dataclass) com bloco formatado, listas de
        incluídos/truncados/omitidos e avisos.
    """
    from backend.core.context import prepare_context_payload as _prepare  # noqa: PLC0415

    # Chama a versão Pydantic V2
    result = _prepare(
        file_paths,
        max_file_chars=max_file_chars,
        max_total_chars=max_total_chars,
    )

    # Converte para o dataclass legado (retrocompatibilidade com 121 testes)
    return ContextPayload(
        block=result.formatted_content,
        included_files=result.included,
        truncated_files=result.truncated,
        omitted_files=result.omitted,
        warnings=result.warnings,
    )


# ─────────────────────────────────────────────────────────────
# Retrocompatibilidade (Sprint 2)
# ─────────────────────────────────────────────────────────────

def build_context_block(file_paths: list[str], max_chars_per_file: int = MAX_FILE_CHARS) -> str:
    """Wrapper de retrocompatibilidade. Prefer prepare_context_payload."""
    if not file_paths:
        return ""
    payload = prepare_context_payload(file_paths, max_file_chars=max_chars_per_file)
    return payload.block