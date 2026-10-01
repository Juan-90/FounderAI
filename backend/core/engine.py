"""
MissionEngine — orquestrador/dispatcher de alto nível (v5.1.0).

Recebe uma InteractionRequest e dispara o pipeline/runner do target_mode,
SEM alterar a lógica interna das engines/agentes da v5.0. Emite eventos de
progresso via callback (on_event) e suporta streaming via astream().
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from backend.api.schemas import (
    InteractionRequest,
    InteractionResponse,
    ResponseStatusLiteral,
)
from backend.core.config import Settings, settings
from backend.domain.enums import MissionStatus

EventCallback = Callable[[dict[str, Any]], None]
Handler = Callable[[InteractionRequest], Awaitable[InteractionResponse]]

API_VERSION = "5.1.0"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status_from(state_status: MissionStatus) -> ResponseStatusLiteral:
    """Mapeia o status interno da missão para o status da API."""
    return "completed" if state_status == MissionStatus.COMPLETED else "failed"


class MissionEngine:
    """Dispatcher unificado dos modos do FounderAI."""

    def __init__(
        self,
        config: Settings | None = None,
        handlers: Optional[dict[str, Handler]] = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._handlers: dict[str, Handler] = handlers or {}

    # ── Eventos ──
    @staticmethod
    def _emit(on_event: Optional[EventCallback], event: dict[str, Any]) -> None:
        if on_event is not None:
            on_event(event)

    # ── API pública ──
    async def run(
        self,
        request: InteractionRequest,
        on_event: Optional[EventCallback] = None,
    ) -> InteractionResponse:
        self._emit(on_event, {"type": "started", "mode": request.target_mode})
        handler = self._handlers.get(request.target_mode) or self._default_handler(
            request.target_mode
        )
        try:
            self._emit(on_event, {"type": "running", "mode": request.target_mode})
            response = await handler(request)
        except Exception as exc:
            response = InteractionResponse(
                mission_id="", status="failed", mode=request.target_mode,
                summary=f"{type(exc).__name__}: {exc}", artifacts_path="",
                created_at=_now(),
            )
        self._emit(on_event, {"type": "done", "status": response.status})
        return response

    async def astream(self, request: InteractionRequest) -> AsyncIterator[dict[str, Any]]:
        """Streaming de eventos de progresso (para WebSocket na Etapa 2)."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def on_event(event: dict[str, Any]) -> None:
            queue.put_nowait(event)

        task = asyncio.create_task(self.run(request, on_event=on_event))
        while not task.done() or not queue.empty():
            try:
                yield queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.01)
        response = await task
        yield {"type": "result", "response": response.model_dump()}

    # ── Handlers default (reutilizam pipelines v5.0) ──
    def _default_handler(self, mode: str) -> Handler:
        async def handler(request: InteractionRequest) -> InteractionResponse:
            return await self._dispatch_real(mode, request)
        return handler

    async def _dispatch_real(self, mode: str, request: InteractionRequest) -> InteractionResponse:
        opts = request.options or {}

        if mode == "discover":
            from backend.discover.pipeline import DiscoverPipeline
            from backend.discover.schemas import DiscoverRequest
            pipe = DiscoverPipeline(config=self._config)
            res = await pipe.run(DiscoverRequest(
                theme=request.prompt,
                max_opportunities=int(opts.get("max", self._config.DISCOVER_MAX_OPPORTUNITIES)),
            ))
            mid = pipe.last_mission_id or ""
            return InteractionResponse(
                mission_id=mid, status="completed" if res.opportunities else "failed",
                mode=mode, summary=res.summary,
                artifacts_path=str(Path(self._config.DISCOVER_ARTIFACTS_DIR) / mid),
                created_at=_now(),
            )

        if mode == "validate":
            from backend.validate.pipeline import ValidatePipeline
            from backend.validate.schemas import ValidateRequest
            pipe = ValidatePipeline(config=self._config)
            state = await pipe.run(ValidateRequest(idea_text=request.prompt))
            return InteractionResponse(
                mission_id=state.mission_id, status=_status_from(state.status),
                mode=mode,
                summary=state.mode_payload.get("final_report", "")[:200] or "validação concluída",
                artifacts_path=str(Path(self._config.VALIDATE_ARTIFACTS_DIR) / state.mission_id),
                created_at=_now(),
            )

        if mode == "build":
            from backend.build.pipeline import BuildPipeline
            from backend.domain.enums import ProjectType
            ptype = ProjectType(opts.get("project_type", "WEB_APP"))
            pipe = BuildPipeline(config=self._config, project_type=ptype)
            state = await pipe.run(request.prompt, project_name=opts.get("name", "App"))
            return InteractionResponse(
                mission_id=state.mission_id, status=_status_from(state.status),
                mode=mode, summary=state.mode_payload.get("tdd_summary", ""),
                artifacts_path=str(Path(self._config.BUILD_ARTIFACTS_DIR) / state.mission_id),
                created_at=_now(),
            )

        if mode == "validate_and_build":
            from backend.validate_and_build.pipeline import ValidateAndBuildPipeline
            from backend.validate_and_build.schemas import ValidateAndBuildRequest
            pipe = ValidateAndBuildPipeline(config=self._config)
            state = await pipe.run(
                ValidateAndBuildRequest(
                    idea_text=request.prompt,
                    auto_build=bool(opts.get("auto_build", True)),
                    require_human_confirmation=False,
                ),
                no_build=bool(opts.get("no_build", False)),
            )
            return InteractionResponse(
                mission_id=state.mission_id, status=_status_from(state.status),
                mode=mode, summary=state.mode_payload.get("summary", ""),
                artifacts_path=str(Path(self._config.VAB_ARTIFACTS_DIR) / state.mission_id),
                created_at=_now(),
            )

        if mode == "self_audit":
            from backend.self_audit.pipeline import SelfAuditPipeline
            from backend.self_audit.schemas import SelfAuditRequest
            pipe = SelfAuditPipeline(config=self._config)
            score = await pipe.run(SelfAuditRequest(
                max_missions_per_mode=int(opts.get("max_per_mode", 1)),
                adversarial_enabled=bool(opts.get("adversarial", False)),
            ))
            mid = pipe.last_audit_dir.name if pipe.last_audit_dir else ""
            ok = score.overall_verdict in ("HEALTHY", "DEGRADED")
            return InteractionResponse(
                mission_id=mid, status="completed" if ok else "failed",
                mode=mode, summary=score.summary,
                artifacts_path=str(Path(self._config.SELF_AUDIT_ARTIFACTS_DIR) / mid),
                created_at=_now(),
            )

        if mode == "golden":
            from backend.golden.runner import GoldenRunner
            report = await GoldenRunner(config=self._config).run()
            return InteractionResponse(
                mission_id=report.run_id, status="completed" if report.all_passed else "failed",
                mode=mode, summary=report.summary,
                artifacts_path=report.artifacts_path, created_at=_now(),
            )

        raise ValueError(f"target_mode não suportado: {mode}")