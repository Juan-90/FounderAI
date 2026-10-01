"""
Aplicação FastAPI do FounderAI (v5.1.0).

create_app() permite injetar config/engine (testável via TestClient).
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.api.routes import router
from backend.core.config import Settings, settings
from backend.core.engine import API_VERSION, MissionEngine


def create_app(
    config: Settings | None = None,
    engine: MissionEngine | None = None,
) -> FastAPI:
    config = config if config is not None else settings
    engine = engine if engine is not None else MissionEngine(config=config)

    app = FastAPI(
        title="FounderAI API",
        description="Interaction Layer REST/WebSocket do FounderAI (AI Project OS).",
        version=API_VERSION,
    )
    app.state.config = config
    app.state.engine = engine
    app.include_router(router)
    return app


# Instância default para `uvicorn backend.api.app:app`
app = create_app()