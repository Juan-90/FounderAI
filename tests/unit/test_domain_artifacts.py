"""
Testes do domínio BUILD Mode e do ArtifactManager (v4.2.0 etapa 1/3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import (
    DeploymentStrategy,
    MissionStatus,
    ProjectMode,
    ProjectType,
)
from backend.domain.models import Artifact, MissionState, Project


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture()
def manager(tmp_path: Path) -> ArtifactManager:
    return ArtifactManager(root=tmp_path)


def _make_state(mission_id: str = "m1") -> MissionState:
    return MissionState(
        mission_id=mission_id,
        project_id="p1",
        mode=ProjectMode.BUILD,
        status=MissionStatus.IN_PROGRESS,
        current_stage="codegen",
    )


# ─────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────

def test_enums_valores() -> None:
    assert ProjectMode.BUILD.value == "BUILD"
    assert ProjectType.WEB_APP.value == "WEB_APP"
    assert DeploymentStrategy.PRIVATE.value == "PRIVATE"
    assert MissionStatus.ESCALATED.value == "ESCALATED"


# ─────────────────────────────────────────────────────────────
# Models: defaults
# ─────────────────────────────────────────────────────────────

def test_artifact_defaults_id_e_created_at() -> None:
    a = Artifact(name="x.py", type="py", path="m1/x.py", content="print(1)")
    assert a.id
    assert a.created_at is not None


def test_mission_state_defaults() -> None:
    s = _make_state()
    assert s.artifacts == []
    assert s.mode_payload == {}
    assert s.updated_at is not None


def test_project_defaults() -> None:
    p = Project(name="Barbearia", intent="Agendar cortes")
    assert p.type == ProjectType.WEB_APP
    assert p.mode == ProjectMode.BUILD
    assert p.deployment == DeploymentStrategy.PRIVATE


# ─────────────────────────────────────────────────────────────
# ArtifactManager: save_artifact
# ─────────────────────────────────────────────────────────────

def test_save_artifact_cria_arquivo_e_retorna_artifact(manager: ArtifactManager, tmp_path: Path) -> None:
    art = manager.save_artifact("m1", "index.html", "<h1>Oi</h1>")
    target = tmp_path / "m1" / "index.html"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "<h1>Oi</h1>"
    assert art.name == "index.html"
    assert art.type == "html"
    assert art.path == "m1/index.html"
    assert art.content == "<h1>Oi</h1>"


def test_save_artifact_com_subfolder(manager: ArtifactManager, tmp_path: Path) -> None:
    art = manager.save_artifact("m1", "app.py", "print(1)", subfolder="src")
    target = tmp_path / "m1" / "src" / "app.py"
    assert target.exists()
    assert art.path == "m1/src/app.py"
    assert art.type == "py"


def test_save_artifact_sobrescreve_mesmo_name(manager: ArtifactManager, tmp_path: Path) -> None:
    manager.save_artifact("m1", "a.txt", "v1")
    art2 = manager.save_artifact("m1", "a.txt", "v2")
    target = tmp_path / "m1" / "a.txt"
    assert target.read_text(encoding="utf-8") == "v2"
    assert art2.content == "v2"


def test_save_artifact_sem_extensao_type_text(manager: ArtifactManager) -> None:
    art = manager.save_artifact("m1", "Makefile", "all: build")
    assert art.type == "text"


# ─────────────────────────────────────────────────────────────
# ArtifactManager: path traversal
# ─────────────────────────────────────────────────────────────

def test_traversal_bloqueado_no_name(manager: ArtifactManager) -> None:
    with pytest.raises(ValueError):
        manager.save_artifact("m1", "../../evil.txt", "x")


def test_traversal_bloqueado_no_subfolder(manager: ArtifactManager) -> None:
    with pytest.raises(ValueError):
        manager.save_artifact("m1", "a.txt", "x", subfolder="../fora")


def test_traversal_bloqueado_no_mission_id(manager: ArtifactManager) -> None:
    with pytest.raises(ValueError):
        manager.save_artifact("../m", "a.txt", "x")


def test_name_vazio_raise(manager: ArtifactManager) -> None:
    with pytest.raises(ValueError):
        manager.save_artifact("m1", "", "x")


# ─────────────────────────────────────────────────────────────
# ArtifactManager: save_mission_state
# ─────────────────────────────────────────────────────────────

def test_save_mission_state_escreve_json_roundtrip(manager: ArtifactManager, tmp_path: Path) -> None:
    state = _make_state("m9")
    manager.save_mission_state(state)
    target = tmp_path / "m9" / "mission_state.json"
    assert target.exists()
    loaded = MissionState.model_validate_json(target.read_text(encoding="utf-8"))
    assert loaded.mission_id == "m9"
    assert loaded.mode == ProjectMode.BUILD
    assert loaded.status == MissionStatus.IN_PROGRESS
    assert loaded.current_stage == "codegen"


# ─────────────────────────────────────────────────────────────
# Root configurável via Settings
# ─────────────────────────────────────────────────────────────

def test_root_configuravel_via_settings(tmp_path: Path) -> None:
    cfg = Settings(BUILD_ARTIFACTS_DIR=str(tmp_path / "custom"))
    mgr = ArtifactManager(config=cfg)
    art = mgr.save_artifact("mX", "f.txt", "data")
    assert (tmp_path / "custom" / "mX" / "f.txt").exists()
    assert art.path == "mX/f.txt"