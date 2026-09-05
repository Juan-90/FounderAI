"""
tests/unit/test_prompt_loader.py
Suite de testes — Módulo C2: carregamento de prompts externos.

Execução:
    pytest tests/unit/test_prompt_loader.py -v
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core.prompt_loader import (
    _FALLBACK_PROMPTS,
    _PROMPT_FILES,
    _PROMPTS_DIR,
    list_available_prompts,
    load_prompt,
)

from pathlib import Path
from unittest.mock import patch
import pytest


# ─────────────────────────────────────────
# Carregamento dos arquivos reais
# ─────────────────────────────────────────

class TestLoadPromptFromFile:
    def test_architect_loads_from_file(self):
        """Architect deve carregar do arquivo externo."""
        prompt = load_prompt("Architect")
        assert len(prompt) > 50
        assert "ARCHITECT" in prompt
        assert "JSON" in prompt

    def test_security_coder_loads_from_file(self):
        """SecurityCoder deve carregar do arquivo externo."""
        prompt = load_prompt("SecurityCoder")
        assert "SECURITY CODER" in prompt
        assert "VETO" in prompt
        assert "LGPD" in prompt

    def test_generalist_loads_from_file(self):
        """Generalist deve carregar do arquivo externo."""
        prompt = load_prompt("Generalist")
        assert "GENERALIST" in prompt
        assert "mercado" in prompt.lower() or "negócio" in prompt.lower()

    def test_all_jurors_return_non_empty(self):
        """Todos os jurados devem retornar prompts não-vazios."""
        for juror_name in _PROMPT_FILES:
            prompt = load_prompt(juror_name)
            assert isinstance(prompt, str)
            assert len(prompt.strip()) > 0, f"Prompt vazio para {juror_name}"

    def test_prompts_are_distinct(self):
        """Cada jurado deve ter um prompt diferente."""
        prompts = [load_prompt(name) for name in _PROMPT_FILES]
        assert len(set(prompts)) == len(prompts), "Prompts duplicados detectados"

    def test_prompt_files_exist_on_disk(self):
        """Todos os arquivos de prompt devem existir no disco."""
        for juror_name, filename in _PROMPT_FILES.items():
            path = _PROMPTS_DIR / filename
            assert path.exists(), f"Arquivo ausente: {path}"
            assert path.is_file(), f"Não é arquivo: {path}"

    def test_prompt_files_are_readable(self):
        """Todos os arquivos devem ser legíveis como UTF-8."""
        for juror_name, filename in _PROMPT_FILES.items():
            path = _PROMPTS_DIR / filename
            content = path.read_text(encoding="utf-8")
            assert len(content.strip()) > 0


# ─────────────────────────────────────────
# Fallback quando arquivo ausente
# ─────────────────────────────────────────

class TestFallbackBehavior:
    def test_fallback_used_when_file_missing(self, tmp_path):
        """Se o arquivo não existir, deve usar o fallback sem exceção."""
        fake_dir = tmp_path / "prompts_empty"
        fake_dir.mkdir()

        with patch("backend.core.prompt_loader._PROMPTS_DIR", fake_dir):
            prompt = load_prompt("Architect")

        assert prompt == _FALLBACK_PROMPTS["Architect"]
        assert len(prompt) > 0

    def test_fallback_content_is_meaningful(self):
        """Fallbacks devem conter instruções mínimas de papel."""
        for juror_name, fallback in _FALLBACK_PROMPTS.items():
            assert "JSON" in fallback, f"Fallback de {juror_name} não menciona JSON"
            assert len(fallback) > 30


def test_fallback_used_on_oserror(tmp_path):
    """Se a leitura do arquivo lançar OSError, deve acionar o fallback com segurança sem estourar exceção."""
    fake_dir = tmp_path / "prompts"
    fake_dir.mkdir()
    fake_file = fake_dir / _PROMPT_FILES["Generalist"]
    fake_file.write_text("conteudo temporario", encoding="utf-8")

    with patch("backend.core.prompt_loader._PROMPTS_DIR", fake_dir):
        with patch.object(Path, "read_text", side_effect=PermissionError("Acesso negado simulado")):
            prompt = load_prompt("Generalist")
            
            assert prompt == _FALLBACK_PROMPTS["Generalist"]
            assert len(prompt) > 0


# ─────────────────────────────────────────
# Jurado desconhecido
# ─────────────────────────────────────────

class TestUnknownJuror:
    def test_unknown_juror_raises_runtime_error(self):
        """Jurado não mapeado deve lançar RuntimeError."""
        with pytest.raises(RuntimeError, match="não reconhecido"):
            load_prompt("Philosopher")

    def test_empty_juror_name_raises_runtime_error(self):
        """Nome vazio deve lançar RuntimeError."""
        with pytest.raises(RuntimeError):
            load_prompt("")

    def test_case_sensitive_juror_name(self):
        """Nome com case errado deve lançar RuntimeError."""
        with pytest.raises(RuntimeError):
            load_prompt("architect")  # deve ser "Architect"


# ─────────────────────────────────────────
# list_available_prompts
# ─────────────────────────────────────────

class TestListAvailablePrompts:
    def test_returns_all_jurors(self):
        """Deve retornar entrada para todos os jurados."""
        result = list_available_prompts()
        assert set(result.keys()) == set(_PROMPT_FILES.keys())

    def test_status_ok_when_files_exist(self):
        """Status deve ser 'ok' quando arquivos existem."""
        result = list_available_prompts()
        for juror_name, info in result.items():
            assert info["status"] == "ok", (
                f"{juror_name}: esperado 'ok', obtido '{info['status']}'"
            )

    def test_status_fallback_when_files_missing(self, tmp_path):
        """Status deve ser 'fallback' quando arquivos não existem."""
        empty_dir = tmp_path / "empty_prompts"
        empty_dir.mkdir()

        with patch("backend.core.prompt_loader._PROMPTS_DIR", empty_dir):
            result = list_available_prompts()

        for info in result.values():
            assert info["status"] == "fallback"

    def test_each_entry_has_required_keys(self):
        """Cada entrada deve ter file, path e status."""
        result = list_available_prompts()
        for juror_name, info in result.items():
            assert "file" in info, f"'file' ausente em {juror_name}"
            assert "path" in info, f"'path' ausente em {juror_name}"
            assert "status" in info, f"'status' ausente em {juror_name}"