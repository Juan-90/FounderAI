"""
Pipeline do Modo BUILD — FounderAI v4.2.0 (Path A: Barbearia).

Agentes especializados (Requirements, Architecture, Implementation, Report)
orquestrados pelo BuildPipeline em 6 estágios, com gate estático e execução
de testes em sandbox.
"""

from backend.build.agents import (
    ArchitectureAgent,
    BuildAgentError,
    BuildReporter,
    ImplementationAgent,
    RequirementsAgent,
)
from backend.build.pipeline import BuildPipeline

__all__ = [
    "ArchitectureAgent",
    "BuildAgentError",
    "BuildPipeline",
    "BuildReporter",
    "ImplementationAgent",
    "RequirementsAgent",
]