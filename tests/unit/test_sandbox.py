"""
Testes da Sandbox Isolada (v4.0 Fase A).

Cobertura exigida:
  1. Validação de schemas (SandboxInput / SandboxOutput);
  2. Execução com sucesso (exit_code 0);
  3. Execução com falha de código (pytest falhando → exit_code 1);
  4. Loop infinito → timed_out=True e exit_code=None;
  5. Truncamento de output acima de max_output_bytes;
  6. Docker indisponível → tratamento gracioso (exceção tipada).

Testes 2–5 exigem Docker + imagem construída; sem eles, skip gracioso
(mantém a suíte 100% verde em CI sem Docker).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.core.config import Settings
from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.sandbox.exceptions import (
    DockerUnavailableError,
    ImageNotFoundError,
    SandboxError,
    SandboxTimeoutError,
)
from backend.sandbox.models import SandboxInput, SandboxOutput


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture()
def docker_runner() -> DockerSandboxRunner:
    """Runner real; skip gracioso se Docker/imagem ausentes."""
    runner = DockerSandboxRunner()
    if not runner.is_available():
        pytest.skip("Docker indisponível — testes de execução da sandbox pulados.")
    if not runner.image_exists():
        pytest.skip(
            "Imagem founderai-sandbox-python:v1 não construída. "
            "Rode: docker build -t founderai-sandbox-python:v1 "
            "-f backend/sandbox/dockerfile/Dockerfile backend/sandbox/dockerfile"
        )
    return runner


# ─────────────────────────────────────────────────────────────
# 1) Validação de schemas
# ─────────────────────────────────────────────────────────────

def test_sandbox_input_valida_e_limites_de_timeout() -> None:
    sbx = SandboxInput(files={"a.py": "print(1)"}, command=["python", "a.py"])
    assert sbx.timeout_seconds == 20
    assert sbx.max_output_bytes == 1_048_576

    with pytest.raises(ValidationError):
        SandboxInput(files={"a.py": "x"}, command=["python"], timeout_seconds=0)
    with pytest.raises(ValidationError):
        SandboxInput(files={"a.py": "x"}, command=["python"], timeout_seconds=121)


def test_sandbox_input_rejeita_command_como_string() -> None:
    """Comando deve ser lista de strings — nunca str simples (regra 3)."""
    with pytest.raises(ValidationError):
        SandboxInput(files={"a.py": "x"}, command="python a.py")  # type: ignore[arg-type]


def test_sandbox_output_defaults() -> None:
    out = SandboxOutput()
    assert out.exit_code is None
    assert out.stdout == ""
    assert out.stderr == ""
    assert out.duration_ms == 0
    assert out.timed_out is False
    assert out.stdout_truncated is False
    assert out.stderr_truncated is False
    assert out.error is None


# ─────────────────────────────────────────────────────────────
# 6) Infraestrutura: traversal, Docker ausente, imagem ausente
# ─────────────────────────────────────────────────────────────

def test_path_traversal_bloqueado_antes_do_docker() -> None:
    runner = DockerSandboxRunner(docker_bin="docker-fantasma-xyz")
    sbx = SandboxInput(files={"../evil.py": "print(1)"}, command=["python", "evil.py"])
    with pytest.raises(SandboxError):
        runner.run(sbx)


def test_docker_indisponivel_tratamento_gracioso() -> None:
    """Binário inexistente → DockerUnavailableError tipada, sem stack trace."""
    runner = DockerSandboxRunner(docker_bin="docker-inexistente-xyz")
    assert runner.is_available() is False
    sbx = SandboxInput(files={"a.py": "print(1)"}, command=["python", "a.py"])
    with pytest.raises(DockerUnavailableError):
        runner.run(sbx)


def test_imagem_inexistente_raise_image_not_found(docker_runner: DockerSandboxRunner) -> None:
    cfg = Settings(SANDBOX_IMAGE="imagem-que-nao-existe:v99")
    runner = DockerSandboxRunner(config=cfg)
    sbx = SandboxInput(files={"a.py": "print(1)"}, command=["python", "a.py"])
    with pytest.raises(ImageNotFoundError):
        runner.run(sbx)


# ─────────────────────────────────────────────────────────────
# 2) Execução com sucesso
# ─────────────────────────────────────────────────────────────

def test_execucao_com_sucesso_exit_code_zero(docker_runner: DockerSandboxRunner) -> None:
    sbx = SandboxInput(
        files={"calc.py": "print(6 * 7)\n"},
        command=["python", "calc.py"],
        timeout_seconds=30,
    )
    out = docker_runner.run(sbx)
    assert out.error is None
    assert out.exit_code == 0
    assert "42" in out.stdout
    assert out.timed_out is False
    assert out.stdout_truncated is False
    assert out.duration_ms >= 0


# ─────────────────────────────────────────────────────────────
# 3) Execução com falha de código (pytest interno)
# ─────────────────────────────────────────────────────────────

def test_execucao_com_falha_exit_code_um(docker_runner: DockerSandboxRunner) -> None:
    sbx = SandboxInput(
        files={"test_quebra.py": "def test_quebra():\n    assert 1 == 2\n"},
        command=["pytest", "-q", "test_quebra.py"],
        timeout_seconds=60,
    )
    out = docker_runner.run(sbx)
    assert out.error is None
    assert out.exit_code == 1
    assert "1 failed" in out.stdout


# ─────────────────────────────────────────────────────────────
# 4) Timeout em loop infinito
# ─────────────────────────────────────────────────────────────

def test_timeout_loop_infinito(docker_runner: DockerSandboxRunner) -> None:
    sbx = SandboxInput(
        files={"loop.py": "while True:\n    pass\n"},
        command=["python", "loop.py"],
        timeout_seconds=2,
    )
    out = docker_runner.run(sbx)
    assert out.timed_out is True
    assert out.exit_code is None

    with pytest.raises(SandboxTimeoutError):
        docker_runner.run_strict(sbx)


# ─────────────────────────────────────────────────────────────
# 5) Truncamento de output
# ─────────────────────────────────────────────────────────────

def test_truncamento_de_output(docker_runner: DockerSandboxRunner) -> None:
    sbx = SandboxInput(
        files={"big.py": "print('A' * 3_000_000)\n"},
        command=["python", "big.py"],
        timeout_seconds=30,
        max_output_bytes=1024,
    )
    out = docker_runner.run(sbx)
    assert out.exit_code == 0
    assert out.stdout_truncated is True
    assert len(out.stdout.encode("utf-8")) <= 1024