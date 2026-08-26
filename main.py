"""
Fundador IA — CLI Principal (Sprint 2 — Final)
Interface rich com spinner, tabela de scores, painéis e suporte a arquivos de contexto.

Uso:
    python main.py
    python main.py "Minha missão"
    python main.py "Minha missão" -f README.md
    python main.py "Minha missão" -f README.md -f docs/PRD.md
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


# ─────────────────────────────────────────
# Argumentos CLI
# ─────────────────────────────────────────

def _parse_args() -> tuple[str, list[str]]:
    """
    Parseia argumentos da linha de comando.
    Retorna (mission, context_files).
    Ativa modo interativo se nenhum argumento for fornecido.
    """
    parser = argparse.ArgumentParser(
        prog="fundador-ia",
        description="Fundador IA — Conselho Consultivo Artificial",
        add_help=True,
    )
    parser.add_argument(
        "mission",
        nargs="?",
        default=None,
        help="Missão a ser avaliada pelo Conselho.",
    )
    parser.add_argument(
        "-f", "--file",
        action="append",
        dest="files",
        default=[],
        metavar="ARQUIVO",
        help="Arquivo de contexto a ser anexado (pode ser usado múltiplas vezes).",
    )

    args = parser.parse_args()

    # ── Modo interativo ──
    if args.mission is None:
        console.print()
        console.print(
            Panel(
                "[bold cyan]Fundador IA[/bold cyan] — Conselho Consultivo Artificial\n"
                "[dim]Nenhuma missão fornecida. Modo interativo ativado.[/dim]",
                border_style="cyan",
            )
        )
        mission = console.input(
            "\n[bold]📋 Digite a missão a ser avaliada:[/bold] "
        ).strip()
        if not mission:
            console.print("[red]Missão não pode ser vazia. Encerrando.[/red]")
            sys.exit(1)

        file_input = console.input(
            "[dim]📁 Deseja anexar algum arquivo de contexto? "
            "(ex: README.md ou pressione Enter para pular):[/dim] "
        ).strip()
        if file_input:
            args.files = [f.strip() for f in file_input.split(",") if f.strip()]
        args.mission = mission

    return args.mission, args.files


# ─────────────────────────────────────────
# Validação e exibição de arquivos
# ─────────────────────────────────────────

def _resolve_context_files(file_paths: list[str]) -> list[str]:
    """
    Valida e exibe os arquivos de contexto a serem anexados.
    Retorna apenas os caminhos válidos.
    """
    if not file_paths:
        return []

    from backend.tools.file_tools import _PROJECT_ROOT

    valid: list[str] = []
    console.print()

    for path_str in file_paths:
        resolved = (Path(".") / path_str).resolve()
        if resolved.exists() and resolved.is_file():
            rel = str(resolved.relative_to(_PROJECT_ROOT.resolve()))
            valid.append(rel)
            console.print(f"  [green]📄 Anexado:[/green] {rel}")
        else:
            console.print(f"  [yellow]⚠  Não encontrado:[/yellow] {path_str}")

    if valid:
        console.print()
    return valid


# ─────────────────────────────────────────
# Renderização
# ─────────────────────────────────────────

def _render_header(mission: str, context_files: list[str]) -> None:
    context_info = (
        f"\n\n[dim]Contexto:[/dim] {', '.join(Path(f).name for f in context_files)}"
        if context_files
        else ""
    )
    console.print()
    console.print(
        Panel(
            f"[bold white]Conselho Consultivo Artificial[/bold white]\n\n"
            f"[dim]Missão:[/dim]\n[italic]{mission}[/italic]{context_info}",
            title="[bold cyan]🏛  Fundador IA[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()


def _render_scores_table(decision) -> None:
    table = Table(
        title="Avaliações do Conselho",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Jurado", style="bold", min_width=16)
    table.add_column("Score", justify="center", min_width=8)
    table.add_column("Veredicto", justify="center", min_width=12)
    table.add_column("Raciocínio", min_width=44)

    for r in decision.juror_responses:
        score_style = (
            "green" if r.score >= 7.0
            else "yellow" if r.score >= 5.0
            else "red"
        )
        verdict_str = (
            "[green]✅ APPROVE[/green]"
            if r.verdict.value == "APPROVE"
            else "[red]🚫 VETO[/red]"
        )
        reasoning_short = r.reasoning[:80] + ("…" if len(r.reasoning) > 80 else "")
        table.add_row(
            r.juror_name,
            f"[{score_style}]{r.score:.1f}/10[/{score_style}]",
            verdict_str,
            reasoning_short,
        )

    console.print()
    console.print(table)


def _render_final_verdict(decision) -> None:
    approved = decision.final_verdict == "APPROVED"
    border = "green" if approved else "red"
    icon = "✅" if approved else "❌"
    label = (
        "[bold green]APPROVED[/bold green]"
        if approved
        else "[bold red]REJECTED[/bold red]"
    )
    console.print()
    console.print(
        Panel(
            f"{icon} Veredito Final: {label}\n"
            f"[dim]Score Médio: [/dim][bold]{decision.average_score:.2f}/10.0[/bold]",
            title="[bold]🎯 Decisão do Conselho[/bold]",
            border_style=border,
            padding=(1, 2),
        )
    )


def _render_error(error: Exception) -> None:
    console.print()
    console.print(
        Panel(
            f"[bold]{type(error).__name__}[/bold]\n\n{str(error)}",
            title="[bold red]⚠  Erro[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )


# ─────────────────────────────────────────
# Orquestração com spinner por jurado
# ─────────────────────────────────────────

async def _run_with_spinner(mission: str, context_files: list[str]) -> object:
    """Executa jurados sequencialmente com spinner individual por jurado."""
    from backend.agents.council import JURORS, _evaluate_juror
    from backend.schemas.council import CouncilDecision, JurorResponse, JurorVerdict
    from backend.tools.file_tools import build_context_block

    context_block: str = build_context_block(context_files) if context_files else ""
    responses: list[JurorResponse] = []

    for juror in JURORS:
        with console.status(
            f"[cyan]Consultando Jurado [{juror['name']}]...[/cyan]",
            spinner="dots",
        ):
            response = await _evaluate_juror(juror, mission, context_block)

        responses.append(response)

        score_style = (
            "green" if response.score >= 7.0
            else "yellow" if response.score >= 5.0
            else "red"
        )
        verdict_icon = "✅" if response.verdict.value == "APPROVE" else "🚫"
        console.print(
            f"  [bold]{response.juror_name}[/bold] — "
            f"Score: [{score_style}]{response.score:.1f}/10[/{score_style}] "
            f"{verdict_icon} {response.verdict.value}"
        )

    average_score = round(sum(r.score for r in responses) / len(responses), 2)
    security = next((r for r in responses if r.juror_name == "SecurityCoder"), None)
    security_vetoed = security is not None and security.verdict == JurorVerdict.VETO
    security_ok = security is not None and security.score >= 5.0

    final_verdict = (
        "APPROVED"
        if average_score >= 8.0 and not security_vetoed and security_ok
        else "REJECTED"
    )

    return CouncilDecision(
        mission=mission,
        final_verdict=final_verdict,
        average_score=average_score,
        juror_responses=responses,
    )


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────

async def main() -> None:
    from backend.core.llm_client import (
        OllamaInvalidResponseError,
        OllamaTimeoutError,
        OllamaUnavailableError,
    )
    from backend.storage.decisions import save_council_decision

    mission, raw_files = _parse_args()
    context_files = _resolve_context_files(raw_files)
    _render_header(mission, context_files)

    try:
        decision = await _run_with_spinner(mission, context_files)
    except (OllamaUnavailableError, OllamaTimeoutError, OllamaInvalidResponseError) as e:
        _render_error(e)
        sys.exit(1)
    except RuntimeError as e:
        _render_error(e)
        sys.exit(1)
    except Exception as e:
        _render_error(e)
        sys.exit(1)

    _render_scores_table(decision)
    _render_final_verdict(decision)

    console.print()
    with console.status(
        "[dim]Salvando decisão em docs/DECISIONS.md...[/dim]", spinner="dots"
    ):
        save_council_decision(decision)
    console.print("[dim]💾 Decisão registrada em docs/DECISIONS.md[/dim]")
    console.print()


if __name__ == "__main__":
    asyncio.run(main())