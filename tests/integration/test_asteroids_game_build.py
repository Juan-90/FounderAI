"""
Caso integrado do Jogo de Nave vs Asteroides — v4.3.0 Path B.

Cobertura:
  1. Pipeline (LLM mockado) gera arquivos de jogo + game_spec.json;
  2. Testes de lógica do jogo (colisão, score, game over) passam 100% na
     sandbox Docker em modo headless (SDL_VIDEODRIVER=dummy propagado).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from backend.build.pipeline import BuildPipeline
from backend.core.config import Settings
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectType
from backend.qa.orchestrator import TDDLoop
from backend.qa.schemas import TDDRequest
from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.sandbox.models import SandboxInput, SandboxOutput
from backend.sandbox.runner import SandboxRunner

from tests.unit.test_build_pipeline import FakeBuildClient, FakeGate, FakeTDD

INTENT_NAVES = (
    "Quero um jogo 2D simples em que o jogador controla uma nave, atira e "
    "destrói asteroides, com pontuação."
)

REQ_MD = "# Game Loop\n30-60s\n# Entidades\nplayer, asteroid, projectile\n"
ARCH_MD = "# Stack\npygame\n# Arquivos\nmain.py, game.py, entities.py\n"
REPORT_MD = "# O que foi construído\nJogo de nave vs asteroides.\n"

GAME_CODE = '''import math


class Entity:
    def __init__(self, x, y, radius):
        self.x = x
        self.y = y
        self.radius = radius

    def collides(self, other):
        dx = self.x - other.x
        dy = self.y - other.y
        return math.hypot(dx, dy) <= (self.radius + other.radius)


class Ship(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, radius=12)
        self.lives = 3
        self.score = 0

    def shoot(self):
        return Projectile(self.x, self.y - self.radius)

    def hit(self):
        self.lives -= 1

    @property
    def game_over(self):
        return self.lives <= 0


class Asteroid(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, radius=20)


class Projectile(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, radius=3)


def resolve_collisions(ship, asteroids, projectiles):
    destroyed = []
    for proj in list(projectiles):
        for ast in list(asteroids):
            if proj.collides(ast):
                destroyed.append(ast)
                projectiles.remove(proj)
                asteroids.remove(ast)
                ship.score += 10
                break
    for ast in list(asteroids):
        if ast.collides(ship):
            asteroids.remove(ast)
            ship.hit()
    return destroyed
'''

GAME_TESTS = '''from game import Ship, Asteroid, Projectile, resolve_collisions


def test_colisao_projeto_asteroide_incrementa_score():
    ship = Ship(50, 50)
    ast = Asteroid(50, 10)
    proj = Projectile(50, 12)
    resolve_collisions(ship, [ast], [proj])
    assert ship.score == 10


def test_sem_colisao_nao_pontua():
    ship = Ship(0, 0)
    ast = Asteroid(200, 200)
    proj = Projectile(0, -5)
    resolve_collisions(ship, [ast], [proj])
    assert ship.score == 0


def test_colisao_asteroide_nave_perde_vida():
    ship = Ship(50, 50)
    ast = Asteroid(52, 52)
    resolve_collisions(ship, [ast], [])
    assert ship.lives == 2


def test_game_over_quando_vidas_zeradas():
    ship = Ship(0, 0)
    for _ in range(3):
        ship.hit()
    assert ship.game_over is True
'''

IMPL_GAME = {
    "files": {"game.py": GAME_CODE},
    "test_files": {"test_game.py": GAME_TESTS},
}


class RecordingRunner(DockerSandboxRunner):
    """DockerRunner real que registra os SandboxInput (para assertar env)."""

    def __init__(self) -> None:
        super().__init__()
        self.inputs: list[SandboxInput] = []

    def run(self, sbx_input: SandboxInput) -> SandboxOutput:
        self.inputs.append(sbx_input)
        return super().run(sbx_input)


@pytest.fixture()
def docker_runner() -> RecordingRunner:
    runner = RecordingRunner()
    if not runner.is_available():
        pytest.skip("Docker indisponível — testes reais da sandbox pulados.")
    if not runner.image_exists():
        pytest.skip("Imagem founderai-sandbox-python:v1 não construída.")
    return runner


# ─────────────────────────────────────────────────────────────
# 1) Pipeline mockado gera arquivos de jogo + game_spec.json
# ─────────────────────────────────────────────────────────────

def test_game_pipeline_mockado_gera_arquivos_e_game_spec(tmp_path: Path) -> None:
    client = FakeBuildClient([REQ_MD, ARCH_MD, REPORT_MD], [IMPL_GAME])
    pipe = BuildPipeline(
        client=client,
        artifact_manager=ArtifactManager(root=tmp_path),
        static_gate=FakeGate(),
        tdd_loop=FakeTDD(success=True),
        project_type=ProjectType.GAME,
    )
    state = asyncio.run(pipe.run(INTENT_NAVES, "AsteroidGame"))

    assert state.status == MissionStatus.COMPLETED
    names = {a.name for a in state.artifacts}
    assert {"requirements.md", "architecture.md", "game.py",
            "test_game.py", "game_spec.json", "report.md"} <= names

    mid = state.mission_id
    spec_path = tmp_path / mid / "game_spec.json"
    assert spec_path.exists()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["engine"] == "pygame"
    assert spec["headless"] is True
    assert spec["execution_env"]["SDL_VIDEODRIVER"] == "dummy"


# ─────────────────────────────────────────────────────────────
# 2) Testes de lógica do jogo passam 100% na sandbox headless
# ─────────────────────────────────────────────────────────────

def test_jogo_testes_de_logica_passam_na_sandbox_headless(docker_runner: RecordingRunner) -> None:
    cfg = Settings(STATIC_ANALYSIS_ENABLED=False)
    loop = TDDLoop(runner=docker_runner, config=cfg)
    result = asyncio.run(loop.run(TDDRequest(
        source_files={"game.py": GAME_CODE},
        test_files={"test_game.py": GAME_TESTS},
        goal="Jogo de nave vs asteroides",
        env={"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "PYTHONUNBUFFERED": "1"},
    )))
    assert result.success is True
    assert result.escalated is False
    assert result.final_sandbox_result is not None
    assert result.final_sandbox_result.exit_code == 0
    # Env headless realmente propagado ao container
    assert docker_runner.inputs
    assert docker_runner.inputs[0].env.get("SDL_VIDEODRIVER") == "dummy"
    assert docker_runner.inputs[0].env.get("PYTHONUNBUFFERED") == "1"


# ─────────────────────────────────────────────────────────────
# 3) Pipeline GAME propaga env headless ao TDD (mockado, sem Docker)
# ─────────────────────────────────────────────────────────────

def test_game_pipeline_propaga_env_headless_ao_tdd(tmp_path: Path) -> None:
    captured: list[TDDRequest] = []

    class CapturingTDD(FakeTDD):
        async def run(self, request: TDDRequest):
            captured.append(request)
            return await super().run(request)

    client = FakeBuildClient([REQ_MD, ARCH_MD, REPORT_MD], [IMPL_GAME])
    pipe = BuildPipeline(
        client=client,
        artifact_manager=ArtifactManager(root=tmp_path),
        static_gate=FakeGate(),
        tdd_loop=CapturingTDD(success=True),
        project_type=ProjectType.GAME,
    )
    asyncio.run(pipe.run(INTENT_NAVES, "AsteroidGame"))

    assert captured
    assert captured[0].env.get("SDL_VIDEODRIVER") == "dummy"
    assert captured[0].env.get("PYTHONUNBUFFERED") == "1"