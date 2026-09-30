"""
CLI helper do comando golden-missions (v5.0.0 GA).
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from backend.cli import summary_panel
from backend.golden.runner import GoldenRunner

console = Console()


async def run_golden_mode(pipeline: GoldenRunner | None = None) -> int:
    runner = pipeline if pipeline is not None else GoldenRunner()
    console.print("[bold cyan]🏅 Golden Missions — regressão GA[/bold cyan]")
    report = await runner.run()

    table = Table(title="Golden Missions", show_header=True,
                  header_style="bold cyan", border_style="dim", padding=(0, 1))
    table.add_column("ID", style="dim", min_width=4)
    table.add_column("Missão", min_width=30)
    table.add_column("Modo", min_width=18)
    table.add_column("Resultado", justify="center", min_width=10)
    for r in report.results:
        table.add_row(r.id, r.name, r.mode.value,
                      "[green]OK[/green]" if r.success else "[red]FAIL[/red]")
    console.print()
    console.print(table)

    summary_panel(
        "🏅 Golden Missions",
        report.all_passed,
        [report.summary, f"Artefatos: {report.artifacts_path}"],
    )
    return 0 if report.all_passed else 1