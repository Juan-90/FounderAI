"""
Testes do Loop TDD / QAAgent (v4.0 Fase B — Bloco 1).

Cobertura:
  • Schemas (defaults e limites);
  • Mecânica do loop SEM infraestrutura (FakeRunner/FakeAgent async):
    baseline, self-healing e escalação por limite de retries;
  • QAAgent com fake async de cliente LLM (parse de JSON e contratos);
  • Reais na Sandbox Docker (gateados com skip gracioso): baseline verde e
    self-healing de código quebrado com LLM real (≤ 3 retries).

Async: testes sync dirigem corrotinas via asyncio.run (sem dependência de plugin).
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import pytest

from backend.core.llm_client import LLMProviderError
from backend.qa.agent import QAAgent, QAAgentError
from backend.qa.orchestrator import TDDLoop
from backend.qa.schemas import TDDAttempt, TDDRequest, TDDResult
from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.sandbox.models import SandboxInput, SandboxOutput
from backend.sandbox.runner import SandboxRunner


# ─────────────────────────────────────────────────────────────
# Fakes tipados (mecânica sem infraestrutura)
# ─────────────────────────────────────────────────────────────

class FakeRunner(SandboxRunner):
    """Runner em memória: devolve outputs pré-programados por chamada."""

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
    """Cliente LLM em memória (async): payloads JSON por chamada."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = list(payloads)

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        if not self._payloads:
            raise AssertionError("FakeLLMClient: chamadas esgotadas.")
        return self._payloads.pop(0)


class FakeAgent(QAAgent):
    """QAAgent determinístico (async): patch corrige main.py para a + b."""

    def __init__(self, fixed_source: dict[str, str]) -> None:
        super().__init__(client=FakeLLMClient([]))
        self._fixed_source = fixed_source

    async def generate_tests(
        self, source_files: dict[str, str], goal: Optional[str] = None
    ) -> dict[str, str]:
        return {"test_main.py": "def test_placeholder():\n    assert True\n"}

    async def analyze_failure(
        self,
        source_files: dict[str, str],
        test_files: dict[str, str],
        sandbox_result: SandboxOutput,
    ) -> str:
        return "Diagnóstico fake: lógica de soma incorreta."

    async def generate_fix(
        self,
        source_files: dict[str, str],
        test_files: dict[str, str],
        analysis: str,
    ) -> tuple[dict[str, str], dict[str, str], str]:
        return dict(self._fixed_source), dict(test_files), "Fake: corrige operador."


def _fail() -> SandboxOutput:
    return SandboxOutput(exit_code=1, stdout="1 failed", stderr="AssertionError")


def _ok() -> SandboxOutput:
    return SandboxOutput(exit_code=0, stdout="1 passed")


GOOD_SOURCE: dict[str, str] = {"main.py": "def soma(a: int, b: int) -> int:\n    return a + b\n"}
BROKEN_SOURCE: dict[str, str] = {"main.py": "def soma(a: int, b: int) -> int:\n    return a - b\n"}
TESTS: dict[str, str] = {
    "test_main.py": "from main import soma\n\n\ndef test_soma():\n    assert soma(2, 3) == 5\n"
}


@pytest.fixture()
def docker_runner() -> DockerSandboxRunner:
    """Runner real; skip gracioso sem Docker/imagem."""
    runner = DockerSandboxRunner()
    if not runner.is_available():
        pytest.skip("Docker indisponível — testes reais da sandbox pulados.")
    if not runner.image_exists():
        pytest.skip("Imagem founderai-sandbox-python:v1 não construída.")
    return runner


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────

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
    assert result.attempts[0].attempt_number == 0


# ─────────────────────────────────────────────────────────────
# Mecânica do loop (sem Docker/LLM)
# ─────────────────────────────────────────────────────────────

def test_baseline_sucesso_tentativa_zero() -> None:
    runner = FakeRunner([_ok()])
    loop = TDDLoop(runner=runner, agent=FakeAgent(GOOD_SOURCE))
    result = asyncio.run(loop.run(TDDRequest(source_files=GOOD_SOURCE, test_files=TESTS)))

    assert result.success is True
    assert result.escalated is False
    assert len(result.attempts) == 1
    assert result.attempts[0].attempt_number == 0
    assert len(runner.calls) == 1
    assert "main.py" in runner.calls[0].files
    assert "test_main.py" in runner.calls[0].files


def test_self_healing_mecanica_com_fakes() -> None:
    runner = FakeRunner([_fail(), _ok()])
    loop = TDDLoop(runner=runner, agent=FakeAgent(GOOD_SOURCE))
    result = asyncio.run(loop.run(TDDRequest(source_files=BROKEN_SOURCE, test_files=TESTS)))

    assert result.success is True
    assert len(result.attempts) == 2
    assert result.attempts[1].attempt_number == 1
    assert result.attempts[1].analysis == "Diagnóstico fake: lógica de soma incorreta."
    assert result.attempts[1].patch_summary == "Fake: corrige operador."
    assert result.final_source_code == GOOD_SOURCE


def test_escalacao_apos_limite_de_retries() -> None:
    runner = FakeRunner([_fail(), _fail(), _fail(), _fail()])
    loop = TDDLoop(runner=runner, agent=FakeAgent(BROKEN_SOURCE))
    result = asyncio.run(
        loop.run(TDDRequest(source_files=BROKEN_SOURCE, test_files=TESTS, max_retries=3))
    )

    assert result.success is False
    assert result.escalated is True
    assert len(result.attempts) == 4  # baseline 0 + retries 1..3
    assert [a.attempt_number for a in result.attempts] == [0, 1, 2, 3]
    assert "Falha persistente após 3 tentativas" in result.summary


# ─────────────────────────────────────────────────────────────
# QAAgent com fake async de cliente LLM
# ─────────────────────────────────────────────────────────────

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
    fake = FakeLLMClient([
        {"source_files": GOOD_SOURCE, "patch_summary": "troca operador"},
    ])
    agent = QAAgent(client=fake)
    source, tests, summary = asyncio.run(
        agent.generate_fix(BROKEN_SOURCE, TESTS, "diag")
    )
    assert source == GOOD_SOURCE
    assert tests == TESTS  # ausente no JSON → preservado
    assert summary == "troca operador"


# ─────────────────────────────────────────────────────────────
# Reais na Sandbox Docker (skip gracioso sem infra)
# ─────────────────────────────────────────────────────────────

def test_baseline_sucesso_real_na_sandbox(docker_runner: DockerSandboxRunner) -> None:
    """Código correto + testes válidos → sucesso na tentativa 0, sem LLM."""
    loop = TDDLoop(runner=docker_runner, agent=FakeAgent(GOOD_SOURCE))
    result = asyncio.run(loop.run(TDDRequest(source_files=GOOD_SOURCE, test_files=TESTS)))

    assert result.success is True
    assert result.escalated is False
    assert len(result.attempts) == 1


@pytest.mark.real_llm
def test_self_healing_real_na_sandbox(docker_runner: DockerSandboxRunner) -> None:
    """Código quebrado → QAAgent real + Sandbox real → sucesso em ≤ 3 retries."""
    loop = TDDLoop(runner=docker_runner)  # QAAgent real (LLMClient híbrido)
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
    assert result.final_source_code["main.py"] != BROKEN_SOURCE["main.py"]