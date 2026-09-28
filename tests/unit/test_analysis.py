"""
Testes do Pre-Sandbox Guardrail (v4.1.0 Módulo A).
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock
import subprocess

import pytest

from backend.analysis.models import StaticAnalysisResult, StaticIssue
from backend.analysis.static_gate import StaticAnalysisGate


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────

def test_static_issue_tipos_validos() -> None:
    issue = StaticIssue(
        tool="ruff", code="E501", message="linha muito longa",
        file="main.py", line=42, severity="error",
    )
    assert issue.tool == "ruff"
    assert issue.severity == "error"


def test_static_issue_rejeita_tool_invalido() -> None:
    with pytest.raises(Exception):
        StaticIssue(tool="eslint", message="x", severity="error")  # type: ignore[arg-type]


def test_static_analysis_result_defaults() -> None:
    r = StaticAnalysisResult(passed=True)
    assert r.issues == []
    assert r.ruff_passed is True
    assert r.mypy_passed is True
    assert r.duration_ms == 0


# ─────────────────────────────────────────────────────────────
# Path traversal bloqueado
# ─────────────────────────────────────────────────────────────

def test_path_traversal_bloqueado() -> None:
    gate = StaticAnalysisGate(mypy_enabled=False)
    with pytest.raises(ValueError):
        gate.run({"../evil.py": "print(1)"})


def test_arquivos_vazios_retorna_passed() -> None:
    gate = StaticAnalysisGate(mypy_enabled=False)
    result = gate.run({})
    assert result.passed is True
    assert result.issues == []


# ─────────────────────────────────────────────────────────────
# Parse de saídas
# ─────────────────────────────────────────────────────────────

def test_parse_ruff_json_vazio() -> None:
    from pathlib import Path
    assert StaticAnalysisGate._parse_ruff_json("", Path(".")) == []
    assert StaticAnalysisGate._parse_ruff_json("not-json", Path(".")) == []


def test_parse_ruff_json_com_issues(tmp_path) -> None:
    raw = '[{"filename":"main.py","code":"F401","message":"unused import","location":{"row":3}}]'
    issues = StaticAnalysisGate._parse_ruff_json(raw, tmp_path)
    assert len(issues) == 1
    assert issues[0].tool == "ruff"
    assert issues[0].code == "F401"
    assert issues[0].line == 3


def test_parse_mypy_output_com_code() -> None:
    raw = "main.py:10: error: Name 'x' is not defined  [name-defined]\n"
    issues = StaticAnalysisGate._parse_mypy_output(raw)
    assert len(issues) == 1
    assert issues[0].tool == "mypy"
    assert issues[0].code == "name-defined"
    assert issues[0].severity == "error"
    assert issues[0].line == 10


def test_parse_mypy_warning() -> None:
    raw = "main.py:5: warning: Unused variable\n"
    issues = StaticAnalysisGate._parse_mypy_output(raw)
    assert len(issues) == 1
    assert issues[0].severity == "warning"


# ─────────────────────────────────────────────────────────────
# Execução com mocks (sem I/O real)
# ─────────────────────────────────────────────────────────────

def test_ruff_sem_issues_passa() -> None:
    gate = StaticAnalysisGate(mypy_enabled=False)
    fake_proc = subprocess.CompletedProcess(
        args=["ruff"], returncode=0, stdout="[]", stderr=""
    )
    with patch.object(gate, "_run_tool", return_value=fake_proc):
        result = gate.run({"main.py": "def hello(): pass\n"})
    assert result.passed is True
    assert result.ruff_passed is True
    assert result.issues == []


def test_ruff_com_erro_falha() -> None:
    gate = StaticAnalysisGate(mypy_enabled=False)
    fake_proc = subprocess.CompletedProcess(
        args=["ruff"], returncode=1,
        stdout='[{"filename":"main.py","code":"F401","message":"unused","location":{"row":1}}]',
        stderr="",
    )
    with patch.object(gate, "_run_tool", return_value=fake_proc):
        result = gate.run({"main.py": "import os\n"})
    assert result.passed is False
    assert result.ruff_passed is False
    assert len(result.issues) == 1
    assert result.issues[0].severity == "error"


def test_ruff_nao_encontrado_falha_com_issue() -> None:
    gate = StaticAnalysisGate(mypy_enabled=False)
    with patch.object(gate, "_run_tool", side_effect=FileNotFoundError("ruff not found")):
        result = gate.run({"main.py": "x=1\n"})
    assert result.passed is False
    assert result.ruff_passed is False
    assert any(i.tool == "ruff" and "não encontrado" in i.message for i in result.issues)


def test_mypy_habilitado_e_executado() -> None:
    gate = StaticAnalysisGate(mypy_enabled=True)

    def fake_tool(cmd, cwd):
        if cmd[0] == "ruff":
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if cmd[0] == "mypy":
            return subprocess.CompletedProcess(
                cmd, 0, "Success: no issues found\n", ""
            )
        raise AssertionError(f"Comando inesperado: {cmd}")

    with patch.object(gate, "_run_tool", side_effect=fake_tool):
        result = gate.run({"main.py": "def x() -> int:\n    return 1\n"})
    assert result.passed is True
    assert result.mypy_passed is True