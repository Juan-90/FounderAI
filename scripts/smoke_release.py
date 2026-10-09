"""
Smoke de release (v5.5.0): valida infraestrutura + memória + feedback + IMPROVE dry-run.

Uso:
  python scripts/smoke_release.py
  python main.py smoke

Sem rede e sem Docker: TestClient in-process + stubs de gate/TDD (dry-run).
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, cast

# Garante a raiz do repo no sys.path quando executado direto
# (python scripts/smoke_release.py), pois o dir do script (scripts/) não a inclui.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.core.config import Settings, settings  # noqa: E402


@dataclass
class SmokeStep:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SmokeReport:
    ok: bool
    steps: list[SmokeStep] = field(default_factory=list)


class _Gate:
    def __init__(self, passed: bool = True) -> None:
        self.passed = passed

    def run(self, files):
        return SimpleNamespace(passed=self.passed, summary="gate(stub)")


class _TDD:
    async def run(self, request):
        return SimpleNamespace(success=True, escalated=False, summary="tdd(stub)")


class NoopEngine:
    """Engine inerte p/ smoke (não executa missões reais)."""

    def __init__(self, config: Settings) -> None:
        self._config = config

    async def run(self, request, on_event=None):
        from datetime import datetime, timezone
        from backend.api.schemas import InteractionResponse
        return InteractionResponse(
            mission_id="smoke", status="failed", mode=request.target_mode,
            summary="smoke não executa missões", artifacts_path="",
            created_at=datetime.now(timezone.utc),
        )


def _run_coro(coro):
    """Executa coroutine com ou sem event loop já rodando (CLI async vs sync)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(coro)).result()


def run_smoke(config: Optional[Settings] = None) -> SmokeReport:
    cfg = config if config is not None else settings
    steps: list[SmokeStep] = []

    def step(name: str, fn) -> None:
        try:
            detail = fn()
            steps.append(SmokeStep(name, True, detail or ""))
        except Exception as exc:
            steps.append(SmokeStep(name, False, f"{type(exc).__name__}: {exc}"))

    try:
        from fastapi.testclient import TestClient
        from backend.api.app import create_app
        client = TestClient(create_app(config=cfg, engine=cast(Any, NoopEngine(cfg))))
    except Exception as exc:
        return SmokeReport(ok=False, steps=[SmokeStep("bootstrap API", False, str(exc))])

    from backend.core.improve.patcher import ImprovePatcher, ImproveQualityRunner
    from backend.core.improve.pipeline import ImprovePipeline
    from backend.domain.improve import ImproveRequest
    from backend.domain.memory import MemoryEventType
    from backend.domain.memory_store import DiskProjectMemoryStore

    store = DiskProjectMemoryStore(base_dir=Path(cfg.PROJECT_MEMORY_DIR))
    project: dict = {"id": None}

    # 1 — health / version
    def s_health():
        r = client.get("/health")
        r.raise_for_status()
        d = r.json()
        assert "status" in d and "version" in d
        return f"status={d['status']} version={d['version']}"
    step("GET /health", s_health)

    def s_version():
        r = client.get("/api/v1/version")
        r.raise_for_status()
        d = r.json()
        assert d.get("name") == "FounderAI" and d.get("version")
        return f"version={d['version']}"
    step("GET /api/v1/version", s_version)

    # 2 — cria + exibe projeto
    def s_create():
        mem = store.create(name="SmokeProject")
        project["id"] = mem.project_id
        r = client.get(f"/api/v1/projects/{mem.project_id}")
        r.raise_for_status()
        return f"project_id={mem.project_id}"
    step("Cria projeto de teste", s_create)

    # 3 — feedback humano
    def s_feedback():
        r = client.post(f"/api/v1/projects/{project['id']}/feedback",
                        json={"rating": 5, "note": "smoke ok", "tags": ["smoke"]})
        r.raise_for_status()
        d = r.json()
        assert d["accepted"]
        return f"learning_id={d['learning_id']}"
    step("POST feedback humano", s_feedback)

    # 4 — timeline com OBSERVED
    def s_timeline():
        r = client.get(f"/api/v1/projects/{project['id']}/timeline")
        r.raise_for_status()
        items = r.json()
        assert any(i["type"] == MemoryEventType.OBSERVED.value for i in items)
        return "evento OBSERVED presente"
    step("GET timeline (OBSERVED)", s_timeline)

    # 5 — IMPROVE dry-run (mockado)
    def s_improve():
        pipe = ImprovePipeline(
            store=store, config=cfg,
            patcher=ImprovePatcher(),
            quality_runner=ImproveQualityRunner(static_gate=_Gate(True), tdd_loop=_TDD()),
        )
        res = _run_coro(pipe.execute(ImproveRequest(
            project_id=project["id"], require_human_confirmation=False, auto_apply=True,
        )))
        return f"success={res.success} waiting_human={res.waiting_human}"
    step("IMPROVE dry-run", s_improve)

    return SmokeReport(ok=all(s.ok for s in steps), steps=steps)


def main(config: Optional[Settings] = None) -> int:
    from rich.console import Console
    from rich.table import Table
    console = Console()
    report = run_smoke(config=config)
    table = Table(title="Smoke de Release (v5.5.0)")
    table.add_column("Passo", min_width=28)
    table.add_column("OK", justify="center")
    table.add_column("Detalhe", min_width=40)
    for s in report.steps:
        table.add_row(s.name, "[green]✅[/green]" if s.ok else "[red]❌[/red]", s.detail)
    console.print(table)
    console.print("[bold green]SMOKE OK[/bold green]" if report.ok
                  else "[bold red]SMOKE FALHOU[/bold red]")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())