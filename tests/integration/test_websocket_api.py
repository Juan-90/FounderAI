"""
Testes de integração WebSocket da API (v5.1.0).

Usa fastapi.testclient.TestClient.websocket_connect. Importorskip mantém
a suíte verde se fastapi não estiver instalado.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.api.app import create_app  # noqa: E402
from backend.api.schemas import InteractionRequest, InteractionResponse  # noqa: E402
from backend.core.config import Settings  # noqa: E402
from backend.core.engine import MissionEngine  # noqa: E402


class StreamingFakeEngine(MissionEngine):
    """Engine fake que emite eventos via astream()."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[InteractionRequest] = []

    async def run(self, request, on_event=None) -> InteractionResponse:
        self.calls.append(request)
        if on_event is not None:
            on_event({"type": "started", "mode": request.target_mode})
            on_event({"type": "running", "mode": request.target_mode})
            on_event({"type": "done", "status": "completed"})
        return InteractionResponse(
            mission_id="m-ws-1", status="completed", mode=request.target_mode,
            summary="streamed", artifacts_path="artifacts/test/m-ws-1",
            created_at=datetime.now(timezone.utc),
        )

    async def astream(self, request: InteractionRequest) -> AsyncIterator[dict]:
        self.calls.append(request)
        yield {"type": "started", "mode": request.target_mode}
        yield {"type": "running", "mode": request.target_mode}
        yield {"type": "done", "status": "completed"}
        yield {"type": "result", "response": {
            "mission_id": "m-ws-1", "status": "completed", "mode": request.target_mode,
            "summary": "streamed", "artifacts_path": "artifacts/test/m-ws-1",
        }}


def _cfg(tmp_path: Path) -> Settings:
    return Settings(
        DISCOVER_ARTIFACTS_DIR=str(tmp_path / "discover"),
        VALIDATE_ARTIFACTS_DIR=str(tmp_path / "validate"),
        BUILD_ARTIFACTS_DIR=str(tmp_path / "build"),
        VAB_ARTIFACTS_DIR=str(tmp_path / "vab"),
        SELF_AUDIT_ARTIFACTS_DIR=str(tmp_path / "self_audit"),
        GOLDEN_ARTIFACTS_DIR=str(tmp_path / "golden"),
    )


def test_websocket_stream_entrega_eventos(tmp_path: Path) -> None:
    engine = StreamingFakeEngine()
    client = TestClient(create_app(config=_cfg(tmp_path), engine=engine))
    events: list[dict] = []

    with client.websocket_connect(
        "/ws/v1/missions/m-ws-1/stream?mode=discover&prompt=teste"
    ) as ws:
        for _ in range(4):  # started, running, done, result
            raw = ws.receive_text()
            events.append(json.loads(raw))

    kinds = [e["type"] for e in events]
    assert "status_update" in kinds       # started/running mapeados
    assert "completed" in kinds           # done
    assert "artifact_generated" in kinds  # result
    assert engine.calls                   # engine foi acionado via astream


def test_websocket_propaga_erro_como_evento(tmp_path: Path) -> None:
    """Falha NO MEIO do stream vira evento type=error (não derruba o socket)."""

    class BrokenEngine(StreamingFakeEngine):
        async def astream(self, request: InteractionRequest) -> AsyncIterator[dict]:
            # Async generator real: emite 1 evento e falha em seguida.
            yield {"type": "started", "mode": request.target_mode}
            raise RuntimeError("explodiu")

    engine = BrokenEngine()
    client = TestClient(create_app(config=_cfg(tmp_path), engine=engine))

    with client.websocket_connect(
        "/ws/v1/missions/m-broken/stream?mode=build&prompt=x"
    ) as ws:
        first = json.loads(ws.receive_text())
        assert first["type"] == "status_update"  # stream iniciou normalmente
        error_event = json.loads(ws.receive_text())

    assert error_event["type"] == "error"
    assert "explodiu" in error_event["payload"]["message"]