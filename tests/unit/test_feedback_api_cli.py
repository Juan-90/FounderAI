"""
Testes da API REST + CLI de feedback (v5.5.0 — OBSERVE).
"""

from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.api.app import create_app  # noqa: E402
from backend.api.schemas import InteractionResponse  # noqa: E402
from backend.cli import cmd_feedback  # noqa: E402
from backend.core.config import Settings  # noqa: E402
from backend.core.engine import MissionEngine  # noqa: E402
from backend.domain.memory import MemoryEventType  # noqa: E402
from backend.domain.memory_store import DiskProjectMemoryStore  # noqa: E402


def _cfg(tmp_path: Path) -> Settings:
    return Settings(
        PROJECT_MEMORY_DIR=str(tmp_path / "projects"),
        VALIDATE_ARTIFACTS_DIR=str(tmp_path / "validate"),
        BUILD_ARTIFACTS_DIR=str(tmp_path / "build"),
        VAB_ARTIFACTS_DIR=str(tmp_path / "vab"),
        OBSERVE_FEEDBACK_ENABLED=True,
        OBSERVE_FEEDBACK_MAX_NOTE_CHARS=2000,
    )


class FakeEngine(MissionEngine):
    async def run(self, request, on_event=None):
        from datetime import datetime, timezone
        return InteractionResponse(
            mission_id="m-test", status="completed", mode=request.target_mode,
            summary="ok", artifacts_path="artifacts/test/m-test",
            created_at=datetime.now(timezone.utc),
        )


def _setup(tmp_path: Path):
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    client = TestClient(create_app(config=cfg, engine=FakeEngine()))
    return client, store, mem, cfg


# ─────────────────────────────────────────────────────────────
# API REST
# ─────────────────────────────────────────────────────────────

def test_api_feedback_payload_valido(tmp_path: Path) -> None:
    client, store, mem, _ = _setup(tmp_path)
    r = client.post(f"/api/v1/projects/{mem.project_id}/feedback",
                    json={"rating": 5, "note": "muito bom", "tags": ["ux"]})
    assert r.status_code == 200
    d = r.json()
    assert d["accepted"] is True
    assert d["learning_id"] and d["event_id"]

    m = store.get(mem.project_id)
    assert m is not None
    assert any(l.source == "human_feedback" for l in m.learnings)
    assert any(e.type == MemoryEventType.OBSERVED for e in m.events)


def test_api_feedback_payload_vazio_rejeitado(tmp_path: Path) -> None:
    client, store, mem, _ = _setup(tmp_path)
    r = client.post(f"/api/v1/projects/{mem.project_id}/feedback", json={})
    assert r.status_code == 200
    assert r.json()["accepted"] is False

    m = store.get(mem.project_id)
    assert m is not None
    assert m.learnings == []


def test_api_feedback_rating_fora_do_range_422(tmp_path: Path) -> None:
    client, _, mem, _ = _setup(tmp_path)
    r = client.post(f"/api/v1/projects/{mem.project_id}/feedback", json={"rating": 9})
    assert r.status_code == 422


def test_api_timeline_inclui_observed_formatado(tmp_path: Path) -> None:
    client, _, mem, _ = _setup(tmp_path)
    client.post(f"/api/v1/projects/{mem.project_id}/feedback",
                json={"rating": 4, "note": "ok"})
    r = client.get(f"/api/v1/projects/{mem.project_id}/timeline")
    assert r.status_code == 200
    items = r.json()
    assert any(i["type"] == "observed" for i in items)
    assert any(i.get("display", "").startswith("observed:") for i in items)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def test_cli_feedback_invoca_servico(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")

    code = cmd_feedback(mem.project_id, rating=4, note="boa", tags=["a"], config=cfg)
    assert code == 0
    m = store.get(mem.project_id)
    assert m is not None
    assert any(l.source == "human_feedback" and "rating=4" in l.text for l in m.learnings)
    assert any(e.type == MemoryEventType.OBSERVED for e in m.events)


def test_cli_feedback_vazio_retorna_1(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = DiskProjectMemoryStore(base_dir=tmp_path / "projects")
    mem = store.create(name="P")
    code = cmd_feedback(mem.project_id, config=cfg)
    assert code == 1