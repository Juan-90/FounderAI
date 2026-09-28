"""
StaticAnalysisGate — execução isolada de ruff/mypy sobre arquivos em memória.

Materializa os arquivos em TemporaryDirectory, executa subprocess com timeout,
parseia saídas estruturadas e garante cleanup em finally.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

from backend.analysis.models import StaticAnalysisResult, StaticIssue
from backend.core.config import settings


class StaticAnalysisGate:
    """Gate de análise estática pré-sandbox."""

    def __init__(
        self,
        mypy_enabled: bool | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._mypy_enabled: bool = (
            settings.STATIC_ANALYSIS_MYPY_ENABLED
            if mypy_enabled is None
            else mypy_enabled
        )
        self._timeout: float = (
            settings.STATIC_ANALYSIS_TIMEOUT_SECONDS
            if timeout_seconds is None
            else timeout_seconds
        )

    # ── Helpers ──
    @staticmethod
    def _write_files(root: Path, files: dict[str, str]) -> None:
        for rel, content in files.items():
            rel_path = Path(rel)
            if rel_path.is_absolute() or any(p == ".." for p in rel_path.parts):
                raise ValueError(f"Path traversal bloqueado: {rel}")
            target = root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    @staticmethod
    def _parse_ruff_json(raw: str, root: Path) -> list[StaticIssue]:
        """Parse da saída `ruff check --output-format=json`."""
        if not raw.strip():
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        issues: list[StaticIssue] = []
        if not isinstance(data, list):
            return []
        for item in data:
            if not isinstance(item, dict):
                continue
            filename = item.get("filename") or item.get("file")
            if filename:
                try:
                    filename = str(Path(filename).resolve().relative_to(root.resolve()))
                except (ValueError, OSError):
                    filename = str(filename)
            issues.append(
                StaticIssue(
                    tool="ruff",
                    code=item.get("code"),
                    message=item.get("message", ""),
                    file=filename,
                    line=item.get("location", {}).get("row")
                    if isinstance(item.get("location"), dict)
                    else item.get("line"),
                    severity="error",
                )
            )
        return issues

    @staticmethod
    def _parse_mypy_output(raw: str) -> list[StaticIssue]:
        """Parse da saída `mypy --show-error-codes`."""
        issues: list[StaticIssue] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("Success:"):
                continue
            # Formato: file.py:line: severity: message  [code]
            parts = line.split(":", 3)
            if len(parts) < 4:
                continue
            filename, lineno_str, severity_raw, rest = parts
            try:
                lineno = int(lineno_str.strip())
            except ValueError:
                lineno = None
            severity = "error" if "error" in severity_raw.lower() else "warning"
            # Extrair code entre colchetes no final (ex: " [unused-import]")
            code: str | None = None
            if rest.rstrip().endswith("]"):
                bracket_start = rest.rfind("[")
                if bracket_start != -1:
                    code = rest[bracket_start + 1 : -1].strip()
                    rest = rest[:bracket_start]
            message = rest.strip().lstrip(":").strip()
            issues.append(
                StaticIssue(
                    tool="mypy",
                    code=code,
                    message=message,
                    file=filename.strip(),
                    line=lineno,
                    severity=severity,
                )
            )
        return issues

    def _run_tool(
        self,
        cmd: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )

    # ── Interface pública ──
    def run(self, files: dict[str, str]) -> StaticAnalysisResult:
        """
        Executa análise estática sobre o conjunto de arquivos.

        Returns:
            StaticAnalysisResult com passed=True somente se não houver
            issues de severidade 'error'.
        """
        if not files:
            return StaticAnalysisResult(
                passed=True,
                issues=[],
                ruff_passed=True,
                mypy_passed=True,
                summary="Sem arquivos para analisar.",
            )

        started = time.perf_counter()
        all_issues: list[StaticIssue] = []
        ruff_passed = True
        mypy_passed = True

        with tempfile.TemporaryDirectory(prefix="founderai-static-") as tmp:
            root = Path(tmp)
            try:
                self._write_files(root, files)

                # ── Ruff (sempre) ──
                try:
                    ruff_proc = self._run_tool(
                        ["ruff", "check", "--output-format=json", "."], root
                    )
                    ruff_issues = self._parse_ruff_json(ruff_proc.stdout, root)
                    all_issues.extend(ruff_issues)
                    if ruff_issues:
                        ruff_passed = False
                except FileNotFoundError:
                    all_issues.append(
                        StaticIssue(
                            tool="ruff",
                            code=None,
                            message="ruff não encontrado no PATH. Instale: pip install ruff",
                            file=None,
                            line=None,
                            severity="error",
                        )
                    )
                    ruff_passed = False
                except subprocess.TimeoutExpired:
                    all_issues.append(
                        StaticIssue(
                            tool="ruff",
                            code=None,
                            message=f"ruff excedeu timeout de {self._timeout}s.",
                            file=None,
                            line=None,
                            severity="error",
                        )
                    )
                    ruff_passed = False

                # ── Mypy (se habilitado) ──
                if self._mypy_enabled:
                    try:
                        mypy_proc = self._run_tool(
                            ["mypy", "--ignore-missing-imports", "--show-error-codes", "."],
                            root,
                        )
                        mypy_issues = self._parse_mypy_output(mypy_proc.stdout)
                        all_issues.extend(mypy_issues)
                        if any(i.severity == "error" for i in mypy_issues):
                            mypy_passed = False
                    except FileNotFoundError:
                        all_issues.append(
                            StaticIssue(
                                tool="mypy",
                                code=None,
                                message="mypy não encontrado no PATH. Instale: pip install mypy",
                                file=None,
                                line=None,
                                severity="warning",
                            )
                        )
                    except subprocess.TimeoutExpired:
                        all_issues.append(
                            StaticIssue(
                                tool="mypy",
                                code=None,
                                message=f"mypy excedeu timeout de {self._timeout}s.",
                                file=None,
                                line=None,
                                severity="error",
                            )
                        )
                        mypy_passed = False

            finally:
                # Cleanup é automático via TemporaryDirectory (context manager)
                pass

        duration_ms = int((time.perf_counter() - started) * 1000)
        has_errors = any(i.severity == "error" for i in all_issues)
        error_count = sum(1 for i in all_issues if i.severity == "error")
        warn_count = sum(1 for i in all_issues if i.severity == "warning")

        summary = (
            f"{len(all_issues)} issue(s): {error_count} erro(s), {warn_count} aviso(s). "
            f"ruff={'OK' if ruff_passed else 'FALHOU'}, "
            f"mypy={'OK' if mypy_passed else 'FALHOU'}."
            if all_issues
            else "Análise estática passou sem issues."
        )

        return StaticAnalysisResult(
            passed=not has_errors and ruff_passed and mypy_passed,
            issues=all_issues,
            ruff_passed=ruff_passed,
            mypy_passed=mypy_passed,
            summary=summary,
            duration_ms=duration_ms,
        )