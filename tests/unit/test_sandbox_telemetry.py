"""
Testes da Telemetria de Sandbox (v4.1.0 Módulo B).

Cobertura:
  • Campos opcionais de telemetria em SandboxOutput (defaults None);
  • Aceitação de valores reais de RAM/CPU/container_id;
  • Parser de unidades de memória (MiB/GiB/KiB);
  • Coleta best-effort de stats sem Docker (não lança, retorna None).
"""

from __future__ import annotations

import pytest

from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.sandbox.models import SandboxOutput


# ─────────────────────────────────────────────────────────────
# Schemas: defaults
# ─────────────────────────────────────────────────────────────

def test_sandbox_output_campos_telemetria_default_none() -> None:
    out = SandboxOutput(exit_code=0, stdout="ok")
    assert out.ram_peak_mb is None
    assert out.cpu_percent_avg is None
    assert out.cpu_percent_max is None
    assert out.container_id is None


def test_sandbox_output_preserva_campos_legados() -> None:
    out = SandboxOutput(exit_code=1, stdout="x", stderr="y", timed_out=False)
    assert out.exit_code == 1
    assert out.stdout == "x"
    assert out.stderr == "y"
    assert out.duration_ms == 0
    assert out.stdout_truncated is False
    assert out.error is None


# ─────────────────────────────────────────────────────────────
# Schemas: valores preenchidos
# ─────────────────────────────────────────────────────────────

def test_sandbox_output_aceita_valores_telemetria() -> None:
    out = SandboxOutput(
        exit_code=0,
        stdout="1 passed",
        ram_peak_mb=245.5,
        cpu_percent_avg=12.3,
        cpu_percent_max=45.6,
        container_id="founderai-sbx-abc123",
    )
    assert out.ram_peak_mb == 245.5
    assert out.cpu_percent_avg == 12.3
    assert out.cpu_percent_max == 45.6
    assert out.container_id == "founderai-sbx-abc123"


def test_sandbox_output_serializa_telemetria() -> None:
    out = SandboxOutput(exit_code=0, ram_peak_mb=100.0, container_id="c1")
    data = out.model_dump()
    assert data["ram_peak_mb"] == 100.0
    assert data["container_id"] == "c1"
    assert data["cpu_percent_avg"] is None


# ─────────────────────────────────────────────────────────────
# Parser de unidades de memória
# ─────────────────────────────────────────────────────────────

def test_parse_mem_to_mb_mib() -> None:
    assert DockerSandboxRunner._parse_mem_to_mb("125.4MiB") == pytest.approx(125.4, rel=1e-3)


def test_parse_mem_to_mb_gib() -> None:
    assert DockerSandboxRunner._parse_mem_to_mb("1.5GiB") == pytest.approx(1.5 * 1024.0, rel=1e-3)


def test_parse_mem_to_mb_kib() -> None:
    assert DockerSandboxRunner._parse_mem_to_mb("512KiB") == pytest.approx(0.5, rel=1e-3)


def test_parse_mem_to_mb_invalido_retorna_none() -> None:
    assert DockerSandboxRunner._parse_mem_to_mb("invalid") is None
    assert DockerSandboxRunner._parse_mem_to_mb("") is None


# ─────────────────────────────────────────────────────────────
# Coleta best-effort (resiliência)
# ─────────────────────────────────────────────────────────────

def test_collect_stats_sem_docker_retorna_none_sem_lancar() -> None:
    """Binário inexistente → stats None, sem exceção (contrato best-effort)."""
    runner = DockerSandboxRunner(docker_bin="docker-fantasma-xyz")
    stats = runner._collect_stats("container-fake")
    assert stats == {
        "ram_peak_mb": None,
        "cpu_percent_avg": None,
        "cpu_percent_max": None,
    }


def test_collect_stats_parseia_saida_docker_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    """Saída real do `docker stats` é convertida em MB e %."""
    import subprocess

    runner = DockerSandboxRunner()

    class FakeProc:
        returncode = 0
        stdout = "45.23%\t125.4MiB / 512MiB\n"

    def fake_run(cmd, **kwargs):
        return FakeProc()

    monkeypatch.setattr(subprocess, "run", fake_run)
    stats = runner._collect_stats("founderai-sbx-fake")
    assert stats["cpu_percent_max"] == pytest.approx(45.23, rel=1e-3)
    assert stats["cpu_percent_avg"] == pytest.approx(45.23, rel=1e-3)
    assert stats["ram_peak_mb"] == pytest.approx(125.4, rel=1e-3)


def test_collect_stats_ignora_saida_vazia(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    runner = DockerSandboxRunner()

    class FakeProc:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: FakeProc())
    stats = runner._collect_stats("founderai-sbx-fake")
    assert stats["ram_peak_mb"] is None
    assert stats["cpu_percent_avg"] is None
    assert stats["cpu_percent_max"] is None


def test_collect_stats_ignora_returncode_diferente_de_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    runner = DockerSandboxRunner()

    class FakeProc:
        returncode = 1
        stdout = "Error: No such container\n"

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: FakeProc())
    stats = runner._collect_stats("founderai-sbx-inexistente")
    assert stats["ram_peak_mb"] is None