"""
CLI helper do Modo VALIDATE_AND_BUILD (v4.5.0).

Exibe Fase 1 (Validação), Gate Decision, prompt interativo [y/N] se
WAITING_HUMAN, Fase 2 (Construção) e o Resumo Composto final.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from rich.console import Console
from rich.panel import Panel

from backend.domain.enums import MissionStatus
from backend.validate_and_build.pipeline import ValidateAndBuildPipeline
from backend.validate_and_build.schemas import (
    BuildGateDecision,
    ValidateAndBuildRequest,
)

console = Console()


def _make_confirm() -> Callable[[BuildGateDecision], bool]:
    def confirm(decision: BuildGateDecision) -> bool:
        console.print()
        console.print(Panel(
            f"[bold]Veredito:[/bold] {decision.source_verdict}  "
            f"[dim]Confiança:[/dim] {decision.confidence:.2f}\n"
            f"[bold]Gate:[/bold] {decision.reason}",
            title="[bold yellow] Gate Decision — confirmação necessária[/bold yellow]",
            border_style="yellow", padding=(1, 2),
        ))
        resp = console.input("\n[bold]Prosseguir com o BUILD? [y/N]:[/bold] ").strip().lower()
        return resp in ("y", "yes", "s", "sim")
    return confirm


async def run_validate_and_build_mode(
    intent: str,
    context_files: Optional[Sequence[str]] = None,
    name: Optional[str] = None,
    no_build: bool = False,
    auto_build: bool = False,
    no_confirm: bool = False,
    pipeline: Optional[ValidateAndBuildPipeline] = None,
) -> int:
    if not intent or not intent.strip():
        console.print(Panel(
            'Informe a ideia.\nEx: python main.py validate-and-build "Validar EcoTrack-IA e construir MVP"',
            title="[bold red]⚠  Intent vazia[/bold red]", border_style="red", padding=(1, 2),
        ))
        return 1

    request = ValidateAndBuildRequest(
        idea_text=intent, name=name, context_files=list(context_files or [])
    )
    if auto_build:
        request.auto_build = True
        request.require_human_confirmation = False

    confirm = None if no_confirm else _make_confirm()
    pipe = pipeline if pipeline is not None else ValidateAndBuildPipeline()

    console.print("[bold green]🔍 Fase 1 — Validação[/bold green]")
    state = await pipe.run(request, confirm=confirm, no_build=no_build)

    gate = state.mode_payload.get("gate", {})
    build = state.mode_payload.get("build")
    status_style = (
        "green" if state.status == MissionStatus.COMPLETED
        else "yellow" if state.status == MissionStatus.WAITING_HUMAN
        else "red"
    )
    build_line = (
        f"[bold]Build:[/bold] {build.get('status')} — {build.get('tdd_summary', '')}"
        if build else "[bold]Build:[/bold] não executado"
    )
    console.print()
    console.print(Panel(
        f"[bold]Status:[/bold] [{status_style}]{state.status.value}[/{status_style}]\n"
        f"[bold]Gate:[/bold] should_build={gate.get('should_build')} "
        f"needs_human={gate.get('needs_human_confirmation')}\n"
        f"{build_line}\n"
        f"[dim]Mission ID:[/dim] {state.mission_id}\n"
        f"[dim]Diretório:[/dim] {pipe.artifacts.root / state.mission_id}",
        title="[bold]🧩 Resumo Composto Final[/bold]", border_style=status_style, padding=(1, 2),
    ))
    return 0 if state.status in (MissionStatus.COMPLETED, MissionStatus.WAITING_HUMAN) else 1