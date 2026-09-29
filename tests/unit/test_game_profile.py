"""
Testes do GameProfile e da especialização dos agentes (v4.3.0).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.build.agents import ImplementationAgent, RequirementsAgent
from backend.build.profiles import (
    BaseProjectProfile,
    GameProfile,
    WebAppProfile,
    profile_for,
)
from backend.domain.enums import ProjectType


# ─────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────

def test_profile_for_game_retorna_gameprofile() -> None:
    p = profile_for(ProjectType.GAME)
    assert isinstance(p, GameProfile)
    assert p.project_type == ProjectType.GAME


def test_profile_for_web_retorna_webappprofile() -> None:
    p = profile_for(ProjectType.WEB_APP)
    assert isinstance(p, WebAppProfile)


def test_profile_for_internal_system_default_web() -> None:
    p = profile_for(ProjectType.INTERNAL_SYSTEM)
    assert isinstance(p, WebAppProfile)


# ─────────────────────────────────────────────────────────────
# GameProfile: stack / estrutura / env
# ─────────────────────────────────────────────────────────────

def test_game_profile_stack_pygame() -> None:
    p = GameProfile()
    assert "pygame" in p.stack


def test_game_profile_file_structure() -> None:
    p = GameProfile()
    for fname in ("main.py", "game.py", "entities.py"):
        assert fname in p.file_structure


def test_game_profile_headless_env() -> None:
    p = GameProfile(headless=True)
    assert p.execution_env["SDL_VIDEODRIVER"] == "dummy"
    assert p.execution_env["SDL_AUDIODRIVER"] == "dummy"


def test_game_profile_sem_headless_env_vazio() -> None:
    p = GameProfile(headless=False)
    assert p.execution_env == {}


def test_game_profile_test_command() -> None:
    assert GameProfile().test_command() == ["pytest", "-q"]


# ─────────────────────────────────────────────────────────────
# GameProfile: prompts de gameplay
# ─────────────────────────────────────────────────────────────

def test_game_requirements_prompt_cobre_gameplay() -> None:
    prompt = GameProfile().requirements_prompt("jogo de nave")
    low = prompt.lower()
    assert "game loop" in low
    assert "win/lose" in low
    assert "controles" in low
    assert "player" in low and "asteroid" in low and "projectile" in low


def test_game_architecture_prompt_separa_logica_e_render() -> None:
    prompt = GameProfile().architecture_prompt("# req")
    low = prompt.lower()
    assert "lógica" in low or "logica" in low
    assert "renderização" in low or "renderizacao" in low
    assert "pygame" in low


def test_game_implementation_prompt_exige_testes_de_logica() -> None:
    prompt = GameProfile().implementation_prompt("# arch")
    low = prompt.lower()
    assert "pygame" in low
    assert "movimento" in low and "colisão" in low or "colisao" in low
    assert "pontuação" in low or "pontuacao" in low


# ─────────────────────────────────────────────────────────────
# WebAppProfile: sanidade
# ─────────────────────────────────────────────────────────────

def test_web_profile_stack_e_estrutura() -> None:
    p = WebAppProfile()
    assert "FastAPI" in p.stack and "SQLite" in p.stack and "Uvicorn" in p.stack
    for fname in ("main.py", "models.py", "schemas.py", "database.py", "test_main.py"):
        assert fname in p.file_structure
    assert p.execution_env == {}


# ─────────────────────────────────────────────────────────────
# Agentes especializados (mock de cliente)
# ─────────────────────────────────────────────────────────────

class _CaptureClient:
    def __init__(self, json_payload: dict[str, Any] | None = None) -> None:
        self.prompts: list[str] = []
        self._json = json_payload or {"files": {"game.py": "x=1"}, "test_files": {}}

    async def complete(self, system_prompt, user_prompt, model=None, role=None) -> str:
        self.prompts.append(user_prompt)
        return "# doc"

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        self.prompts.append(user_prompt)
        return self._json


def test_requirements_agent_usa_prompt_do_gameprofile() -> None:
    client = _CaptureClient()
    agent = RequirementsAgent(client=client, profile=GameProfile())
    asyncio.run(agent.generate("jogo de nave"))
    assert "Game Loop" in client.prompts[0]


def test_implementation_agent_usa_prompt_do_gameprofile() -> None:
    client = _CaptureClient()
    agent = ImplementationAgent(client=client, profile=GameProfile())
    files, tests = asyncio.run(agent.generate("# arch"))
    assert "pygame" in client.prompts[0].lower()
    assert files == {"game.py": "x=1"}


def test_agent_sem_profile_default_web() -> None:
    client = _CaptureClient()
    agent = RequirementsAgent(client=client)
    asyncio.run(agent.generate("saas"))
    assert "WEB APP" in client.prompts[0]