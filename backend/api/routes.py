"""
Rotas REST da API FounderAI (v5.1.0).

Segurança: mission_id/file_name sanitizados contra path traversal
(qualquer ocorrência de '..' é rejeitada com 400).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas import HealthResponse, InteractionRequest, InteractionResponse
from backend.core.config import Settings
from backend.core.engine import API_VERSION, MissionEngine

router = APIRouter()


# ── Dependências (lidas do app.state) ──
def get_config(request: Request) -> Settings:
    return request.app.state.config


def get_engine(request: Request) -> MissionEngine:
    return request.app.state.engine


# ── Helpers de artefatos ──
def _artifact_roots(config: Settings) -> list[Path]:
    return [
        Path(config.DISCOVER_ARTIFACTS_DIR),
        Path(config.VALIDATE_ARTIFACTS_DIR),
        Path(config.BUILD_ARTIFACTS_DIR),
        Path(config.VAB_ARTIFACTS_DIR),
        Path(config.SELF_AUDIT_ARTIFACTS_DIR),
        Path(config.GOLDEN_ARTIFACTS_DIR),
    ]


def _safe_segment(value: str, field: str) -> str:
    """Sanitiza um segmento de caminho; rejeita traversal com 400."""
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail=f"{field} inválido.")
    if ".." in value:
        raise HTTPException(
            status_code=400, detail=f"Path traversal bloqueado em {field}."
        )
    p = Path(value)
    if p.is_absolute() or any(part == ".." for part in p.parts):
        raise HTTPException(
            status_code=400, detail=f"Path traversal bloqueado em {field}."
        )
    return value


def _find_mission_dir(config: Settings, mission_id: str) -> Path | None:
    for root in _artifact_roots(config):
        d = root / mission_id
        if d.is_dir():
            return d
    return None


# ── Rotas ──
@router.get("/health", response_model=HealthResponse)
async def health(config: Settings = Depends(get_config)) -> HealthResponse:
    warnings = config.environment_warnings()
    providers = list(dict.fromkeys([config.PRIMARY_PROVIDER, config.FALLBACK_PROVIDER]))
    return HealthResponse(
        status="degraded" if warnings else "healthy",
        version=API_VERSION,
        environment="development" if config.debug else "production",
        active_providers=providers,
    )


@router.get("/api/v1/version")
async def version() -> dict[str, str]:
    return {"version": API_VERSION, "name": "FounderAI"}


@router.post("/api/v1/interact", response_model=InteractionResponse)
async def interact(
    request: InteractionRequest,
    engine: MissionEngine = Depends(get_engine),
) -> InteractionResponse:
    return await engine.run(request)


@router.get("/api/v1/missions/{mission_id}")
async def get_mission(
    mission_id: str,
    config: Settings = Depends(get_config),
) -> dict:
    mid = _safe_segment(mission_id, "mission_id")
    mdir = _find_mission_dir(config, mid)
    if mdir is None:
        raise HTTPException(status_code=404, detail="Missão não encontrada.")
    state: dict = {}
    state_file = mdir / "mission_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    return {
        "mission_id": mid,
        "artifacts": sorted(p.name for p in mdir.iterdir() if p.is_file()),
        "mission_state": state,
    }


@router.get("/api/v1/artifacts/{mission_id}/{file_name}")
async def get_artifact(
    mission_id: str,
    file_name: str,
    config: Settings = Depends(get_config),
) -> dict:
    mid = _safe_segment(mission_id, "mission_id")
    fname = _safe_segment(file_name, "file_name")
    mdir = _find_mission_dir(config, mid)
    if mdir is None:
        raise HTTPException(status_code=404, detail="Missão não encontrada.")
    target = mdir / fname
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Artefato não encontrado.")
    return {
        "mission_id": mid,
        "file_name": fname,
        "content": target.read_text(encoding="utf-8"),
    }

    # Router WebSocket é registrado em app.py via ws_router.