"""
Fundador IA — CLI Principal (Sprint 3 — Completo)
Menu interativo, reexecução (--last / --rerun), resumo de contexto em KB.

Uso:
    python main.py                          # menu interativo
    python main.py "Minha missão"           # deliberação direta
    python main.py "Missão" -f README.md   # com contexto
    python main.py --last                   # reexecuta última deliberação
    python main.py --last -f outro.md      # reexecuta substituindo arquivos
    python main.py --rerun <ID>            # reexecuta por ID específico
    python main.py --history               # exibe histórico
    python main.py --history -n 10         # últimas 10
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# ─────────────────────────────────────────
# Parser
# ─────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fundador-ia",
        description="Fundador IA — Conselho Consultivo Artificial",
        add_help=True,
    )
    parser.add_argument("mission", nargs="?", default=None,
                        help="Missão a ser avaliada.")
    parser.add_argument("-f", "--file", action="append", dest="files",
                        default=[], metavar="ARQUIVO",
                        help="Arquivo de contexto (repetível).")
    parser.add_argument("--history", action="store_true",
                        help="Exibir histórico de deliberações.")
    parser.add_argument("-n", type=int, default=5, dest="history_limit",
                        metavar="N", help="Entradas no histórico (padrão: 5).")
    parser.add_argument("--last", action="store_true",
                        help="Reexecutar a última deliberação salva.")
    parser.add_argument("--rerun", metavar="ID",
                        help="Reexecutar deliberação por ID específico.")
    return parser


# ─────────────────────────────────────────
# Menu interativo
# ─────────────────────────────────────────

def _interactive_menu() -> argparse.Namespace:
    """Exibe menu numerado e retorna Namespace configurado."""
    console.print()
    console.print(
        Panel(
            "[bold cyan]Fundador IA[/bold cyan] — Conselho Consultivo Artificial\n"
            "[dim]O que deseja fazer?[/dim]\n\n"
            "  [bold][1][/bold] Nova Missão\n"
            "  [bold][2][/bold] Reexecutar Última Missão\n"
            "  [bold][3][/bold] Ver Histórico de Decisões\n"
            "  [bold][4][/bold] Sair",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    choice = console.input("\n[bold]Escolha:[/bold] ").strip()

    ns = argparse.Namespace(
        mission=None, files=[], history=False, history_limit=5,
        last=False, rerun=None,
    )

    if choice == "1":
        ns.mission = console.input(
            "\n[bold]📋 Digite a missão:[/bold] "
        ).strip()
        if not ns.mission:
            console.print("[red]Missão não pode ser vazia.[/red]")
            sys.exit(1)
        file_input = console.input(
            "[dim]📁 Arquivo(s) de contexto (Enter para pular):[/dim] "
        ).strip()
        if file_input:
            ns.files = [f.strip() for f in file_input.split(",") if f.strip()]

    elif choice == "2":
        ns.last = True

    elif choice == "3":
        ns.history = True

    elif choice == "4":
        console.print("[dim]Encerrando.[/dim]")
        sys.exit(0)

    else:
        console.print("[red]Opção inválida.[/red]")
        sys.exit(1)

    return ns


def _parse_args() -> argparse.Namespace:
    parser = _build_parser()
    args = parser.parse_args()

    # Nenhum argumento → menu interativo
    if (not args.history and not args.last
            and args.rerun is None and args.mission is None):
        return _interactive_menu()

    return args


# ─────────────────────────────────────────
# Reexecução
# ─────────────────────────────────────────

def _load_for_rerun(
    use_last: bool,
    rerun_id: str | None,
    override_files: list[str],
) -> tuple[str, list[str]]:
    """
    Carrega missão e arquivos de uma deliberação anterior.
    Se override_files fornecido, substitui os arquivos originais.
    """
    from backend.core.history import get_decision_by_id, get_last_decision

    entry: dict | None = None

    if use_last:
        entry = get_last_decision()
        if not entry:
            console.print(
                Panel(
                    "[dim]Nenhuma deliberação anterior encontrada.[/dim]",
                    title="[yellow]⚠  Reexecução[/yellow]",
                    border_style="yellow",
                )
            )
            sys.exit(1)

    elif rerun_id:
        entry = get_decision_by_id(rerun_id)
        if not entry:
            console.print(
                Panel(
                    f"[dim]Deliberação com ID [bold]{rerun_id}[/bold] não encontrada.[/dim]",
                    title="[yellow]⚠  Reexecução[/yellow]",
                    border_style="yellow",
                )
            )
            sys.exit(1)

    assert entry is not None  # type narrowing — sys.exit já garantiu isso acima

    mission: str = entry["mission"]
    # Usa override se fornecido, senão usa os originais
    files: list[str] = override_files if override_files else (entry.get("context_files") or [])

    console.print()
    console.print(
        Panel(
            f"[dim]Reexecutando deliberação[/dim]\n"
            f"[bold]ID original:[/bold] {entry['id']}\n"
            f"[bold]Data:[/bold] {entry['timestamp']}",
            title="[bold cyan]🔄 Reexecução[/bold cyan]",
            border_style="cyan",
            padding=(0, 2),
        )
    )

    return mission, files


# ─────────────────────────────────────────
# Contexto com resumo em KB
# ─────────────────────────────────────────

def _prepare_context(file_paths: list[str]) -> tuple[str, list[str]]:
    """Prepara contexto com limites e exibe resumo em KB."""
    if not file_paths:
        return "", []

    from backend.tools.file_tools import _PROJECT_ROOT, prepare_context_payload

    console.print()
    payload = prepare_context_payload(file_paths)

    if payload.included_files:
        console.print("[dim]📁 Contexto Anexado:[/dim]")
        for f in payload.included_files:
            try:
                resolved = (_PROJECT_ROOT / f).resolve()
                size_kb = resolved.stat().st_size / 1024
                size_str = f"{size_kb:.1f} KB"
            except OSError:
                size_str = "? KB"

            flag = " [yellow](truncado)[/yellow]" if f in payload.truncated_files else ""
            console.print(
                f"   [green]📄[/green] {Path(f).name} "
                f"[dim]({size_str})[/dim]{flag}"
            )

    for f in payload.omitted_files:
        console.print(
            f"   [yellow]⚠  Omitido:[/yellow] {Path(f).name} "
            f"[dim](limite de contexto atingido)[/dim]"
        )

    for w in payload.warnings:
        console.print(f"   [yellow]ℹ  {w}[/yellow]")

    if payload.included_files or payload.omitted_files:
        console.print()

    return payload.block, payload.included_files


# ─────────────────────────────────────────
# Histórico
# ─────────────────────────────────────────

def _show_history(limit: int) -> None:
    from backend.core.history import get_recent_decisions

    decisions = get_recent_decisions(limit)

    if not decisions:
        console.print()
        console.print(
            Panel(
                "[dim]Nenhuma deliberação encontrada.\n"
                "Execute [bold]python main.py[/bold] para começar.[/dim]",
                title="[bold cyan]📋 Histórico[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        return

    table = Table(
        title=f"Últimas {len(decisions)} Deliberações",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Data/Hora", min_width=18, style="dim")
    table.add_column("ID", min_width=10, style="dim")
    table.add_column("Missão", min_width=34)
    table.add_column("Score", justify="center", min_width=7)
    table.add_column("Veredito", justify="center", min_width=12)
    table.add_column("Contexto", min_width=14, style="dim")

    for d in decisions:
        mission_short = d["mission"][:55] + ("…" if len(d["mission"]) > 55 else "")
        score = d["average_score"]
        score_style = "green" if score >= 7.0 else "yellow" if score >= 5.0 else "red"
        verdict = d["final_verdict"]
        verdict_str = (
            "[green]✅ APPROVED[/green]" if verdict == "APPROVED"
            else "[red]❌ REJECTED[/red]"
        )
        files = d.get("context_files") or []
        files_str = ", ".join(Path(f).name for f in files) if files else "—"
        short_id = d.get("id", "")[:8] + "…"

        table.add_row(
            d["timestamp"], short_id, mission_short,
            f"[{score_style}]{score:.2f}[/{score_style}]",
            verdict_str, files_str,
        )

    console.print()
    console.print(table)
    console.print(
        f"[dim]Dica: python main.py --rerun <ID> para reexecutar uma deliberação.[/dim]"
    )
    console.print()


# ─────────────────────────────────────────
# Renderização
# ─────────────────────────────────────────

def _render_header(mission: str, included_files: list[str]) -> None:
    context_info = (
        f"\n\n[dim]Contexto:[/dim] {', '.join(Path(f).name for f in included_files)}"
        if included_files else ""
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
            "green" if r.score >= 7.0 else "yellow" if r.score >= 5.0 else "red"
        )
        verdict_str = (
            "[green]✅ APPROVE[/green]" if r.verdict.value == "APPROVE"
            else "[red]🚫 VETO[/red]"
        )
        reasoning_short = r.reasoning[:80] + ("…" if len(r.reasoning) > 80 else "")
        table.add_row(
            r.juror_name,
            f"[{score_style}]{r.score:.1f}/10[/{score_style}]",
            verdict_str, reasoning_short,
        )

    console.print()
    console.print(table)


def _render_final_verdict(decision) -> None:
    approved = decision.final_verdict == "APPROVED"
    console.print()
    console.print(
        Panel(
            f"{'✅' if approved else '❌'} Veredito Final: "
            f"{'[bold green]APPROVED[/bold green]' if approved else '[bold red]REJECTED[/bold red]'}\n"
            f"[dim]Score Médio: [/dim][bold]{decision.average_score:.2f}/10.0[/bold]",
            title="[bold]🎯 Decisão do Conselho[/bold]",
            border_style="green" if approved else "red",
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
# Deliberação com spinner
# ─────────────────────────────────────────

async def _run_with_spinner(mission: str, context_block: str):
    from backend.agents.council import JURORS, _evaluate_juror
    from backend.schemas.council import CouncilDecision, JurorResponse, JurorVerdict

    responses: list[JurorResponse] = []

    for juror in JURORS:
        with console.status(
            f"[cyan]Consultando Jurado [{juror['name']}]...[/cyan]",
            spinner="dots",
        ):
            response = await _evaluate_juror(juror, mission, context_block)

        responses.append(response)
        score_style = (
            "green" if response.score >= 7.0 else "yellow"
            if response.score >= 5.0 else "red"
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
    from backend.core.history import save_council_decision
    from backend.core.llm_client import LLMProviderError

    args = _parse_args()

    # ── Histórico ──
    if args.history:
        _show_history(args.history_limit)
        return

    # ── Reexecução ──
    if args.last or args.rerun:
        mission, prev_files = _load_for_rerun(
            use_last=args.last,
            rerun_id=args.rerun,
            override_files=args.files,
        )
    else:
        mission = args.mission
        prev_files = args.files

    # ── Contexto ──
    context_block, included_files = _prepare_context(prev_files)
    _render_header(mission, included_files)

    # ── Deliberação ──
    try:
        decision = await _run_with_spinner(mission, context_block)
    except LLMProviderError as e:
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

    # ── Persistência ──
    console.print()
    with console.status("[dim]Salvando decisão...[/dim]", spinner="dots"):
        deliberation_id = save_council_decision(decision, included_files)

    console.print(f"[dim]💾 Decisão registrada — ID: {deliberation_id}[/dim]")
    console.print()


if __name__ == "__main__":
    asyncio.run(main())