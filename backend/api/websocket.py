"""
Camada WebSocket da API FounderAI (v5.1.0).

ConnectionManager gerencia conexões ativas e transmite eventos do MissionEngine
em tempo real. Formato dos eventos:
  {"type": "status_update|log|artifact_generated|completed|error", "payload": {...}}
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.schemas import InteractionRequest
from backend.core.engine import MissionEngine

ws_router = APIRouter()


class ConnectionManager:
    """Gerencia conexões WebSocket ativas por mission_id."""

    def __init__(self) -> None:
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, mission_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.setdefault(mission_id, []).append(websocket)

    def disconnect(self, mission_id: str, websocket: WebSocket) -> None:
        conns = self.active.get(mission_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self.active.pop(mission_id, None)

    async def broadcast(self, mission_id: str, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for conn in self.active.get(mission_id, []):
            try:
                await conn.send_text(json.dumps(message, ensure_ascii=False))
            except Exception:
                dead.append(conn)
        for d in dead:
            self.disconnect(mission_id, d)


manager = ConnectionManager()


async def _emit_to_ws(mission_id: str, event: dict[str, Any]) -> None:
    """Adapter entre callback do MissionEngine e broadcast do manager."""
    evt_type = event.get("type", "log")
    if evt_type == "started":
        payload = {"mode": event.get("mode"), "message": "Missão iniciada"}
        kind = "status_update"
    elif evt_type == "running":
        payload = {"mode": event.get("mode"), "message": "Executando"}
        kind = "status_update"
    elif evt_type == "done":
        payload = {"status": event.get("status"), "message": "Finalizada"}
        kind = "completed"
    elif evt_type == "result":
        payload = event.get("response", {})
        kind = "artifact_generated"
    else:
        payload = event
        kind = "log"
    await manager.broadcast(mission_id, {"type": kind, "payload": payload})


def _build_engine(request_ws: WebSocket) -> MissionEngine:
    """Obtém o MissionEngine compartilhado do app.state."""
    return request_ws.app.state.engine


@ws_router.websocket("/ws/v1/missions/{mission_id}/stream")
async def ws_mission_stream(
    websocket: WebSocket,
    mission_id: str,
    mode: str = "discover",
    prompt: str = "",
) -> None:
    engine = _build_engine(websocket)
    await manager.connect(mission_id, websocket)
    try:
        request = InteractionRequest(
            source="web", target_mode=mode,  # type: ignore[arg-type]
            prompt=prompt,
        )
        async for event in engine.astream(request):
            await _emit_to_ws(mission_id, event)
    except Exception as exc:
        await manager.broadcast(mission_id, {
            "type": "error",
            "payload": {"message": f"{type(exc).__name__}: {exc}"},
        })
    finally:
        manager.disconnect(mission_id, websocket)