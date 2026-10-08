"""
Rotas REST da API FounderAI (v5.1 + v5.2 evidence + v5.3 projects).

Segurança: mission_id/file_name sanitizados contra path traversal (400 em '..').
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schemas import HealthResponse, InteractionRequest, InteractionResponse
from backend.core.config import Settings
from backend.core.engine import API_VERSION, MissionEngine
from backend.domain.memory_store import DiskProjectMemoryStore

router = APIRouter()


def get_config(request: Request) -> Settings:
    return request.app.state.config


def get_engine(request: Request) -> MissionEngine:
    return request.app.state.engine


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
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail=f"{field} inválido.")
    if ".." in value:
        raise HTTPException(status_code=400, detail=f"Path traversal bloqueado em {field}.")
    p = Path(value)
    if p.is_absolute() or any(part == ".." for part in p.parts):
        raise HTTPException(status_code=400, detail=f"Path traversal bloqueado em {field}.")
    return value


def _find_mission_dir(config: Settings, mission_id: str) -> Path | None:
    for root in _artifact_roots(config):
        d = root / mission_id
        if d.is_dir():
            return d
    return None


def _load_evidence_summary(mission_dir: Path) -> dict | None:
    evidence_file = mission_dir / "evidence" / "evidence_graph.json"
    if not evidence_file.exists():
        return None
    try:
        data = json.loads(evidence_file.read_text(encoding="utf-8"))
        summary: dict = {
            "sources_count": len(data.get("sources", [])),
            "claims_count": len(data.get("claims", [])),
            "evidence_items_count": len(data.get("evidence_items", [])),
            "gaps_count": len(data.get("notes", [])),
        }
        metrics = data.get("metrics", {}) or {}
        for key in ("provider_used", "cache_hits", "cache_misses",
                    "deduped_sources_count", "deduped_evidence_count",
                    "deduped_claims_count"):
            if key in metrics:
                summary[key] = metrics[key]
        return summary
    except (json.JSONDecodeError, KeyError):
        return None


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
async def get_mission(mission_id: str, config: Settings = Depends(get_config)) -> dict:
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
    artifacts = []
    for p in mdir.iterdir():
        if p.is_file():
            artifacts.append(p.name)
        elif p.is_dir() and p.name == "evidence":
            artifacts.append(f"{p.name}/")
    response = {
        "mission_id": mid,
        "artifacts": sorted(artifacts),
        "mission_state": state,
    }
    evidence_summary = _load_evidence_summary(mdir)
    if evidence_summary:
        response["evidence_summary"] = evidence_summary
    return response


@router.get("/api/v1/artifacts/{mission_id}/{file_name:path}")
async def get_artifact(
    mission_id: str, file_name: str, config: Settings = Depends(get_config),
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


# ── Projetos (v5.3.0) ──
def _project_store(config: Settings) -> DiskProjectMemoryStore:
    return DiskProjectMemoryStore(base_dir=Path(config.PROJECT_MEMORY_DIR))


@router.get("/api/v1/projects")
async def list_projects(config: Settings = Depends(get_config)) -> list[dict]:
    store = _project_store(config)
    return [
        {
            "project_id": p.project_id,
            "name": p.name,
            "status": p.status,
            "events_count": len(p.events),
            "updated_at": p.updated_at.isoformat(),
        }
        for p in store.list_projects()
    ]


@router.get("/api/v1/projects/{project_id}")
async def get_project(project_id: str, config: Settings = Depends(get_config)) -> dict:
    store = _project_store(config)
    memory = store.get(project_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return {
        "project_id": memory.project_id,
        "name": memory.name,
        "status": memory.status,
        "current_goal": memory.current_goal,
        "decisions": [d.model_dump(mode="json") for d in memory.decisions],
        "learnings": [l.model_dump(mode="json") for l in memory.learnings],
        "artifact_versions_count": len(memory.artifact_versions),
        "events_count": len(memory.events),
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat(),
    }


@router.get("/api/v1/projects/{project_id}/timeline")
async def get_timeline(project_id: str, config: Settings = Depends(get_config)) -> list[dict]:
    store = _project_store(config)
    memory = store.get(project_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return [e.model_dump(mode="json") for e in memory.events]


@router.get("/api/v1/projects/{project_id}/artifacts")
async def get_project_artifacts(
    project_id: str, config: Settings = Depends(get_config),
) -> list[dict]:
    store = _project_store(config)
    memory = store.get(project_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return [v.model_dump(mode="json") for v in memory.artifact_versions]