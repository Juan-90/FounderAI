"""
Testes unitários do módulo de Contexto Expandido (Fase 3 — Bloco 1).

Cobre:
  • Validação de path traversal;
  • Truncamento por arquivo (MAX_FILE_CHARS);
  • Omissão por limite total (MAX_TOTAL_CONTEXT_CHARS);
  • Schema Pydantic V2 (ContextPayload) com aliases retrocompatíveis;
  • Retrocompatibilidade com o dataclass legado de backend.tools.file_tools.

Técnica de isolamento: o fixture `temp_project` monkeypatcha
`backend.core.context._PROJECT_ROOT` para o `tmp_path` do pytest, permitindo
exercitar a guarda anti path-traversal sem tocar no repo real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import backend.core.context as context_module
from backend.core.context import _is_safe_path, prepare_context_payload
from backend.core.schemas import ContextPayload as ContextPayloadPydantic
from backend.tools.file_tools import (
    ContextPayload as ContextPayloadDataclass,
    prepare_context_payload as prepare_legacy,
)


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def temp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Raiz de projeto fake para os testes de leitura.

    Monkeypatcha `_PROJECT_ROOT` (usado por `_is_safe_path`) para o
    diretório temporário do pytest e cria os arquivos de cenário.
    """
    monkeypatch.setattr(context_module, "_PROJECT_ROOT", tmp_path)
    (tmp_path / "small.txt").write_text("conteúdo pequeno", encoding="utf-8")
    (tmp_path / "large.txt").write_text("x" * 20_000, encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.md").write_text("# Nested", encoding="utf-8")
    return tmp_path


# ─────────────────────────────────────────────────────────────
# Segurança (path traversal)
# ─────────────────────────────────────────────────────────────

def test_is_safe_path_rejeita_traversal() -> None:
    """Caminhos que escapam da raiz do projeto são bloqueados."""
    is_safe, _ = _is_safe_path("../../../etc/passwd")
    assert is_safe is False


def test_is_safe_path_aceita_caminho_relativo_valido() -> None:
    """Caminhos relativos à raiz são aceitos (existência não é checada aqui)."""
    is_safe, resolved = _is_safe_path("README.md")
    assert is_safe is True
    assert isinstance(resolved, Path)


def test_prepare_context_payload_rejeita_fora_da_raiz(temp_project: Path) -> None:
    """Mesmo com raiz fake, traversal continua bloqueado."""
    payload = prepare_context_payload(["../fora.txt"])
    assert payload.included == []
    assert "../fora.txt" in payload.omitted


# ─────────────────────────────────────────────────────────────
# Truncamento por arquivo (MAX_FILE_CHARS)
# ─────────────────────────────────────────────────────────────

def test_prepare_context_payload_trunca_arquivo_grande(temp_project: Path) -> None:
    """Arquivos maiores que max_file_chars são incluídos E marcados como truncados."""
    payload = prepare_context_payload(
        ["large.txt"],
        max_file_chars=5_000,
        max_total_chars=50_000,
    )
    assert payload.included == ["large.txt"]
    assert payload.truncated == ["large.txt"]
    assert payload.omitted == []
    assert "truncado" in payload.formatted_content.lower()
    # header do bloco + conteúdo truncado + marcador + rodapé
    assert len(payload.formatted_content) <= 5_000 + 500


def test_prepare_context_payload_inclui_arquivo_pequeno(temp_project: Path) -> None:
    """Arquivos menores que max_file_chars entram intactos."""
    payload = prepare_context_payload(
        ["small.txt"],
        max_file_chars=5_000,
        max_total_chars=50_000,
    )
    assert payload.included == ["small.txt"]
    assert payload.truncated == []
    assert payload.omitted == []
    assert "conteúdo pequeno" in payload.formatted_content
    assert payload.total_chars > 0


# ─────────────────────────────────────────────────────────────
# Limite total (MAX_TOTAL_CONTEXT_CHARS)
# ─────────────────────────────────────────────────────────────

def test_prepare_context_payload_omite_por_limite_total(temp_project: Path) -> None:
    """Ao estourar max_total_chars, inclui parcialmente e omite os seguintes."""
    payload = prepare_context_payload(
        ["large.txt", "large.txt", "large.txt"],
        max_file_chars=5_000,
        max_total_chars=10_000,
    )
    assert len(payload.included) >= 1
    assert len(payload.omitted) >= 1
    assert any("Limite total" in w for w in payload.warnings)
    assert payload.total_chars <= 10_000


# ─────────────────────────────────────────────────────────────
# Schema Pydantic V2 (ContextPayload)
# ─────────────────────────────────────────────────────────────

def test_context_payload_aliases_retrocompativeis(temp_project: Path) -> None:
    """Aliases legados (block/included_files/...) espelham os campos novos."""
    payload = prepare_context_payload(["small.txt"])
    assert isinstance(payload, ContextPayloadPydantic)
    assert payload.block == payload.formatted_content
    assert payload.included_files == payload.included
    assert payload.truncated_files == payload.truncated
    assert payload.omitted_files == payload.omitted


def test_context_payload_summary() -> None:
    """summary() gera a linha de status exibida na CLI."""
    payload = ContextPayloadPydantic(
        included=["a.txt", "b.txt"],
        truncated=["b.txt"],
        omitted=["c.txt"],
    )
    assert payload.summary() == "2 incluído(s), 1 truncado(s), 1 omitido(s)"


# ─────────────────────────────────────────────────────────────
# Retrocompatibilidade com o dataclass legado (file_tools)
# ─────────────────────────────────────────────────────────────

def test_prepare_legacy_retorna_dataclass(temp_project: Path) -> None:
    """file_tools.prepare_context_payload segue retornando o dataclass Sprint 3."""
    result = prepare_legacy(["small.txt"])
    assert isinstance(result, ContextPayloadDataclass)
    assert hasattr(result, "block")
    assert hasattr(result, "included_files")
    assert hasattr(result, "truncated_files")
    assert hasattr(result, "omitted_files")
    assert result.included_files == ["small.txt"]


def test_prepare_legacy_delega_para_core_context(temp_project: Path) -> None:
    """O wrapper legado delega para backend.core.context (bloco não vazio)."""
    result = prepare_legacy(["small.txt"])
    assert result.block  # conteúdo não vazio
    assert "small.txt" in result.block


# ─────────────────────────────────────────────────────────────
# Arquivo inexistente
# ─────────────────────────────────────────────────────────────

def test_prepare_context_payload_arquivo_inexistente() -> None:
    """Arquivos inexistentes são omitidos com warning (sem exceção)."""
    payload = prepare_context_payload(["nao_existe.txt"])
    assert payload.included == []
    assert payload.omitted == ["nao_existe.txt"]
    assert any("não encontrado" in w for w in payload.warnings)