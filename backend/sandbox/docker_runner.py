"""
DockerSandboxRunner — execução efêmera e hardenizada (v4.0 Fase A).

Regras obrigatórias implementadas:
  1. Arquivos gravados em `tempfile.TemporaryDirectory` no host e montados
     de forma efêmera em /sandbox (limpeza garantida em `finally`);
  2. Flags estritas: --rm, --network=none, --cap-drop=ALL,
     --security-opt=no-new-privileges, --pids-limit=64, --memory=512m, --cpus=1.0;
  3. Comando SEMPRE como lista (argv direto, nunca `sh -c` / str simples);
  4. Truncamento de stdout/stderr em `max_output_bytes` com flags
     `stdout_truncated` / `stderr_truncated`; limpeza em `finally`.

Implementação via subprocess do CLI `docker` (zero dependências novas).
"""

from __future__ import annotations

import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Final

from backend.core.config import Settings, settings
from backend.sandbox.exceptions import (
    DockerUnavailableError,
    ImageNotFoundError,
    SandboxError,
)
from backend.sandbox.models import SandboxInput, SandboxOutput
from backend.sandbox.runner import SandboxRunner

_IMAGE_TAG_FALLBACK: Final[str] = "founderai-sandbox-python:v1"
_CONTAINER_WORKDIR: Final[str] = "/sandbox"

# Hardening fixo — não configurável por chamada (superfície de ataque mínima)
_HARDENING_FLAGS: Final[tuple[str, ...]] = (
    "--network=none",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--pids-limit=64",
    "--memory=512m",
    "--cpus=1.0",
)


class DockerSandboxRunner(SandboxRunner):
    """Runner de sandbox baseado em containers Docker efêmeros."""

    def __init__(
        self,
        config: Settings | None = None,
        docker_bin: str = "docker",
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._docker: str = docker_bin

    # ─────────────────────────────────────────
    # Probes de infraestrutura
    # ─────────────────────────────────────────

    def is_available(self) -> bool:
        """True se o daemon do Docker responde a `docker info`."""
        try:
            probe = subprocess.run(
                [self._docker, "info"],
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            return False
        return probe.returncode == 0

    def image_exists(self) -> bool:
        """True se a imagem configurada já foi construída neste host."""
        try:
            probe = subprocess.run(
                [self._docker, "image", "inspect", self._image()],
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            return False
        return probe.returncode == 0

    def _image(self) -> str:
        return self._config.SANDBOX_IMAGE or _IMAGE_TAG_FALLBACK

    # ─────────────────────────────────────────
    # Helpers internos
    # ─────────────────────────────────────────

    @staticmethod
    def _safe_relpath(rel: str) -> Path:
        """Bloqueia caminhos absolutos e path traversal no SandboxInput."""
        if not rel or not rel.strip():
            raise SandboxError(f"Caminho de arquivo vazio no SandboxInput: '{rel}'")
        path = Path(rel)
        if path.is_absolute() or any(part == ".." for part in path.parts):
            raise SandboxError(f"Path traversal bloqueado no SandboxInput: '{rel}'")
        return path

    @staticmethod
    def _cap(data: bytes, limit: int) -> tuple[str, bool]:
        """Trunca bytes no limite e decodifica UTF-8 sem exceções."""
        if len(data) > limit:
            return data[:limit].decode("utf-8", errors="replace"), True
        return data.decode("utf-8", errors="replace"), False

    def _write_files(self, root: Path, files: dict[str, str]) -> None:
        for rel, content in files.items():
            target = root / self._safe_relpath(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def _base_argv(self, container_name: str, volume_src: str) -> list[str]:
        argv: list[str] = [
            self._docker, "run", "--rm",
            *_HARDENING_FLAGS,
            "--name", container_name,
            "--volume", f"{volume_src}:{_CONTAINER_WORKDIR}",
            "--workdir", _CONTAINER_WORKDIR,
            self._image(),
        ]
        return argv

    def _force_remove(self, container_name: str) -> None:
        """Garante remoção do container mesmo após timeout/kill do cliente."""
        try:
            subprocess.run(
                [self._docker, "rm", "-f", container_name],
                capture_output=True,
                timeout=15,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            pass  # já removido pelo --rm ou daemon indisponível

    # ─────────────────────────────────────────
    # Interface pública
    # ─────────────────────────────────────────

    def run(self, sbx_input: SandboxInput) -> SandboxOutput:
        """Executa o comando em container efêmero hardenizado."""
        # Validação de caminhos ANTES de tocar no Docker (falha rápida)
        for rel in sbx_input.files:
            self._safe_relpath(rel)

        if not self.is_available():
            raise DockerUnavailableError(
                "Daemon do Docker inacessível. "
                "Verifique se o Docker Desktop/daemon está em execução."
            )
        if not self.image_exists():
            raise ImageNotFoundError(
                f"Imagem '{self._image()}' não encontrada. Construa com: "
                f"docker build -t {self._image()} "
                "-f backend/sandbox/dockerfile/Dockerfile backend/sandbox/dockerfile"
            )

        container_name = f"founderai-sbx-{uuid.uuid4().hex[:12]}"
        stdout_bytes = b""
        stderr_bytes = b""
        exit_code: int | None = None
        timed_out = False
        error: str | None = None
        started = time.perf_counter()

        with tempfile.TemporaryDirectory(prefix="founderai-sbx-") as tmp:
            root = Path(tmp)
            try:
                self._write_files(root, sbx_input.files)
                argv = self._base_argv(container_name, str(root))
                argv.extend(sbx_input.command)  # argv direto: NUNCA via shell
                try:
                    proc = subprocess.run(
                        argv,
                        capture_output=True,
                        timeout=sbx_input.timeout_seconds,
                    )
                    exit_code = proc.returncode
                    stdout_bytes = proc.stdout or b""
                    stderr_bytes = proc.stderr or b""
                except subprocess.TimeoutExpired as exc:
                    timed_out = True
                    exit_code = None
                    stdout_bytes = exc.stdout or b""
                    stderr_bytes = exc.stderr or b""
            except SandboxError:
                raise
            except Exception as exc:  # infra inesperada → saída graciosa
                error = f"{type(exc).__name__}: {exc}"
            finally:
                self._force_remove(container_name)

        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout, stdout_truncated = self._cap(stdout_bytes, sbx_input.max_output_bytes)
        stderr, stderr_truncated = self._cap(stderr_bytes, sbx_input.max_output_bytes)

        return SandboxOutput(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            error=error,
        )