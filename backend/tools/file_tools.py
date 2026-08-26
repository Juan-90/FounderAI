"""
File Tools — Utilitários seguros para leitura de arquivos do projeto.
Sprint 3: Limites configuráveis de contexto e prepare_context_payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ─────────────────────────────────────────
# Constantes configuráveis
# ─────────────────────────────────────────

MAX_FILE_CHARS: int = 10_000       # Máximo de caracteres por arquivo
MAX_TOTAL_CONTEXT_CHARS: int = 30_000  # Máximo total de contexto injetado

# Pastas ignoradas na listagem
_IGNORED_DIRS: frozenset[str] = frozenset({
    ".venv", "venv", "__pycache__", ".git",
    ".mypy_cache", ".pytest_cache", "node_modules",
    ".ruff_cache", "dist", "build",
})

# Raiz absoluta do projeto
_PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.resolve()


# ─────────────────────────────────────────
# Resultado estruturado do prepare
# ─────────────────────────────────────────

@dataclass
class ContextPayload:
    """Resultado de prepare_context_payload."""
    block: str                          # Bloco de texto pronto para injeção no prompt
    included_files: list[str]           # Arquivos efetivamente incluídos
    truncated_files: list[str]          # Arquivos truncados por MAX_FILE_CHARS
    omitted_files: list[str]            # Arquivos omitidos por MAX_TOTAL_CONTEXT_CHARS
    warnings: list[str] = field(default_factory=list)  # Mensagens de aviso


# ─────────────────────────────────────────
# Segurança
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# Leitura individual
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# Listagem do projeto
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# Payload de contexto com limites
# ─────────────────────────────────────────

def prepare_context_payload(
    file_paths: list[str],
    max_file_chars: int = MAX_FILE_CHARS,
    max_total_chars: int = MAX_TOTAL_CONTEXT_CHARS,
) -> ContextPayload:
    """
    Prepara o bloco de contexto para injeção nos prompts dos jurados.

    Para cada arquivo:
    - Lê até max_file_chars (truncando se necessário).
    - Acumula o total. Se ultrapassar max_total_chars, omite os arquivos seguintes.

    Returns:
        ContextPayload com bloco formatado, listas de incluídos/truncados/omitidos e avisos.
    """
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

        try:
            raw_content = resolved.read_text(encoding="utf-8", errors="replace")
        except (PermissionError, OSError) as e:
            warnings.append(f"Ignorado: '{file_path}' — erro de leitura: {e}")
            omitted.append(file_path)
            continue

        was_truncated = len(raw_content) > max_file_chars
        content = (
            raw_content[:max_file_chars] + "\n[Conteúdo truncado por limite de tamanho]"
            if was_truncated
            else raw_content
        )

        # Verifica se ainda cabe no total
        if total_chars + len(content) > max_total_chars:
            # Tenta incluir o quanto cabe
            remaining = max_total_chars - total_chars
            if remaining > 200:  # Vale incluir parcialmente
                content = (
                    content[:remaining]
                    + "\n[Conteúdo omitido: limite total de contexto atingido]"
                )
                truncated.append(file_path)
                included.append(file_path)
                total_chars = max_total_chars
            else:
                omitted.append(file_path)

            limit_reached = True
            if remaining > 200:
                blocks.append(f"\n[{Path(file_path).name}]:\n{content}\n---")
            warnings.append(
                f"Limite total de {max_total_chars:,} caracteres atingido. "
                f"{len(file_paths) - len(included) - len(omitted)} arquivo(s) omitido(s)."
            )
            continue

        total_chars += len(content)
        included.append(file_path)
        if was_truncated:
            truncated.append(file_path)
            warnings.append(
                f"'{Path(file_path).name}' truncado em {max_file_chars:,} caracteres."
            )

        blocks.append(f"\n[{Path(file_path).name}]:\n{content}\n---")

    if omitted and not limit_reached:
        # Omitidos por erro, não por limite
        pass

    block = "\n".join(blocks) if len(blocks) > 1 else ""

    return ContextPayload(
        block=block,
        included_files=included,
        truncated_files=truncated,
        omitted_files=omitted,
        warnings=warnings,
    )


# ─────────────────────────────────────────
# Retrocompatibilidade (Sprint 2)
# ─────────────────────────────────────────

def build_context_block(file_paths: list[str], max_chars_per_file: int = MAX_FILE_CHARS) -> str:
    """Wrapper de retrocompatibilidade. Prefer prepare_context_payload."""
    if not file_paths:
        return ""
    payload = prepare_context_payload(file_paths, max_file_chars=max_chars_per_file)
    return payload.block