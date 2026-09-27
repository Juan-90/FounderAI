"""
Exceções customizadas da Sandbox Isolada (v4.0 Fase A).

Hierarquia única sob `SandboxError` para captura seletiva pelo orquestrador,
sem vazar stack traces de infraestrutura para o usuário final.
"""

from __future__ import annotations


class SandboxError(Exception):
    """Classe base de todos os erros da sandbox."""


class DockerUnavailableError(SandboxError):
    """O daemon do Docker não está acessível neste host."""


class SandboxTimeoutError(SandboxError):
    """A execução excedeu o tempo limite configurado."""


class ImageNotFoundError(SandboxError):
    """A imagem da sandbox (founderai-sandbox-python:v1) não foi encontrada."""
    