"""
Caso canônico da Barbearia — North Star da v4.2.0.

Cobertura:
  1. Pipeline mockado gera todos os artefatos (requirements, architecture,
     code, tests, report.md) com o MVP presente no código;
  2. O MVP da barbearia (serviços/agendamento/cancelamento) passa nos testes
     DENTRO da sandbox Docker (código stdlib, sem LLM, gate estático isolado);
  3. E2E real (LLM + Docker), gateado por --run-real-llm: pipeline completo
     da intent canônica da Barbearia.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.build.pipeline import BuildPipeline
from backend.core.config import Settings
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus
from backend.qa.orchestrator import TDDLoop
from backend.qa.schemas import TDDRequest
from backend.sandbox.docker_runner import DockerSandboxRunner

from tests.unit.test_build_pipeline import FakeBuildClient, FakeGate, FakeTDD

INTENT_BARBEARIA = (
    "Quero um sistema simples para minha barbearia permitir agendamento "
    "de horários dos clientes."
)

REQ_MD = "# Objetivo\nAgendamento de horários.\n# Usuários\nClientes da barbearia.\n# MVP\n...\n"
ARCH_MD = "# Stack\nFastAPI + SQLite\n# Arquivos Necessários\nbarbearia.py, test_barbearia.py\n"
REPORT_MD = "# O que foi construído\nSistema de agendamento da barbearia.\n"

BARBEARIA_CODE = '''SERVICOS = {
    "corte": 40.0,
    "barba": 30.0,
    "corte_barba": 65.0,
}

_AGENDA: dict[str, dict] = {}


class HorarioIndisponivel(Exception):
    pass


class ServicoInexistente(Exception):
    pass


def listar_servicos():
    return dict(SERVICOS)


def agendar(cliente, servico, horario):
    if servico not in SERVICOS:
        raise ServicoInexistente(servico)
    if horario in _AGENDA:
        raise HorarioIndisponivel(horario)
    _AGENDA[horario] = {"cliente": cliente, "servico": servico}
    return dict(_AGENDA[horario])


def listar_agendamentos():
    return dict(_AGENDA)


def cancelar(horario):
    if horario not in _AGENDA:
        return False
    del _AGENDA[horario]
    return True
'''

BARBEARIA_TESTS = '''import pytest

from barbearia import (
    agendar, cancelar, listar_agendamentos, listar_servicos,
    HorarioIndisponivel, ServicoInexistente,
)


def test_listar_servicos_inclui_mvp():
    assert "corte" in listar_servicos()


def test_agendamento_fluxo_completo():
    agg = agendar("Juan", "corte", "2026-10-01 09:00")
    assert agg["cliente"] == "Juan"
    assert "2026-10-01 09:00" in listar_agendamentos()


def test_cancelamento_remove_agendamento():
    agendar("Maria", "barba", "2026-10-01 10:00")
    assert cancelar("2026-10-01 10:00") is True
    assert "2026-10-01 10:00" not in listar_agendamentos()


def test_horario_indisponivel():
    agendar("Jose", "corte", "2026-10-02 09:00")
    with pytest.raises(HorarioIndisponivel):
        agendar("Ana", "corte", "2026-10-02 09:00")


def test_servico_inexistente():
    with pytest.raises(ServicoInexistente):
        agendar("Ana", "massagem", "2026-10-03 09:00")
'''

IMPL_BARBEARIA = {
    "files": {"barbearia.py": BARBEARIA_CODE},
    "test_files": {"test_barbearia.py": BARBEARIA_TESTS},
}


@pytest.fixture()
def docker_runner() -> DockerSandboxRunner:
    runner = DockerSandboxRunner()
    if not runner.is_available():
        pytest.skip("Docker indisponível — testes reais da sandbox pulados.")
    if not runner.image_exists():
        pytest.skip("Imagem founderai-sandbox-python:v1 não construída.")
    return runner


# ─────────────────────────────────────────────────────────────
# 1) Pipeline mockado gera artefatos + MVP
# ─────────────────────────────────────────────────────────────

def test_barbearia_pipeline_mockado_gera_artefatos(tmp_path: Path) -> None:
    client = FakeBuildClient([REQ_MD, ARCH_MD, REPORT_MD], [IMPL_BARBEARIA])
    pipe = BuildPipeline(
        client=client,
        artifact_manager=ArtifactManager(root=tmp_path),
        static_gate=FakeGate(),
        tdd_loop=FakeTDD(success=True),
    )
    state = asyncio.run(pipe.run(INTENT_BARBEARIA, "BarbeariaApp"))

    assert state.status == MissionStatus.COMPLETED
    names = {a.name for a in state.artifacts}
    assert {"requirements.md", "architecture.md", "barbearia.py",
            "test_barbearia.py", "report.md"} <= names

    mid = state.mission_id
    for fname in ("requirements.md", "architecture.md", "barbearia.py",
                  "test_barbearia.py", "report.md", "mission_state.json"):
        assert (tmp_path / mid / fname).exists(), f"artefato ausente: {fname}"

    code = (tmp_path / mid / "barbearia.py").read_text(encoding="utf-8")
    assert "agendar" in code and "cancelar" in code and "SERVICOS" in code


# ─────────────────────────────────────────────────────────────
# 2) MVP passa nos testes DENTRO da sandbox (sem LLM, gate isolado)
# ─────────────────────────────────────────────────────────────

def test_barbearia_mvp_testes_passam_no_docker(docker_runner: DockerSandboxRunner) -> None:
    """Valida execução na sandbox; gate estático desligado para isolar do LLM."""
    cfg = Settings(STATIC_ANALYSIS_ENABLED=False)
    loop = TDDLoop(runner=docker_runner, config=cfg)
    result = asyncio.run(loop.run(TDDRequest(
        source_files={"barbearia.py": BARBEARIA_CODE},
        test_files={"test_barbearia.py": BARBEARIA_TESTS},
        goal="MVP de agendamento da barbearia",
    )))
    assert result.success is True
    assert result.escalated is False
    assert result.final_sandbox_result is not None
    assert result.final_sandbox_result.exit_code == 0


# ─────────────────────────────────────────────────────────────
# 3) E2E real (LLM + Docker) — North Star
# ─────────────────────────────────────────────────────────────

@pytest.mark.real_llm
def test_barbearia_e2e_real_llm_e_docker(
    tmp_path: Path, docker_runner: DockerSandboxRunner
) -> None:
    cfg = Settings(STATIC_ANALYSIS_MAX_CYCLES=2)
    pipe = BuildPipeline(
        artifact_manager=ArtifactManager(root=tmp_path),
        static_gate=FakeGate(),
        tdd_loop=TDDLoop(runner=docker_runner, config=cfg),
        config=cfg,
    )
    state = asyncio.run(pipe.run(INTENT_BARBEARIA, "BarbeariaApp"))

    names = {a.name for a in state.artifacts}
    assert {"requirements.md", "architecture.md", "report.md"} <= names
    if state.status != MissionStatus.COMPLETED:
        pytest.fail(
            "North Star não atingida: "
            f"status={state.status.value} payload={state.mode_payload}"
        )