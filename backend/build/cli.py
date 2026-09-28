"""
CLI helper do Modo BUILD (v4.2.0).

Encapsula a execução do BuildPipeline com impressão de estágios [k/6]
e painel-resumo final, retornando exit code (0=COMPLETED, 1=outro).
Mantém main.py magro e esta lógica testável/isolada.
"""

from __future__ import annotations

from typing import Callable

from rich.console import Console
from rich.panel import Panel

from backend.build.pipeline import BuildPipeline
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus

console = Console()

StageCallback = Callable[[int, str], None]


def _make_stage_printer() -> StageCallback:
    def on_stage(index: int, label: str) -> None:
        console.print(f"[bold cyan][{index}/6][/bold cyan] {label}")
    return on_stage


async def run_build_mode(
    intent: str,
    project_name: str = "BarbeariaApp",
    pipeline: BuildPipeline | None = None,
) -> int:
    """
    Executa o Modo BUILD de ponta a ponta e imprime progresso + resumo.

    Returns:
        0 se COMPLETED, 1 caso contrário (FAILED/ESCALATED/intent vazia).
    """
    if not intent or not intent.strip():
        console.print(
            Panel(
                "Informe a intenção do projeto.\n"
                'Ex: python main.py build "Quero um sistema de agendamento '
                'para minha barbearia"',
                title="[bold red]⚠  Intent vazia[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return 1

    manager = ArtifactManager()
    pipe = pipeline if pipeline is not None else BuildPipeline(artifact_manager=manager)

    console.print()
    console.print(
        Panel(
            f"[dim]Projeto:[/dim] [bold]{project_name}[/bold]\n"
            f"[dim]Intent:[/dim] [italic]{intent}[/italic]",
            title="[bold cyan]🏗  Modo BUILD[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    state = await pipe.run(intent, project_name=project_name, on_stage=_make_stage_printer())

    artifacts_list = "\n".join(f"   📄 {a.name}" for a in state.artifacts) or "   (nenhum)"
    status_style = (
        "green" if state.status == MissionStatus.COMPLETED
        else "yellow" if state.status == MissionStatus.ESCALATED
        else "red"
    )
    console.print()
    console.print(
        Panel(
            f"[bold]Status:[/bold] [{status_style}]{state.status.value}[/{status_style}]\n"
            f"[dim]Mission ID:[/dim] {state.mission_id}\n"
            f"[dim]Artefatos:[/dim]\n{artifacts_list}\n"
            f"[dim]Diretório:[/dim] {manager.root / state.mission_id}",
            title="[bold]🏁 Build concluída[/bold]",
            border_style=status_style,
            padding=(1, 2),
        )
    )
    return 0 if state.status == MissionStatus.COMPLETED else 1