"""
Pack formal das 7 Golden Missions (v5.0.0 GA).

G1 DISCOVER · G2 VALIDATE · G3 VAB no-build · G4 VAB build-path ·
G5 BUILD Web · G6 BUILD Game · G7 SELF-AUDIT.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.domain.enums import ProjectMode


class GoldenMission(BaseModel):
    """Uma missão canônica de regressão GA."""

    id: str = Field(description="Identificador G1..G7")
    name: str
    mode: ProjectMode
    intent: str
    options: dict[str, Any] = Field(default_factory=dict)


GOLDEN_PACK: list[GoldenMission] = [
    GoldenMission(
        id="G1", name="Discover Barbearias", mode=ProjectMode.DISCOVER,
        intent="Software para barbearias/salões no Brasil",
        options={"max_opportunities": 5},
    ),
    GoldenMission(
        id="G2", name="Validate EcoTrack-IA", mode=ProjectMode.VALIDATE,
        intent="Validar o EcoTrack-IA, sistema com IA para PMEs reduzirem pegada de carbono.",
    ),
    GoldenMission(
        id="G3", name="VAB no-build (ideia fraca)", mode=ProjectMode.VALIDATE_AND_BUILD,
        intent="Rede social genérica sem diferencial em mercado saturado.",
        options={"no_build": True, "auto_build": False},
    ),
    GoldenMission(
        id="G4", name="VAB build-path (ideia forte)", mode=ProjectMode.VALIDATE_AND_BUILD,
        intent="Sistema de agendamento para barbearias com demanda comprovada e MVP claro.",
        options={"auto_build": True},
    ),
    GoldenMission(
        id="G5", name="Build Web Barbearia", mode=ProjectMode.BUILD,
        intent="Quero um sistema de agendamento para minha barbearia.",
        options={"project_type": "WEB_APP"},
    ),
    GoldenMission(
        id="G6", name="Build Game Asteroids", mode=ProjectMode.BUILD,
        intent="Quero um jogo 2D Asteroids-like em Pygame.",
        options={"project_type": "GAME"},
    ),
    GoldenMission(
        id="G7", name="Self-Audit ecossistema", mode=ProjectMode.SELF_AUDIT,
        intent="Auditoria completa do ecossistema FounderAI.",
    ),
]


def get_golden_pack() -> list[GoldenMission]:
    return list(GOLDEN_PACK)