"""
CLI helper do Modo BUILD (v4.3: inferência de nome de projeto por tipo/intent).
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from rich.console import Console
from rich.panel import Panel

from backend.build.pipeline import BuildPipeline
from backend.build.profiles import GameProfile, profile_for
from backend.core.config import settings
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectType

console = Console()

StageCallback = Callable[[int, str], None]

_SUFFIX_BY_TYPE: dict[ProjectType, str] = {
    ProjectType.GAME: "Game",
    ProjectType.WEB_APP: "App",
    ProjectType.INTERNAL_SYSTEM: "System",
}


def infer_project_name(intent: str, project_type: ProjectType) -> str:
    """
    Infere um nome de projeto a partir da última palavra significativa do
    intent + sufixo do tipo. Ex:
      '...para minha barbearia' + WEB_APP -> 'BarbeariaApp'
      '...nave atirando em asteroides' + GAME -> 'AsteroidesGame'
    """
    suffix = _SUFFIX_BY_TYPE[project_type]
    words = re.findall(r"[A-Za-zÀ-ÿ]{4,}", intent or "")
    base = words[-1].capitalize() if words else "Founder"
    if base.endswith(suffix):
        return base
    return f"{base}{suffix}"


def _make_stage_printer() -> StageCallback:
    def on_stage(index: int, label: str) -> None:
        console.print(f"[bold cyan][{index}/6][/bold cyan] {label}")
    return on_stage


async def run_build_mode(
    intent: str,
    project_name: Optional[str] = None,
    project_type: Optional[ProjectType] = None,
    pipeline: Optional[BuildPipeline] = None,
) -> int:
    if not intent or not intent.strip():
        console.print(Panel(
            'Informe a intenção do projeto.\nEx: python main.py build "..." --type GAME',
            title="[bold red]⚠  Intent vazia[/bold red]", border_style="red", padding=(1, 2),
        ))
        return 1

    effective_type = project_type or ProjectType(settings.BUILD_DEFAULT_PROJECT_TYPE)
    effective_name = project_name or infer_project_name(intent, effective_type)
    profile = profile_for(effective_type, headless=settings.BUILD_GAME_HEADLESS)

    if isinstance(profile, GameProfile):
        console.print(
            f"[bold magenta]🎮 GameProfile ativado[/bold magenta] — "
            f"engine={settings.BUILD_GAME_ENGINE}, headless={profile.headless}, "
            f"env={profile.execution_env}"
        )
    else:
        console.print(
            f"[bold blue]🌐 {type(profile).__name__} ativado[/bold blue] — "
            f"stack={', '.join(profile.stack)}"
        )

    manager = ArtifactManager()
    pipe = pipeline if pipeline is not None else BuildPipeline(
        artifact_manager=manager, project_type=effective_type, profile=profile,
    )

    console.print()
    console.print(Panel(
        f"[dim]Projeto:[/dim] [bold]{effective_name}[/bold]\n"
        f"[dim]Tipo:[/dim] {effective_type.value}\n"
        f"[dim]Intent:[/dim] [italic]{intent}[/italic]",
        title="[bold cyan]🏗  Modo BUILD[/bold cyan]", border_style="cyan", padding=(1, 2),
    ))

    state = await pipe.run(intent, project_name=effective_name, on_stage=_make_stage_printer())

    artifacts_list = "\n".join(f"   📄 {a.name}" for a in state.artifacts) or "   (nenhum)"
    status_style = (
        "green" if state.status == MissionStatus.COMPLETED
        else "yellow" if state.status == MissionStatus.ESCALATED
        else "red"
    )
    console.print()
    console.print(Panel(
        f"[bold]Status:[/bold] [{status_style}]{state.status.value}[/{status_style}]\n"
        f"[dim]Mission ID:[/dim] {state.mission_id}\n"
        f"[dim]Artefatos:[/dim]\n{artifacts_list}\n"
        f"[dim]Diretório:[/dim] {manager.root / state.mission_id}",
        title="[bold]🏁 Build concluída[/bold]", border_style=status_style, padding=(1, 2),
    ))
    return 0 if state.status == MissionStatus.COMPLETED else 1