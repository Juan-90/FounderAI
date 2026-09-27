"""
Abstração base do Runner de Sandbox (v4.0 Fase A).

Contrato mínimo para qualquer backend de execução isolada
(Docker hoje; podman/local-restrito no futuro), mantendo o
orquestrador desacoplado da implementação.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.sandbox.exceptions import SandboxTimeoutError
from backend.sandbox.models import SandboxInput, SandboxOutput


class SandboxRunner(ABC):
    """Interface de execução isolada e efêmera."""

    @abstractmethod
    def is_available(self) -> bool:
        """True se o backend de execução está acessível neste host."""

    @abstractmethod
    def run(self, sbx_input: SandboxInput) -> SandboxOutput:
        """
        Executa o comando de forma isolada.

        Resultados de código (exit code, timeout, truncamento) voltam no
        `SandboxOutput`; falhas de infraestrutura pré-condição levantam
        exceções tipadas (`DockerUnavailableError`, `ImageNotFoundError`).
        """

    def run_strict(self, sbx_input: SandboxInput) -> SandboxOutput:
        """Como `run`, mas levanta `SandboxTimeoutError` em vez de flag."""
        output = self.run(sbx_input)
        if output.timed_out:
            raise SandboxTimeoutError(
                f"Execução excedeu {sbx_input.timeout_seconds}s na sandbox."
            )
        return output
    