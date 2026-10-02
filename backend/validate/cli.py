"""
CLI helper do Modo VALIDATE (v4.4 + v5.2 Evidence).
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from rich.console import Console
from rich.panel import Panel

from backend.core.evidence.service import EvidenceService
from backend.domain.enums import MissionStatus
from backend.validate.pipeline import ValidatePipeline
from backend.validate.schemas import ValidateRequest

console = Console()


def _make_stage_printer() -> Callable[[int, str], None]:
    def on_stage(index: int, label: str) -> None:
        console.print(f"[bold cyan][{index}/7][/bold cyan] {label}")
    return on_stage


async def run_validate_mode(
    intent: str,
    context_files: Optional[Sequence[str]] = None,
    name: Optional[str] = None,
    pipeline: Optional[ValidatePipeline] = None,
    evidence_service: Optional[EvidenceService] = None,
) -> int:
    if not intent or not intent.strip():
        console.print(Panel(
            'Informe a ideia a validar.\nEx: python main.py validate "Quero validar o EcoTrack-IA..."',
            title="[bold red]⚠  Intent vazia[/bold red]", border_style="red", padding=(1, 2),
        ))
        return 1

    request = ValidateRequest(
        idea_text=intent,
        name=name,
        context_files=list(context_files or []),
    )

    console.print(
        "[bold green]🔍 ValidateProfile ativado[/bold green] — "
        "pipeline de 7 estágios (intake → síntese)"
    )
    if evidence_service is None:
        console.print("[yellow]⚠  Evidência externa desabilitada (--no-evidence ou config)[/yellow]")
    console.print()
    console.print(Panel(
        f"[dim]Ideia:[/dim] [italic]{intent}[/italic]\n"
        f"[dim]Contexto:[/dim] {', '.join(request.context_files) or '(nenhum)'}",
        title="[bold cyan]🔍  Modo VALIDATE[/bold cyan]", border_style="cyan", padding=(1, 2),
    ))

    pipe = pipeline if pipeline is not None else ValidatePipeline(evidence_service=evidence_service)
    state = await pipe.run(request, on_stage=_make_stage_printer())

    rec = state.mode_payload.get("recommendation", {})
    verdict = rec.get("verdict", "N/A")
    confidence = rec.get("confidence", 0.0)
    risks = state.mode_payload.get("risks_contrarian", {})
    top_risks = (risks.get("reasons_to_kill") or risks.get("regulatory_risks") or [])[:3]
    experiments = state.mode_payload.get("experiments", [])

    status_style = (
        "green" if state.status == MissionStatus.COMPLETED
        else "yellow" if state.status == MissionStatus.WAITING_HUMAN
        else "red"
    )
    risks_lines = "\n".join(f"   ⚠️  {r}" for r in top_risks) or "   (nenhum risco crítico listado)"

    error_line = ""
    if state.status != MissionStatus.COMPLETED:
        err = state.mode_payload.get("error", "")
        stage = state.mode_payload.get("error_stage", "")
        error_line = f"\n[bold red]Erro ({stage}):[/bold red] [dim]{err}[/dim]"

    console.print()
    console.print(Panel(
        f"[bold]Status:[/bold] [{status_style}]{state.status.value}[/{status_style}]\n"
        f"[bold]Veredito:[/bold] [bold yellow]{verdict}[/bold yellow]  "
        f"[dim]Confiança:[/dim] {confidence:.2f}{error_line}\n\n"
        f"[bold]Top Riscos:[/bold]\n{risks_lines}\n\n"
        f"[bold]Experimentos:[/bold] {len(experiments)} proposto(s)\n"
        f"[dim]Mission ID:[/dim] {state.mission_id}\n"
        f"[dim]Diretório:[/dim] {pipe.artifacts.root / state.mission_id}",
        title="[bold]🔎 Validação concluída[/bold]", border_style=status_style, padding=(1, 2),
    ))
    return 0 if state.status in (MissionStatus.COMPLETED, MissionStatus.WAITING_HUMAN) else 1