"""
Testes da CLI e API de projetos (v5.3.0).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.api.app import create_app  # noqa: E402
from backend.cli import cmd_artifacts, cmd_list, cmd_show, cmd_timeline  # noqa: E402
from backend.core.config import Settings  # noqa: E402
from backend.core.engine import MissionEngine  # noqa: E402
from backend.domain.memory import ArtifactKind  # noqa: E402
from backend.domain.memory_store import DiskProjectMemoryStore  # noqa: E402


def _cfg(tmp_path: Path) -> Settings:
    return Settings(
        PROJECT_MEMORY_DIR=str(tmp_path / "projects"),
        VALIDATE_ARTIFACTS_DIR=str(tmp_path / "validate"),
        BUILD_ARTIFACTS_DIR=str(tmp_path / "build"),
        VAB_ARTIFACTS_DIR=str(tmp_path / "vab"),
    )


class FakeEngine(MissionEngine):
    async def run(self, request, on_event=None):
        from backend.api.schemas import InteractionResponse
        from datetime import datetime, timezone
        return InteractionResponse(
            mission_id="m-test", status="completed", mode=request.target_mode,
            summary="ok", artifacts_path="artifacts/test/m-test",
            created_at=datetime.now(timezone.utc),
        )


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def test_cli_list_vazio(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    cfg = _cfg(tmp_path)
    result = cmd_list(config=cfg)
    assert result == 0
    captured = capsys.readouterr()
    assert "Nenhum projeto encontrado" in captured.out


def test_cli_list_com_projetos(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    store.create(name="Projeto A")
    store.create(name="Projeto B")

    result = cmd_list(config=cfg)
    assert result == 0
    captured = capsys.readouterr()
    assert "Projeto A" in captured.out
    assert "Projeto B" in captured.out


def test_cli_show(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="Teste")
    store.add_decision(mem.project_id, "Usar FastAPI", "performance")

    result = cmd_show(mem.project_id, config=cfg)
    assert result == 0
    captured = capsys.readouterr()
    assert "Teste" in captured.out
    assert "Usar FastAPI" in captured.out


def test_cli_show_inexistente(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    result = cmd_show("nao-existe", config=cfg)
    assert result == 1


def test_cli_timeline(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="Teste")
    from backend.domain.memory import MemoryEventType
    store.append_event(mem.project_id, MemoryEventType.PROJECT_CREATED, "Criado")

    result = cmd_timeline(mem.project_id, config=cfg)
    assert result == 0
    captured = capsys.readouterr()
    assert "project_created" in captured.out


def test_cli_artifacts(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="Teste")
    artifact_file = tmp_path / "requirements.md"
    artifact_file.write_text("# Req", encoding="utf-8")
    store.add_artifact_version(mem.project_id, ArtifactKind.REQUIREMENTS, str(artifact_file))

    result = cmd_artifacts(mem.project_id, config=cfg)
    assert result == 0
    captured = capsys.readouterr()
    assert "requirements" in captured.out


# ─────────────────────────────────────────────────────────────
# API REST
# ─────────────────────────────────────────────────────────────

def test_api_list_projects_vazio(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    client = TestClient(create_app(config=cfg, engine=FakeEngine()))
    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    assert r.json() == []


def test_api_list_projects_com_dados(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    store.create(name="Projeto X")

    client = TestClient(create_app(config=cfg, engine=FakeEngine()))
    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Projeto X"


def test_api_get_project(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="Teste API")
    store.add_decision(mem.project_id, "Decisão X", "rationale")

    client = TestClient(create_app(config=cfg, engine=FakeEngine()))
    r = client.get(f"/api/v1/projects/{mem.project_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Teste API"
    assert len(data["decisions"]) == 1
    assert data["decisions"][0]["title"] == "Decisão X"


def test_api_get_project_404(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    client = TestClient(create_app(config=cfg, engine=FakeEngine()))
    r = client.get("/api/v1/projects/nao-existe")
    assert r.status_code == 404


def test_api_timeline(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="Teste")
    from backend.domain.memory import MemoryEventType
    store.append_event(mem.project_id, MemoryEventType.BUILD_STARTED, "Build 1")

    client = TestClient(create_app(config=cfg, engine=FakeEngine()))
    r = client.get(f"/api/v1/projects/{mem.project_id}/timeline")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["type"] == "build_started"


def test_api_artifacts(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="Teste")
    artifact_file = tmp_path / "arch.md"
    artifact_file.write_text("# Arch", encoding="utf-8")
    store.add_artifact_version(mem.project_id, ArtifactKind.ARCHITECTURE, str(artifact_file))

    client = TestClient(create_app(config=cfg, engine=FakeEngine()))
    r = client.get(f"/api/v1/projects/{mem.project_id}/artifacts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["kind"] == "architecture"