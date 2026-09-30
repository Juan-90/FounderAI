"""
CLI helper do Modo SELF-AUDIT (v4.6.0) — painel Rich do Scorecard.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from backend.self_audit.pipeline import SelfAuditPipeline
from backend.self_audit.schemas import SelfAuditRequest

console = Console()


async def run_self_audit_mode(
    no_build: bool = False,
    no_validate: bool = False,
    no_vab: bool = False,
    max_per_mode: int = 3,
    pipeline: SelfAuditPipeline | None = None,
) -> int:
    request = SelfAuditRequest(
        include_build=not no_build,
        include_validate=not no_validate,
        include_validate_and_build=not no_vab,
        max_missions_per_mode=max_per_mode,
    )
    pipe = pipeline if pipeline is not None else SelfAuditPipeline()

    console.print("[bold green]🩺 SELF-AUDIT — Auditoria Interna[/bold green]")
    with console.status("[cyan]Executando missões canônicas...[/cyan]", spinner="dots"):
        scorecard = await pipe.run(request)

    style = (
        "green" if scorecard.overall_verdict == "HEALTHY"
        else "yellow" if scorecard.overall_verdict == "DEGRADED"
        else "red"
    )
    findings = "\n".join(f"   ⚠️  {f}" for f in scorecard.adversarial_findings[:5]) or "   (nenhum)"
    console.print()
    console.print(Panel(
        f"[bold]Veredito:[/bold] [{style}]{scorecard.overall_verdict}[/{style}]  "
        f"[dim]Confiança:[/dim] {scorecard.confidence:.2f}\n"
        f"[bold]Taxa de Sucesso:[/bold] {scorecard.success_rate:.0%} "
        f"({scorecard.total_missions} missões)\n"
        f"[dim]BUILD:[/dim] {scorecard.build_success_rate if scorecard.build_success_rate is not None else '—'}  "
        f"[dim]VALIDATE:[/dim] {scorecard.validate_success_rate if scorecard.validate_success_rate is not None else '—'}  "
        f"[dim]VAB:[/dim] {scorecard.vab_success_rate if scorecard.vab_success_rate is not None else '—'}\n"
        f"[bold]Checks objetivos:[/bold] {scorecard.objective_checks_passed}/"
        f"{scorecard.objective_checks_total}\n\n"
        f"[bold]Achados adversariais:[/bold]\n{findings}\n\n"
        f"[dim]{scorecard.summary}[/dim]",
        title="[bold]🩺 Scorecard SELF-AUDIT[/bold]", border_style=style, padding=(1, 2),
    ))
    return 0 if scorecard.overall_verdict in ("HEALTHY", "DEGRADED") else 1