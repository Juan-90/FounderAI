"""
File Tools — Utilitários seguros para leitura de arquivos do projeto.
Sprint 2: Fornece contexto de arquivos locais para o Conselho Consultivo.
"""

from __future__ import annotations

from pathlib import Path

# Pastas ignoradas na listagem do projeto
_IGNORED_DIRS: frozenset[str] = frozenset({
    ".venv", "venv", "__pycache__", ".git",
    ".mypy_cache", ".pytest_cache", "node_modules",
    ".ruff_cache", "dist", "build",
})

# Raiz absoluta do projeto (pasta onde está este arquivo, subindo 3 níveis)
_PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.resolve()


def _is_safe_path(file_path: str) -> tuple[bool, Path]:
    """
    Valida que o caminho solicitado está dentro da raiz do projeto.
    Retorna (is_safe, resolved_path).
    Protege contra Path Traversal (../../etc/passwd, etc).
    """
    try:
        resolved = (_PROJECT_ROOT / file_path).resolve()
        is_safe = resolved.is_relative_to(_PROJECT_ROOT)
        return is_safe, resolved
    except Exception:
        return False, Path()


def list_project_files(
    base_path: str = ".",
    extensions: list[str] | None = None,
) -> list[str]:
    """
    Lista arquivos do projeto filtrando pastas de ambiente e cache.

    Args:
        base_path: Caminho base relativo à raiz do projeto.
        extensions: Extensões a incluir. Padrão: [".md", ".py", ".json"]

    Returns:
        Lista de caminhos relativos à raiz do projeto.
    """
    if extensions is None:
        extensions = [".md", ".py", ".json"]

    is_safe, resolved_base = _is_safe_path(base_path)
    if not is_safe or not resolved_base.exists():
        return []

    result: list[str] = []

    for path in sorted(resolved_base.rglob("*")):
        # Ignora pastas bloqueadas em qualquer nível da hierarquia
        if any(part in _IGNORED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue

        # Retorna caminho relativo à raiz do projeto
        try:
            result.append(str(path.relative_to(_PROJECT_ROOT)))
        except ValueError:
            continue

    return result


def read_project_file(file_path: str, max_chars: int = 15000) -> str:
    """
    Lê o conteúdo de um arquivo do projeto com segurança.

    Args:
        file_path: Caminho relativo ou absoluto do arquivo.
        max_chars: Limite de caracteres. Conteúdo excedente é truncado.

    Returns:
        Conteúdo do arquivo como string, ou mensagem de erro clara.
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


def build_context_block(file_paths: list[str], max_chars_per_file: int = 15000) -> str:
    """
    Lê múltiplos arquivos e monta o bloco de contexto formatado
    para injeção nos prompts dos jurados.

    Args:
        file_paths: Lista de caminhos relativos ao projeto.
        max_chars_per_file: Limite por arquivo.

    Returns:
        Bloco de texto formatado ou string vazia se não houver arquivos.
    """
    if not file_paths:
        return ""

    blocks: list[str] = ["\n--- CONTEXTO DO PROJETO (Arquivos Anexados) ---"]

    for path in file_paths:
        content = read_project_file(path, max_chars=max_chars_per_file)
        file_name = Path(path).name
        blocks.append(f"\n[{file_name}]:\n{content}\n---")

    return "\n".join(blocks)