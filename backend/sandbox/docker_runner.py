"""
DockerSandboxRunner — execução efêmera e hardenizada (v4.0 + v4.1.0 telemetry).

Mudança v4.1.0: flag --rm removida para permitir coleta de stats via
`docker stats --no-stream` antes do force-remove no finally.
A semântica de cleanup permanece idêntica (docker rm -f no finally).
"""

from __future__ import annotations

import json
import re
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

_HARDENING_FLAGS: Final[tuple[str, ...]] = (
    "--network=none",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--pids-limit=64",
    "--memory=512m",
    "--cpus=1.0",
)

# Regex para parse de valores docker stats (ex: "45.23%", "125.4MiB")
_CPU_RE = re.compile(r"([\d.]+)%")
_MEM_RE = re.compile(r"([\d.]+)([KMGTP]?i?B)")
_MEM_UNITS: Final[dict[str, float]] = {
    "B": 1.0,
    "KB": 1024.0,
    "KIB": 1024.0,
    "MB": 1024.0 ** 2,
    "MIB": 1024.0 ** 2,
    "GB": 1024.0 ** 3,
    "GIB": 1024.0 ** 3,
}


class DockerSandboxRunner(SandboxRunner):
    """Runner de sandbox com coleta de telemetria best-effort."""

    def __init__(
        self,
        config: Settings | None = None,
        docker_bin: str = "docker",
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._docker: str = docker_bin

    # ── Probes ──
    def is_available(self) -> bool:
        try:
            probe = subprocess.run(
                [self._docker, "info"], capture_output=True, timeout=10
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            return False
        return probe.returncode == 0

    def image_exists(self) -> bool:
        try:
            probe = subprocess.run(
                [self._docker, "image", "inspect", self._image()],
                capture_output=True, timeout=10,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            return False
        return probe.returncode == 0

    def _image(self) -> str:
        return self._config.SANDBOX_IMAGE or _IMAGE_TAG_FALLBACK

    # ── Helpers ──
    @staticmethod
    def _safe_relpath(rel: str) -> Path:
        if not rel or not rel.strip():
            raise SandboxError(f"Caminho vazio: '{rel}'")
        path = Path(rel)
        if path.is_absolute() or any(part == ".." for part in path.parts):
            raise SandboxError(f"Path traversal bloqueado: '{rel}'")
        return path

    @staticmethod
    def _cap(data: bytes, limit: int) -> tuple[str, bool]:
        if len(data) > limit:
            return data[:limit].decode("utf-8", errors="replace"), True
        return data.decode("utf-8", errors="replace"), False

    def _write_files(self, root: Path, files: dict[str, str]) -> None:
        for rel, content in files.items():
            target = root / self._safe_relpath(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def _base_argv(self, container_name: str, volume_src: str) -> list[str]:
        # --rem removido em v4.1.0: permite coleta de stats antes do rm -f
        return [
            self._docker, "run",
            *_HARDENING_FLAGS,
            "--name", container_name,
            "--volume", f"{volume_src}:{_CONTAINER_WORKDIR}",
            "--workdir", _CONTAINER_WORKDIR,
            self._image(),
        ]

    def _force_remove(self, container_name: str) -> None:
        try:
            subprocess.run(
                [self._docker, "rm", "-f", container_name],
                capture_output=True, timeout=15,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            pass

    @staticmethod
    def _parse_mem_to_mb(value: str) -> float | None:
        match = _MEM_RE.match(value.strip())
        if not match:
            return None
        num = float(match.group(1))
        unit = match.group(2).upper()
        bytes_total = num * _MEM_UNITS.get(unit, 1.0)
        return bytes_total / (1024.0 ** 2)

    def _collect_stats(self, container_name: str) -> dict:
        """Coleta best-effort de stats do container. Nunca lança."""
        result: dict = {
            "ram_peak_mb": None,
            "cpu_percent_avg": None,
            "cpu_percent_max": None,
        }
        try:
            proc = subprocess.run(
                [
                    self._docker, "stats", "--no-stream",
                    "--format", "{{.CPUPerc}}\t{{.MemUsage}}",
                    container_name,
                ],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode != 0:
                return result
            for line in proc.stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                cpu_str, mem_str = parts[0], parts[1]
                cpu_match = _CPU_RE.match(cpu_str.strip())
                if cpu_match:
                    cpu_val = float(cpu_match.group(1))
                    result["cpu_percent_max"] = max(
                        result["cpu_percent_max"] or 0.0, cpu_val
                    )
                    result["cpu_percent_avg"] = cpu_val  # uma amostra = avg = max
                # mem_str formato: "125.4MiB / 512MiB"
                mem_parts = mem_str.split("/", 1)
                if mem_parts:
                    mb = self._parse_mem_to_mb(mem_parts[0])
                    if mb is not None:
                        result["ram_peak_mb"] = max(
                            result["ram_peak_mb"] or 0.0, mb
                        )
        except (subprocess.SubprocessError, OSError, ValueError):
            pass  # best-effort: falha silenciosa
        return result

    # ── Interface pública ──
    def run(self, sbx_input: SandboxInput) -> SandboxOutput:
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
        stats: dict = {"ram_peak_mb": None, "cpu_percent_avg": None, "cpu_percent_max": None}

        with tempfile.TemporaryDirectory(prefix="founderai-sbx-") as tmp:
            root = Path(tmp)
            try:
                self._write_files(root, sbx_input.files)
                argv = self._base_argv(container_name, str(root))
                argv.extend(sbx_input.command)
                try:
                    proc = subprocess.run(
                        argv, capture_output=True, timeout=sbx_input.timeout_seconds,
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
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            finally:
                # Coleta best-effort de stats ANTES do force-remove
                stats = self._collect_stats(container_name)
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
            ram_peak_mb=stats["ram_peak_mb"],
            cpu_percent_avg=stats["cpu_percent_avg"],
            cpu_percent_max=stats["cpu_percent_max"],
            container_id=container_name,
        )