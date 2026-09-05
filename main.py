"""
Fundador IA v2.0 — CLI Principal (Sprint 4 — MVP Congelado)

Uso:
    python main.py                              Menu interativo
    python main.py "Missão"                     Deliberação direta
    python main.py "Missão" -f README.md        Com arquivo de contexto
    python main.py --last                        Reexecutar última deliberação
    python main.py --last -f outro.md           Reexecutar com novo contexto
    python main.py --rerun <ID>                 Reexecutar por ID
    python main.py --history                    Ver histórico
    python main.py --history -n 10              Últimas 10 deliberações
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
# Parser com help rico
# ─────────────────────────────────────────

class _RichHelpFormatter(argparse.HelpFormatter):
    """HelpFormatter que adiciona cabeçalho visual ao --help."""
    def format_help(self) -> str:
        return (
            "\n  🏛  Fundador IA v2.0 — Conselho Consultivo Artificial\n"
            "  ─────────────────────────────────────────────────────\n\n"
            + super().format_help()
            + "\n  Exemplos:\n"
            "    python main.py \"Criar um app de finanças para MEIs\"\n"
            "    python main.py \"Missão\" -f README.md -f docs/PRD.md\n"
            "    python main.py --last\n"
            "    python main.py --rerun abc12345-...\n"
            "    python main.py --history -n 10\n"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Avalia missões de produto via Conselho Consultivo de IAs.",
        formatter_class=_RichHelpFormatter,
        add_help=True,
    )
    parser.add_argument(
        "mission", nargs="?", default=None,
        help="Texto da missão a ser avaliada pelo Conselho.",
    )
    parser.add_argument(
        "-f", "--file",
        action="append", dest="files", default=[], metavar="ARQUIVO",
        help="Arquivo de contexto a anexar (repetível). Ex: -f README.md",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Exibir histórico de deliberações anteriores.",
    )
    parser.add_argument(
        "-n",
        type=int, default=5, dest="history_limit", metavar="N",
        help="Número de entradas no histórico (padrão: 5).",
    )
    parser.add_argument(
        "--last",
        action="store_true",
        help="Reexecutar a última deliberação salva.",
    )
    parser.add_argument(
        "--rerun", metavar="ID",
        help="Reexecutar uma deliberação específica pelo ID.",
    )
    return parser


def _parse_args() -> argparse.Namespace:
    parser = _build_parser()
    args = parser.parse_args()

    if not any([args.history, args.last, args.rerun, args.mission]):
        return _interactive_menu()

    return args


# ─────────────────────────────────────────
# Menu interativo
# ─────────────────────────────────────────

def _interactive_menu() -> argparse.Namespace:
    ns = argparse.Namespace(
        mission=None, files=[], history=False, history_limit=5,
        last=False, rerun=None,
    )
    console.print()
    console.print(
        Panel(
            "[bold cyan]Fundador IA v2.0[/bold cyan] — Conselho Consultivo Artificial\n\n"
            "  [bold][1][/bold]  Nova Missão\n"
            "  [bold][2][/bold]  Reexecutar Última Deliberação\n"
            "  [bold][3][/bold]  Ver Histórico de Decisões\n"
            "  [bold][4][/bold]  Sair",
            title="[bold cyan]🏛  Menu Principal[/bold cyan]",
            border_style="cyan",
            padding=(1, 3),
        )
    )
    choice = console.input("\n[bold]Escolha uma opção:[/bold] ").strip()

    if choice == "1":
        ns.mission = console.input("\n[bold]📋 Missão:[/bold] ").strip()
        if not ns.mission:
            _exit_error("Missão não pode ser vazia.")
        file_input = console.input(
            "[dim]📁 Arquivos de contexto (separados por vírgula ou Enter para pular):[/dim] "
        ).strip()
        if file_input:
            ns.files = [f.strip() for f in file_input.split(",") if f.strip()]
    elif choice == "2":
        ns.last = True
    elif choice == "3":
        ns.history = True
    elif choice == "4":
        console.print("\n[dim]Encerrando. Até logo![/dim]\n")
        sys.exit(0)
    else:
        _exit_error(f"Opção inválida: '{choice}'. Escolha entre 1 e 4.")

    return ns


# ─────────────────────────────────────────
# Utilitários de saída
# ─────────────────────────────────────────

def _exit_error(message: str, exception: Exception | None = None) -> None:
    """Exibe erro amigável e encerra com código 1. Nunca expõe stack trace."""
    detail = str(exception) if exception else ""
    body = message + (f"\n\n[dim]{detail}[/dim]" if detail else "")
    console.print()
    console.print(
        Panel(
            body,
            title="[bold red]⚠  Erro[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )
    sys.exit(1)


def _print_warning(message: str) -> None:
    console.print(f"  [bold yellow]⚠  {message}[/bold yellow]")


def _print_success(message: str) -> None:
    console.print(f"  [bold green]✅ {message}[/bold green]")


def _print_info(message: str) -> None:
    console.print(f"  [dim]{message}[/dim]")


# ─────────────────────────────────────────
# Reexecução
# ─────────────────────────────────────────

def _load_for_rerun(
    use_last: bool,
    rerun_id: str | None,
    override_files: list[str],
) -> tuple[str, list[str]]:
    try:
        from backend.core.history import get_decision_by_id, get_last_decision
    except Exception as e:
        _exit_error("Falha ao carregar módulo de histórico.", e)

    entry: dict | None = None

    if use_last:
        try:
            entry = get_last_decision()
        except Exception as e:
            _exit_error("Falha ao ler o histórico de deliberações.", e)
        if not entry:
            _exit_error(
                "Nenhuma deliberação anterior encontrada.\n"
                "Execute uma deliberação primeiro com: python main.py \"sua missão\""
            )

    elif rerun_id:
        try:
            entry = get_decision_by_id(rerun_id)
        except Exception as e:
            _exit_error("Falha ao buscar deliberação no histórico.", e)
        if not entry:
            _exit_error(
                f"Deliberação com ID [bold]{rerun_id}[/bold] não encontrada.\n"
                "Use [bold]python main.py --history[/bold] para ver os IDs disponíveis."
            )

    assert entry is not None

    mission: str = entry["mission"]
    files: list[str] = override_files if override_files else (entry.get("context_files") or [])

    console.print()
    console.print(
        Panel(
            f"[dim]ID original:[/dim] [bold]{entry['id']}[/bold]\n"
            f"[dim]Data:[/dim] {entry['timestamp']}",
            title="[bold cyan]🔄 Reexecutando Deliberação[/bold cyan]",
            border_style="cyan",
            padding=(0, 2),
        )
    )
    return mission, files


# ─────────────────────────────────────────
# Contexto com resumo em KB
# ─────────────────────────────────────────

def _prepare_context(file_paths: list[str]) -> tuple[str, list[str]]:
    if not file_paths:
        return "", []

    from backend.tools.file_tools import _PROJECT_ROOT, prepare_context_payload  # noqa: PLC0415

    project_root: Path = Path(_PROJECT_ROOT)  # type annotation explícita elimina Unbound

    try:
        payload = prepare_context_payload(file_paths)
    except Exception as e:
        _exit_error("Falha ao preparar contexto de arquivos.", e)

    console.print()
    if payload.included_files:
        console.print("[dim]📁 Contexto Anexado:[/dim]")
        for f in payload.included_files:
            try:
                size_kb = (project_root / f).stat().st_size / 1024
                size_str = f"{size_kb:.1f} KB"
            except OSError:
                size_str = "? KB"
            flag = " [bold yellow](truncado)[/bold yellow]" if f in payload.truncated_files else ""
            console.print(f"   [green]📄[/green] {Path(f).name} [dim]({size_str})[/dim]{flag}")

    for f in payload.omitted_files:
        _print_warning(f"{Path(f).name} omitido — limite de contexto atingido.")

    for w in payload.warnings:
        _print_warning(w)

    if payload.included_files or payload.omitted_files:
        console.print()

    return payload.block, payload.included_files


# ─────────────────────────────────────────
# Histórico
# ─────────────────────────────────────────

def _show_history(limit: int) -> None:
    try:
        from backend.core.history import get_recent_decisions
        decisions = get_recent_decisions(limit)
    except Exception as e:
        _exit_error("Falha ao ler o histórico de deliberações.", e)

    if not decisions:
        console.print()
        console.print(
            Panel(
                "[dim]Nenhuma deliberação encontrada.\n"
                "Execute [bold]python main.py \"sua missão\"[/bold] para começar.[/dim]",
                title="[bold cyan]📋 Histórico de Deliberações[/bold cyan]",
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
        verdict_str = (
            "[green]✅ APPROVED[/green]" if d["final_verdict"] == "APPROVED"
            else "[red]❌ REJECTED[/red]"
        )
        files = d.get("context_files") or []
        files_str = ", ".join(Path(f).name for f in files) if files else "—"
        short_id = (d.get("id") or "")[:8] + "…"

        table.add_row(
            d["timestamp"], short_id, mission_short,
            f"[{score_style}]{score:.2f}[/{score_style}]",
            verdict_str, files_str,
        )

    console.print()
    console.print(table)
    console.print(
        "\n[dim]Dica: python main.py --rerun <ID completo> para reexecutar.[/dim]\n"
    )


# ─────────────────────────────────────────
# Renderização da deliberação
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
            title="[bold cyan]🏛  Fundador IA v2.0[/bold cyan]",
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
    reason_line = (
        f"\n[dim]Motivo: [/dim][italic]{decision.reason}[/italic]"
        if getattr(decision, "reason", "") else ""
    )
    console.print()
    console.print(
        Panel(
            f"{'✅' if approved else '❌'} Veredito Final: "
            f"{'[bold green]APPROVED[/bold green]' if approved else '[bold red]REJECTED[/bold red]'}\n"
            f"[dim]Score Médio: [/dim][bold]{decision.average_score:.2f}/10.0[/bold]"
            f"{reason_line}",
            title="[bold]🎯 Decisão do Conselho[/bold]",
            border_style="green" if approved else "red",
            padding=(1, 2),
        )
    )


# ─────────────────────────────────────────
# Deliberação com spinner
# ─────────────────────────────────────────

async def _run_with_spinner(mission: str, context_block: str):
    from backend.agents.council import JURORS, _evaluate_juror
    from backend.core.llm_client import LLMProviderError
    from backend.schemas.council import CouncilDecision, JurorResponse, JurorVerdict

    responses: list[JurorResponse] = []

    for juror in JURORS:
        with console.status(
            f"[cyan]Consultando Jurado [{juror['name']}]...[/cyan]",
            spinner="dots",
        ):
            try:
                response = await _evaluate_juror(juror, mission, context_block)
            except LLMProviderError as e:
                _exit_error(
                    f"Falha ao consultar o Jurado [{juror['name']}].\n{e}",
                )
            except RuntimeError as e:
                _exit_error(str(e))
            except Exception as e:
                _exit_error(
                    f"Erro inesperado ao consultar [{juror['name']}].",
                    exception=e,
                )

        responses.append(response)
        score_style = (
            "green" if response.score >= 7.0 else
            "yellow" if response.score >= 5.0 else "red"
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
# Entry point com tratamento global
# ─────────────────────────────────────────

async def main() -> None:
    args = _parse_args()

    # ── Histórico ──
    if args.history:
        _show_history(args.history_limit)
        sys.exit(0)

    # ── Reexecução ──
    if args.last or args.rerun:
        mission, prev_files = _load_for_rerun(
            use_last=args.last,
            rerun_id=args.rerun,
            override_files=args.files,
        )
    else:
        mission = args.mission or ""
        prev_files = args.files

    if not mission:
        _exit_error("Missão não pode ser vazia.")

    # ── Contexto ──
    context_block, included_files = _prepare_context(prev_files)
    _render_header(mission, included_files)

    # ── Deliberação ──
    decision = await _run_with_spinner(mission, context_block)

    _render_scores_table(decision)
    _render_final_verdict(decision)

    # ── Persistência ──
    console.print()
    with console.status("[dim]Salvando decisão...[/dim]", spinner="dots"):
        try:
            from backend.core.history import save_council_decision
            deliberation_id = save_council_decision(decision, included_files)
        except Exception as e:
            _print_warning(f"Falha ao salvar decisão: {e}")
            deliberation_id = "não salvo"

    _print_success(f"Decisão registrada — ID: {deliberation_id}")
    console.print()
    sys.exit(0)


# ─────────────────────────────────────────
# Guarda de topo com tratamento global
# ─────────────────────────────────────────

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n\n[dim]Interrompido pelo usuário.[/dim]\n")
        sys.exit(0)
    except SystemExit:
        raise  # Deixa sys.exit() propagar normalmente
    except Exception as e:
        console.print()
        console.print(
            Panel(
                f"[bold]Erro inesperado:[/bold] {type(e).__name__}\n\n"
                f"[dim]{e}[/dim]",
                title="[bold red]⚠  Erro Crítico[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        sys.exit(1)