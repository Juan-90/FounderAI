"""
CLI helper do Modo DISCOVER (v4.7.0) — tabela de ranking + detalhes + atalhos.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from backend.discover.pipeline import DiscoverPipeline
from backend.discover.schemas import DiscoverRequest

console = Console()


async def run_discover_mode(
    intent: str,
    max_opportunities: int = 8,
    handoff_id: Optional[str] = None,
    pipeline: Optional[DiscoverPipeline] = None,
) -> int:
    if not intent or not intent.strip():
        console.print(Panel(
            'Informe o tema.\nEx: python main.py discover "Oportunidades de software '
            'para barbearias no Brasil"',
            title="[bold red]⚠  Tema vazio[/bold red]", border_style="red", padding=(1, 2),
        ))
        return 1

    request = DiscoverRequest(
        theme=intent,
        max_opportunities=max_opportunities,
        handoff_to_validate=handoff_id is not None,
        selected_opportunity_id=handoff_id,
    )
    pipe = pipeline if pipeline is not None else DiscoverPipeline()

    console.print("[bold magenta]🧭 Modo DISCOVER[/bold magenta] — mapeamento de oportunidades")
    result = await pipe.run(request)

    table = Table(title="Ranking de Oportunidades", show_header=True,
                  header_style="bold magenta", border_style="dim", padding=(0, 1))
    table.add_column("ID", style="dim", min_width=22)
    table.add_column("Título", min_width=34)
    table.add_column("Score", justify="center", min_width=7)
    table.add_column("Evidência", justify="center", min_width=10)
    for p in result.opportunities:
        score_style = "green" if p.score >= 0.7 else "yellow" if p.score >= 0.5 else "red"
        table.add_row(p.id, p.title, f"[{score_style}]{p.score:.2f}[/{score_style}]",
                      p.evidence_level)
    console.print()
    console.print(table)

    for p in result.opportunities[:3]:
        console.print(Panel(
            f"[italic]{p.one_liner}[/italic]\n\n"
            f"[dim]Problema:[/dim] {p.problem}\n"
            f"[dim]Por quê agora:[/dim] {p.why_now}\n"
            f"[dim]Riscos:[/dim] {', '.join(p.risks) or '—'}",
            title=f"[bold]{p.title}[/bold] ({p.score:.2f})",
            border_style="magenta", padding=(1, 2),
        ))

    if result.rejected:
        console.print(f"[yellow]⚠  {len(result.rejected)} rejeitada(s) pelo critic:[/yellow]")
        for r in result.rejected[:5]:
            console.print(f"   [dim]•[/dim] {r['title']} — {r['reason']}")

    if pipe.last_handoff:
        console.print(
            f"[bold green]🔗 Handoff:[/bold green] oportunidade "
            f"{pipe.last_handoff['opportunity_id']} → validação "
            f"{pipe.last_handoff['validate_mission_id']}"
        )
    elif result.opportunities:
        top = result.opportunities[0]
        console.print(
            f"\n[dim]Atalho validar top:[/dim] python main.py validate "
            f'"{top.title}: {top.one_liner}"'
        )
        console.print(
            f"[dim]Atalho handoff:[/dim] python main.py discover \"{intent}\" "
            f"--handoff {top.id}"
        )

    console.print(f"\n[dim]{result.summary}[/dim]")
    return 0 if result.opportunities else 1