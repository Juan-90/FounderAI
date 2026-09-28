"""
Testes do BuildPipeline (v4.2.0 etapa 2/3) com LLMClient mockado.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from backend.analysis.models import StaticAnalysisResult
from backend.build.agents import BuildAgentError, ImplementationAgent
from backend.build.pipeline import BuildPipeline
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus
from backend.qa.schemas import TDDRequest, TDDResult


# ─────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────

class FakeBuildClient:
    """Cliente LLM em memória: filas separadas para complete e complete_json."""

    def __init__(
        self,
        complete_responses: list[str],
        json_responses: list[dict[str, Any]],
    ) -> None:
        self._complete = list(complete_responses)
        self._json = list(json_responses)

    async def complete(self, system_prompt, user_prompt, model=None, role=None) -> str:
        if not self._complete:
            raise RuntimeError("FakeBuildClient: complete esgotado.")
        return self._complete.pop(0)

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        if not self._json:
            raise RuntimeError("FakeBuildClient: complete_json esgotado.")
        return self._json.pop(0)


class FakeGate:
    def __init__(self, fail_times: int = 0) -> None:
        self._fail = fail_times
        self.calls = 0

    def run(self, files: dict[str, str]) -> StaticAnalysisResult:
        self.calls += 1
        if self._fail > 0:
            self._fail -= 1
            return StaticAnalysisResult(passed=False, summary="erro estático fake")
        return StaticAnalysisResult(passed=True, summary="ok")


class FakeRepair:
    def __init__(self, fixed: dict[str, str]) -> None:
        self._fixed = fixed
        self.calls = 0

    async def generate_fix(self, source_files, test_files, analysis):
        self.calls += 1
        return dict(self._fixed), dict(test_files), "reparo fake"


class FakeTDD:
    def __init__(self, success: bool = True, escalated: bool = False) -> None:
        self._success = success
        self._escalated = escalated
        self.requests: list[TDDRequest] = []

    async def run(self, request: TDDRequest) -> TDDResult:
        self.requests.append(request)
        return TDDResult(
            success=self._success,
            final_source_code=dict(request.source_files),
            final_tests_code=dict(request.test_files),
            attempts=[],
            escalated=self._escalated,
            summary="fake tdd",
        )


REQ_MD = "# Objetivo\nAgendar cortes.\n# Usuários\nClientes.\n# MVP\n...\n"
ARCH_MD = "# Stack\nFastAPI + SQLite\n# Arquivos Necessários\nmain.py...\n"
REPORT_MD = "# O que foi construído\nBarbeariaApp\n"
IMPL_PAYLOAD = {
    "files": {"main.py": "def soma(a, b):\n    return a + b\n"},
    "test_files": {"test_main.py": "from main import soma\n\ndef test_s():\n    assert soma(2, 3) == 5\n"},
}


def _make_pipeline(
    tmp_path: Path,
    client: FakeBuildClient,
    gate: FakeGate | None = None,
    repair: FakeRepair | None = None,
    tdd: FakeTDD | None = None,
) -> BuildPipeline:
    return BuildPipeline(
        client=client,
        artifact_manager=ArtifactManager(root=tmp_path),
        static_gate=gate if gate is not None else FakeGate(),
        repair_agent=repair if repair is not None else FakeRepair(IMPL_PAYLOAD["files"]),
        tdd_loop=tdd if tdd is not None else FakeTDD(),
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────
# Pipeline completo (sucesso)
# ─────────────────────────────────────────────────────────────

def test_pipeline_completo_sucesso(tmp_path: Path) -> None:
    client = FakeBuildClient(
        complete_responses=[REQ_MD, ARCH_MD, REPORT_MD],
        json_responses=[IMPL_PAYLOAD],
    )
    pipe = _make_pipeline(tmp_path, client)
    state = _run(pipe.run("Sistema de agendamento de barbearia", "BarbeariaApp"))

    assert state.status == MissionStatus.COMPLETED
    assert state.current_stage == "report"
    names = {a.name for a in state.artifacts}
    assert {"requirements.md", "architecture.md", "main.py", "test_main.py", "report.md"} <= names

    mid = state.mission_id
    assert (tmp_path / mid / "requirements.md").exists()
    assert (tmp_path / mid / "architecture.md").exists()
    assert (tmp_path / mid / "report.md").exists()
    assert (tmp_path / mid / "mission_state.json").exists()


# ─────────────────────────────────────────────────────────────
# Quality gate com reparo
# ─────────────────────────────────────────────────────────────

def test_pipeline_quality_gate_repara_e_passa(tmp_path: Path) -> None:
    client = FakeBuildClient([REQ_MD, ARCH_MD, REPORT_MD], [IMPL_PAYLOAD])
    gate = FakeGate(fail_times=1)
    repair = FakeRepair(IMPL_PAYLOAD["files"])
    pipe = _make_pipeline(tmp_path, client, gate=gate, repair=repair)
    state = _run(pipe.run("intent"))

    assert state.status == MissionStatus.COMPLETED
    assert gate.calls == 2          # falhou 1x, passou na 2ª
    assert repair.calls == 1        # um reparo aplicado
    assert state.mode_payload["static_gate_passed"] is True


# ─────────────────────────────────────────────────────────────
# Escalação de testes
# ─────────────────────────────────────────────────────────────

def test_pipeline_escalado_quando_tdd_falha(tmp_path: Path) -> None:
    client = FakeBuildClient([REQ_MD, ARCH_MD, REPORT_MD], [IMPL_PAYLOAD])
    pipe = _make_pipeline(tmp_path, client, tdd=FakeTDD(success=False, escalated=True))
    state = _run(pipe.run("intent"))
    assert state.status == MissionStatus.ESCALATED


def test_pipeline_failed_quando_tdd_falha_sem_escalacao(tmp_path: Path) -> None:
    client = FakeBuildClient([REQ_MD, ARCH_MD, REPORT_MD], [IMPL_PAYLOAD])
    pipe = _make_pipeline(tmp_path, client, tdd=FakeTDD(success=False, escalated=False))
    state = _run(pipe.run("intent"))
    assert state.status == MissionStatus.FAILED


# ─────────────────────────────────────────────────────────────
# Falha graciosa de agente
# ─────────────────────────────────────────────────────────────

def test_pipeline_falha_de_agente_nao_propaga(tmp_path: Path) -> None:
    client = FakeBuildClient(complete_responses=[], json_responses=[IMPL_PAYLOAD])
    pipe = _make_pipeline(tmp_path, client)
    state = _run(pipe.run("intent"))
    assert state.status == MissionStatus.FAILED
    assert "error" in state.mode_payload
    assert (tmp_path / state.mission_id / "mission_state.json").exists()


# ─────────────────────────────────────────────────────────────
# ImplementationAgent: contrato
# ─────────────────────────────────────────────────────────────

def test_implementation_agent_invalido_raise() -> None:
    client = FakeBuildClient([], [{"sem_files": 1}])
    agent = ImplementationAgent(client=client)
    with pytest.raises(BuildAgentError):
        asyncio.run(agent.generate(ARCH_MD))


def test_implementation_agent_retorna_files_e_tests() -> None:
    client = FakeBuildClient([], [IMPL_PAYLOAD])
    agent = ImplementationAgent(client=client)
    files, tests = asyncio.run(agent.generate(ARCH_MD))
    assert files == IMPL_PAYLOAD["files"]
    assert tests == IMPL_PAYLOAD["test_files"]