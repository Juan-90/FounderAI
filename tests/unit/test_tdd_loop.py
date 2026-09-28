"""
Testes do Loop TDD / QAAgent (v4.0 Fase B + v4.1.0 gate isolado).
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import pytest

from backend.analysis.static_gate import StaticAnalysisGate
from backend.core.config import Settings
from backend.core.llm_client import LLMProviderError
from backend.qa.agent import QAAgent, QAAgentError
from backend.qa.orchestrator import TDDLoop
from backend.qa.schemas import TDDAttempt, TDDRequest, TDDResult
from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.sandbox.models import SandboxInput, SandboxOutput
from backend.sandbox.runner import SandboxRunner


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


class FakeLLMClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = list(payloads)

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        if not self._payloads:
            raise AssertionError("FakeLLMClient: chamadas esgotadas.")
        return self._payloads.pop(0)


class FakeGate(StaticAnalysisGate):
    def run(self, files):
        return __import__("backend.analysis.models", fromlist=["StaticAnalysisResult"]).StaticAnalysisResult(
            passed=True, summary="fake ok"
        )


class FakeAgent(QAAgent):
    def __init__(self, fixed_source: dict[str, str]) -> None:
        super().__init__(client=FakeLLMClient([]))
        self._fixed_source = fixed_source

    async def generate_tests(self, source_files, goal=None):
        return {"test_main.py": "def test_placeholder():\n    assert True\n"}

    async def analyze_failure(self, source_files, test_files, sandbox_result):
        return "Diagnóstico fake: lógica de soma incorreta."

    async def generate_fix(self, source_files, test_files, analysis):
        return dict(self._fixed_source), dict(test_files), "Fake: corrige operador."


def _cfg() -> Settings:
    return Settings(STATIC_ANALYSIS_ENABLED=False, ESCALATION_WEBHOOK_ENABLED=False)


def _fail() -> SandboxOutput:
    return SandboxOutput(exit_code=1, stdout="1 failed", stderr="AssertionError")


def _ok() -> SandboxOutput:
    return SandboxOutput(exit_code=0, stdout="1 passed")


GOOD_SOURCE = {"main.py": "def soma(a: int, b: int) -> int:\n    return a + b\n"}
BROKEN_SOURCE = {"main.py": "def soma(a: int, b: int) -> int:\n    return a - b\n"}
TESTS = {"test_main.py": "from main import soma\n\n\ndef test_soma():\n    assert soma(2, 3) == 5\n"}


@pytest.fixture()
def docker_runner() -> DockerSandboxRunner:
    runner = DockerSandboxRunner()
    if not runner.is_available():
        pytest.skip("Docker indisponível — testes reais da sandbox pulados.")
    if not runner.image_exists():
        pytest.skip("Imagem founderai-sandbox-python:v1 não construída.")
    return runner


def test_tdd_request_defaults_e_limites() -> None:
    req = TDDRequest(source_files={"main.py": "x = 1\n"})
    assert req.entry_command == ["pytest", "-q"]
    assert req.max_retries == 3
    assert req.test_files == {}
    assert req.goal is None
    with pytest.raises(Exception):
        TDDRequest(source_files={}, max_retries=0)
    with pytest.raises(Exception):
        TDDRequest(source_files={}, max_retries=6)


def test_tdd_attempt_e_result_tipados() -> None:
    attempt = TDDAttempt(
        attempt_number=0,
        source_code={"main.py": "x = 1\n"},
        tests_code={},
        sandbox_result=SandboxOutput(exit_code=0),
    )
    result = TDDResult(
        success=True,
        final_source_code={"main.py": "x = 1\n"},
        final_tests_code={},
        attempts=[attempt],
        summary="ok",
    )
    assert result.escalated is False
    assert result.final_sandbox_result is None
    assert result.static_gate_passed is None
    assert result.failure_stage is None


def test_baseline_sucesso_tentativa_zero() -> None:
    runner = FakeRunner([_ok()])
    loop = TDDLoop(runner=runner, agent=FakeAgent(GOOD_SOURCE), config=_cfg(), static_gate=FakeGate())
    result = asyncio.run(loop.run(TDDRequest(source_files=GOOD_SOURCE, test_files=TESTS)))
    assert result.success is True
    assert result.escalated is False
    assert len(result.attempts) == 1
    assert result.attempts[0].attempt_number == 0
    assert len(runner.calls) == 1


def test_self_healing_mecanica_com_fakes() -> None:
    runner = FakeRunner([_fail(), _ok()])
    loop = TDDLoop(runner=runner, agent=FakeAgent(GOOD_SOURCE), config=_cfg(), static_gate=FakeGate())
    result = asyncio.run(loop.run(TDDRequest(source_files=BROKEN_SOURCE, test_files=TESTS)))
    assert result.success is True
    assert len(result.attempts) == 2
    assert result.attempts[1].attempt_number == 1
    assert result.final_source_code == GOOD_SOURCE


def test_escalacao_apos_limite_de_retries() -> None:
    runner = FakeRunner([_fail(), _fail(), _fail(), _fail()])
    loop = TDDLoop(runner=runner, agent=FakeAgent(BROKEN_SOURCE), config=_cfg(), static_gate=FakeGate())
    result = asyncio.run(loop.run(TDDRequest(source_files=BROKEN_SOURCE, test_files=TESTS, max_retries=3)))
    assert result.success is False
    assert result.escalated is True
    assert len(result.attempts) == 4
    assert result.failure_stage == "sandbox"
    assert "Falha persistente após 3 tentativas" in result.summary


def test_qaagent_generate_tests_parseia_json() -> None:
    fake = FakeLLMClient([{"files": {"test_main.py": "def test_x():\n    assert True\n"}}])
    agent = QAAgent(client=fake)
    files = asyncio.run(agent.generate_tests(GOOD_SOURCE, goal="somar"))
    assert files == {"test_main.py": "def test_x():\n    assert True\n"}


def test_qaagent_generate_tests_invalido_raise() -> None:
    fake = FakeLLMClient([{"errado": 1}, {"errado": 2}])
    agent = QAAgent(client=fake)
    with pytest.raises(QAAgentError):
        asyncio.run(agent.generate_tests(GOOD_SOURCE))


def test_qaagent_generate_fix_preserva_arquivos_ausentes() -> None:
    fake = FakeLLMClient([{"source_files": GOOD_SOURCE, "patch_summary": "troca operador"}])
    agent = QAAgent(client=fake)
    source, tests, summary = asyncio.run(agent.generate_fix(BROKEN_SOURCE, TESTS, "diag"))
    assert source == GOOD_SOURCE
    assert tests == TESTS
    assert summary == "troca operador"


def test_baseline_sucesso_real_na_sandbox(docker_runner: DockerSandboxRunner) -> None:
    loop = TDDLoop(runner=docker_runner, agent=FakeAgent(GOOD_SOURCE), config=_cfg(), static_gate=FakeGate())
    result = asyncio.run(loop.run(TDDRequest(source_files=GOOD_SOURCE, test_files=TESTS)))
    assert result.success is True
    assert len(result.attempts) == 1


@pytest.mark.real_llm
def test_self_healing_real_na_sandbox(docker_runner: DockerSandboxRunner) -> None:
    loop = TDDLoop(runner=docker_runner, config=_cfg(), static_gate=FakeGate())
    request = TDDRequest(
        source_files=BROKEN_SOURCE,
        test_files=TESTS,
        goal="soma deve retornar a adição de a e b",
        max_retries=3,
    )
    result = asyncio.run(loop.run(request))
    assert result.escalated is False
    assert result.success is True
    assert 2 <= len(result.attempts) <= 4