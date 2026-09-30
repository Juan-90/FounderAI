"""
Pack de missões canônicas do SELF-AUDIT (v4.6.0).

Registro estático de missões de teste por modo, com artefatos obrigatórios e
arquivo de relatório esperados, para alimentar os objective checks.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from backend.domain.enums import ProjectMode, ProjectType
from backend.self_audit.schemas import SelfAuditRequest

_BUILD_REPORT = "report.md"
_BUILD_ARTIFACTS = ["requirements.md", "architecture.md", _BUILD_REPORT]
_VAL_REPORT = "validation_report.md"
_VAL_ARTIFACTS = ["idea_profile.json", _VAL_REPORT]
_VAB_REPORT = "composite_report.md"
_VAB_ARTIFACTS = ["gate_decision.json", _VAB_REPORT]


class CanonicalMission(BaseModel):
    """Uma missão canônica de auditoria."""

    mission_name: str
    mode: ProjectMode
    intent: str
    project_type: Optional[ProjectType] = None
    required_artifacts: list[str] = Field(default_factory=list)
    report_file: str


BUILD_MISSIONS: list[CanonicalMission] = [
    CanonicalMission(
        mission_name="Barbearia (Web)", mode=ProjectMode.BUILD,
        intent="Quero um sistema de agendamento para minha barbearia.",
        project_type=ProjectType.WEB_APP,
        required_artifacts=_BUILD_ARTIFACTS, report_file=_BUILD_REPORT,
    ),
    CanonicalMission(
        mission_name="Asteroids Game (Game 2D)", mode=ProjectMode.BUILD,
        intent="Quero um jogo 2D simples de nave atirando em asteroides.",
        project_type=ProjectType.GAME,
        required_artifacts=_BUILD_ARTIFACTS, report_file=_BUILD_REPORT,
    ),
]

VALIDATE_MISSIONS: list[CanonicalMission] = [
    CanonicalMission(
        mission_name="EcoTrack-IA", mode=ProjectMode.VALIDATE,
        intent="Validar o EcoTrack-IA, sistema com IA para PMEs reduzirem pegada de carbono.",
        required_artifacts=_VAL_ARTIFACTS, report_file=_VAL_REPORT,
    ),
    CanonicalMission(
        mission_name="Ideia Fraca Proposital", mode=ProjectMode.VALIDATE,
        intent="Uma rede social genérica para todos, sem diferencial, em mercado saturado.",
        required_artifacts=_VAL_ARTIFACTS, report_file=_VAL_REPORT,
    ),
    CanonicalMission(
        mission_name="Ideia Ambígua", mode=ProjectMode.VALIDATE,
        intent="Algo com IA para melhorar coisas.",
        required_artifacts=_VAL_ARTIFACTS, report_file=_VAL_REPORT,
    ),
]

VAB_MISSIONS: list[CanonicalMission] = [
    CanonicalMission(
        mission_name="Ideia para Build Aprovado", mode=ProjectMode.VALIDATE_AND_BUILD,
        intent="Sistema de agendamento para barbearias com demanda comprovada e MVP claro.",
        required_artifacts=_VAB_ARTIFACTS, report_file=_VAB_REPORT,
    ),
    CanonicalMission(
        mission_name="Ideia para Discard", mode=ProjectMode.VALIDATE_AND_BUILD,
        intent="Rede social genérica sem diferencial em mercado saturado.",
        required_artifacts=_VAB_ARTIFACTS, report_file=_VAB_REPORT,
    ),
]


def get_canonical_pack() -> dict[ProjectMode, list[CanonicalMission]]:
    return {
        ProjectMode.BUILD: list(BUILD_MISSIONS),
        ProjectMode.VALIDATE: list(VALIDATE_MISSIONS),
        ProjectMode.VALIDATE_AND_BUILD: list(VAB_MISSIONS),
    }


def select_missions(request: SelfAuditRequest) -> list[CanonicalMission]:
    """Seleciona missões respeitando include_* e max_missions_per_mode."""
    pack = get_canonical_pack()
    selected: list[CanonicalMission] = []
    if request.include_build:
        selected += pack[ProjectMode.BUILD][: request.max_missions_per_mode]
    if request.include_validate:
        selected += pack[ProjectMode.VALIDATE][: request.max_missions_per_mode]
    if request.include_validate_and_build:
        selected += pack[ProjectMode.VALIDATE_AND_BUILD][: request.max_missions_per_mode]
    return selected