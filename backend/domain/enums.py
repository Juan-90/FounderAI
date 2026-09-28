"""
Enums de domínio do FounderAI v4.2.0 (BUILD Mode).
"""

from __future__ import annotations

from enum import Enum


class ProjectMode(str, Enum):
    """Modo de operação do projeto."""
    BUILD    = "BUILD"
    VALIDATE = "VALIDATE"
    DISCOVER = "DISCOVER"
    IMPROVE  = "IMPROVE"


class ProjectType(str, Enum):
    """Tipo de produto alvo."""
    WEB_APP         = "WEB_APP"
    INTERNAL_SYSTEM = "INTERNAL_SYSTEM"
    GAME            = "GAME"


class DeploymentStrategy(str, Enum):
    """Estratégia de deploy (v4.2.0: apenas PRIVATE)."""
    PRIVATE = "PRIVATE"


class MissionStatus(str, Enum):
    """Ciclo de vida de uma missão."""
    PENDING     = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"
    FAILED      = "FAILED"
    ESCALATED   = "ESCALATED"