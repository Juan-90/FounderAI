"""
Sandbox Isolada — FounderAI v4.0 Fase A.

Pacote autônomo e desacoplado do Council/agentes: expõe apenas o contrato
de execução isolada (schemas, exceções, runner base e runner Docker).
"""

from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.sandbox.exceptions import (
    DockerUnavailableError,
    ImageNotFoundError,
    SandboxError,
    SandboxTimeoutError,
)
from backend.sandbox.models import SandboxInput, SandboxOutput
from backend.sandbox.runner import SandboxRunner

__all__ = [
    "DockerSandboxRunner",
    "DockerUnavailableError",
    "ImageNotFoundError",
    "SandboxError",
    "SandboxInput",
    "SandboxOutput",
    "SandboxRunner",
    "SandboxTimeoutError",
]