"""
Testes da API REST (v5.1.0) com fastapi.testclient.TestClient.

Usa importorskip para manter a suíte verde mesmo sem fastapi instalado.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.api.app import create_app  # noqa: E402
from backend.api.schemas import InteractionResponse  # noqa: E402
from backend.core.config import Settings  # noqa: E402
from backend.core.engine import MissionEngine  # noqa: E402


class FakeEngine(MissionEngine):
    """Engine fake que não toca nos pipelines reais."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []

    async def run(self, request, on_event=None) -> InteractionResponse:
        self.calls.append(request)
        return InteractionResponse(
            mission_id="m-test", status="completed", mode=request.target_mode,
            summary="ok", artifacts_path="artifacts/build/m-test",
            created_at=datetime.now(timezone.utc),
        )


def _cfg(tmp_path: Path) -> Settings:
    return Settings(
        DISCOVER_ARTIFACTS_DIR=str(tmp_path / "discover"),
        VALIDATE_ARTIFACTS_DIR=str(tmp_path / "validate"),
        BUILD_ARTIFACTS_DIR=str(tmp_path / "build"),
        VAB_ARTIFACTS_DIR=str(tmp_path / "vab"),
        SELF_AUDIT_ARTIFACTS_DIR=str(tmp_path / "self_audit"),
        GOLDEN_ARTIFACTS_DIR=str(tmp_path / "golden"),
    )


def test_health(tmp_path: Path) -> None:
    client = TestClient(create_app(config=_cfg(tmp_path), engine=FakeEngine()))
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["version"] == "5.1.0"
    assert isinstance(data["active_providers"], list)


def test_version(tmp_path: Path) -> None:
    client = TestClient(create_app(config=_cfg(tmp_path), engine=FakeEngine()))
    r = client.get("/api/v1/version")
    assert r.status_code == 200
    assert r.json()["version"] == "5.1.0"


def test_interact_com_engine_fake(tmp_path: Path) -> None:
    engine = FakeEngine()
    client = TestClient(create_app(config=_cfg(tmp_path), engine=engine))
    r = client.post("/api/v1/interact", json={
        "source": "web", "target_mode": "build", "prompt": "criar app x",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["mission_id"] == "m-test"
    assert data["status"] == "completed"
    assert engine.calls  # engine foi acionado


def test_interact_mode_invalido_422(tmp_path: Path) -> None:
    client = TestClient(create_app(config=_cfg(tmp_path), engine=FakeEngine()))
    r = client.post("/api/v1/interact", json={
        "source": "web", "target_mode": "nao_existe", "prompt": "x",
    })
    assert r.status_code == 422


def test_mission_lookup_e_404(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    mdir = tmp_path / "build" / "m1"
    mdir.mkdir(parents=True)
    (mdir / "mission_state.json").write_text(json.dumps({"mode": "BUILD"}), encoding="utf-8")
    (mdir / "report.md").write_text("# report", encoding="utf-8")

    client = TestClient(create_app(config=cfg, engine=FakeEngine()))
    r = client.get("/api/v1/missions/m1")
    assert r.status_code == 200
    assert "report.md" in r.json()["artifacts"]

    r404 = client.get("/api/v1/missions/unknown")
    assert r404.status_code == 404


def test_artifact_download_e_traversal(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    mdir = tmp_path / "build" / "m1"
    mdir.mkdir(parents=True)
    (mdir / "report.md").write_text("# report conteudo", encoding="utf-8")

    client = TestClient(create_app(config=cfg, engine=FakeEngine()))
    r = client.get("/api/v1/artifacts/m1/report.md")
    assert r.status_code == 200
    assert r.json()["content"] == "# report conteudo"

    # traversal bloqueado
    rbad = client.get("/api/v1/artifacts/m1/..secret")
    assert rbad.status_code == 400