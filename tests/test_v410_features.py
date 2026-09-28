"""
Testes de integração da v4.1.0 (Parte 2).

Cobertura:
  a) Análise estática pega código com erro de sintaxe/import SEM subir Docker;
  b) Telemetria (RAM/CPU) e timeout preservados no SandboxOutput;
  c) Escalation Webhook mockado via httpx + integração com TDDLoop escalado.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any, Optional

import httpx
import pytest

from backend.analysis.models import StaticAnalysisResult, StaticIssue
from backend.analysis.static_gate import StaticAnalysisGate
from backend.core.config import Settings
from backend.notifications.webhook import EscalationNotifier
from backend.qa.agent import QAAgent
from backend.qa.orchestrator import TDDLoop
from backend.qa.schemas import TDDRequest
from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.sandbox.models import SandboxInput, SandboxOutput
from backend.sandbox.runner import SandboxRunner


# ─────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────

class FakeRunner(SandboxRunner):
    def __init__(self, outputs: list[SandboxOutput]) -> None:
        self._outputs = list(outputs)
        self.calls: list[SandboxInput] = []

    def is_available(self) -> bool:
        return True

    def run(self, sbx_input: SandboxInput) -> SandboxOutput:
        self.calls.append(sbx_input)
        if self._outputs:
            return self._outputs.pop(0)
        return SandboxOutput(exit_code=0)


class FakeAgent(QAAgent):
    """QAAgent fake com type hints completos para satisfazer LSP."""

    def __init__(self, fixed_source: dict[str, str]) -> None:
        super().__init__(client=None)  # type: ignore[arg-type]
        self._fixed = fixed_source

    async def generate_tests(
        self,
        source_files: dict[str, str],
        goal: Optional[str] = None,
    ) -> dict[str, str]:
        return {"test_main.py": "def test_ok():\n    assert True\n"}

    async def analyze_failure(
        self,
        source_files: dict[str, str],
        test_files: dict[str, str],
        sandbox_result: SandboxOutput,
    ) -> str:
        return "diag fake"

    async def generate_fix(
        self,
        source_files: dict[str, str],
        test_files: dict[str, str],
        analysis: str,
    ) -> tuple[dict[str, str], dict[str, str], str]:
        return dict(self._fixed), dict(test_files), "fake patch"


class FakeGate(StaticAnalysisGate):
    """Gate determinístico que sempre passa (isola testes de mecânica)."""

    def run(self, files: dict[str, str]) -> StaticAnalysisResult:
        return StaticAnalysisResult(passed=True, summary="fake ok")


def _fail() -> SandboxOutput:
    return SandboxOutput(exit_code=1, stdout="1 failed", stderr="AssertionError")


def _ok() -> SandboxOutput:
    return SandboxOutput(exit_code=0, stdout="1 passed")


def _cfg(**overrides: Any) -> Settings:
    """
    Settings de teste com gate/webhook desligados por padrão.

    `base` é anotado como dict[str, Any] para que o desempacotamento
    `Settings(**base)` não seja validado contra cada campo tipado (fix Pylance).
    """
    base: dict[str, Any] = {
        "STATIC_ANALYSIS_ENABLED": False,
        "ESCALATION_WEBHOOK_ENABLED": False,
    }
    base.update(overrides)
    return Settings(**base)


GOOD = {"main.py": "def soma(a, b):\n    return a + b\n"}
TESTS = {"test_main.py": "from main import soma\n\ndef test_soma():\n    assert soma(2, 3) == 5\n"}


# ─────────────────────────────────────────────────────────────
# (a) Análise estática sem Docker
# ─────────────────────────────────────────────────────────────

def test_static_gate_pega_erro_de_sintaxe_sem_docker() -> None:
    """Código com sintaxe quebrada → passed=False, sem tocar em Docker."""
    gate = StaticAnalysisGate(mypy_enabled=False)
    bad = {"main.py": "import os\nimport sys\n\ndef f(:\n    return\n"}
    result = gate.run(bad)
    assert result.passed is False
    assert any(i.severity == "error" for i in result.issues)


def test_static_gate_pega_import_nao_usado_sem_docker() -> None:
    gate = StaticAnalysisGate(mypy_enabled=False)
    bad = {"main.py": "import os\n\nprint('hi')\n"}
    result = gate.run(bad)
    # ruff F401 (ou ruff ausente → issue de ambiente); ambos => passed False
    assert result.passed is False


def test_tddloop_interrompe_antes_da_sandbox_em_falha_estatica() -> None:
    """Gate falhando persistente → failure_stage=static_gate, 0 chamadas Docker."""

    class AlwaysFailGate(StaticAnalysisGate):
        def run(self, files: dict[str, str]) -> StaticAnalysisResult:
            return StaticAnalysisResult(
                passed=False,
                issues=[StaticIssue(tool="ruff", code="E999", message="syntax", file="main.py", line=1)],
                ruff_passed=False,
                summary="erro de sintaxe",
            )

    runner = FakeRunner([_ok()])
    loop = TDDLoop(
        runner=runner,
        agent=FakeAgent(GOOD),
        config=_cfg(STATIC_ANALYSIS_ENABLED=True, STATIC_ANALYSIS_MAX_CYCLES=2),
        static_gate=AlwaysFailGate(),
    )
    result = asyncio.run(loop.run(TDDRequest(source_files=GOOD, test_files=TESTS)))
    assert result.success is False
    assert result.failure_stage == "static_gate"
    assert result.static_gate_passed is False
    assert result.escalated is False
    assert runner.calls == []  # Docker nunca foi acionado


# ─────────────────────────────────────────────────────────────
# (b) Telemetria + timeout preservados
# ─────────────────────────────────────────────────────────────

def test_telemetria_e_timeout_preservados_no_resultado(monkeypatch: pytest.MonkeyPatch) -> None:
    """DockerRunner popula container_id/telemetria e preserva timed_out."""
    runner = DockerSandboxRunner()

    class InfoProc:
        returncode = 0
        stdout = ""
        stderr = b""

    class StatsProc:
        returncode = 0
        stdout = "37.5%\t210.25MiB / 512MiB\n"
        stderr = ""

    class RmProc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kwargs):
        if cmd[1] == "info":
            return InfoProc()
        if cmd[1] == "image":
            return InfoProc()
        if cmd[1] == "stats":
            return StatsProc()
        if cmd[1] == "rm":
            return RmProc()
        # cmd[1] == "run" → simula timeout
        raise subprocess.TimeoutExpired(cmd, timeout=2)

    monkeypatch.setattr(subprocess, "run", fake_run)

    out = runner.run(
        SandboxInput(
            files={"a.py": "while True: pass\n"},
            command=["python", "a.py"],
            timeout_seconds=2,
        )
    )
    assert out.timed_out is True
    assert out.exit_code is None
    assert out.container_id is not None and out.container_id.startswith("founderai-sbx-")
    assert out.ram_peak_mb == pytest.approx(210.25, rel=1e-3)
    assert out.cpu_percent_max == pytest.approx(37.5, rel=1e-3)


def test_sandbox_output_preserva_telemetria_e_timeout_juntos() -> None:
    out = SandboxOutput(
        exit_code=None,
        timed_out=True,
        ram_peak_mb=511.9,
        cpu_percent_avg=88.0,
        cpu_percent_max=99.1,
        container_id="founderai-sbx-x",
    )
    assert out.timed_out is True
    assert out.ram_peak_mb == 511.9
    assert out.cpu_percent_max == 99.1


# ─────────────────────────────────────────────────────────────
# (c) Escalation Webhook mockado + integração
# ─────────────────────────────────────────────────────────────

def test_webhook_mockado_recebe_payload_de_escalacao() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(200, json={"ok": True})

    cfg = _cfg(
        STATIC_ANALYSIS_ENABLED=False,
        ESCALATION_WEBHOOK_ENABLED=True,
        ESCALATION_WEBHOOK_URL="https://hooks.example.com/x",
    )
    notifier = EscalationNotifier(config=cfg, transport=httpx.MockTransport(handler))
    runner = FakeRunner([_fail(), _fail(), _fail(), _fail()])
    loop = TDDLoop(
        runner=runner,
        agent=FakeAgent(GOOD),
        config=cfg,
        static_gate=FakeGate(),
        notifier=notifier,
    )
    result = asyncio.run(
        loop.run(
            TDDRequest(source_files=GOOD, test_files=TESTS, mission_id="mid-9", max_retries=3)
        )
    )
    assert result.escalated is True
    assert result.success is False
    assert len(recorded) == 1
    body = recorded[0].content.decode("utf-8")
    assert "mid-9" in body
    assert "tdd_loop.escalated" in body


def test_webhook_desabilitado_nao_dispara() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(200)

    cfg = _cfg(
        ESCALATION_WEBHOOK_ENABLED=False,
        ESCALATION_WEBHOOK_URL="https://hooks.example.com/x",
    )
    notifier = EscalationNotifier(config=cfg, transport=httpx.MockTransport(handler))
    runner = FakeRunner([_fail(), _fail(), _fail(), _fail()])
    loop = TDDLoop(
        runner=runner,
        agent=FakeAgent(GOOD),
        config=cfg,
        static_gate=FakeGate(),
        notifier=notifier,
    )
    result = asyncio.run(loop.run(TDDRequest(source_files=GOOD, test_files=TESTS)))
    assert result.escalated is True
    assert recorded == []  # webhook desabilitado → nenhuma chamada