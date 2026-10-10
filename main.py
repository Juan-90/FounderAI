"""
Fundador IA v5.5.2 — CLI Principal.

Modos: council (default), build, validate, validate-and-build, self-audit,
discover, golden-missions, project (v5.3 + feedback v5.5), improve (v5.4),
smoke (v5.5).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Callable, NoReturn

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from backend.core.schemas import DeliberationState
from backend.schemas.council import JurorResponse

console = Console()

_CANCEL_TOKENS: frozenset[str] = frozenset({"cancel", "abort", "/cancel"})


class _RichHelpFormatter(argparse.HelpFormatter):
    def format_help(self) -> str:
        return (
            "\n  🏛  Fundador IA v5.5.2 — AI Project Operating System\n"
            "  ─────────────────────────────────────────────────────\n\n"
            + super().format_help()
            + "\n  Exemplos:\n"
            "    python main.py \"Criar app de finanças para MEIs\"\n"
            "    python main.py build \"Sistema de agendamento\" --project <id>\n"
            "    python main.py validate \"Ideia\" --project <id>\n"
            "    python main.py project list\n"
            "    python main.py project feedback <id> --rating 5 --note \"ótimo\"\n"
            "    python main.py improve --project <id> --auto-apply\n"
            "    python main.py smoke\n"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Avalia, descobre, valida, constrói, audita, melhora e observa missões.",
        formatter_class=_RichHelpFormatter,
    )
    parser.add_argument("mission", nargs="?", default=None,
                        help="'build'|'validate'|'validate-and-build'|'self-audit'|"
                             "'discover'|'golden-missions'|'project'|'improve'|'smoke'"
                             "| ou texto da missão.")
    parser.add_argument("build_intent", nargs="?", default=None,
                        help="Intent/tema (build/validate/.../discover) ou action do project.")
    parser.add_argument("project_target", nargs="?", default=None,
                        help="PROJECT: id do projeto p/ show/timeline/artifacts/feedback.")

    parser.add_argument("-f", "--file", action="append", dest="files", default=[],
                        metavar="ARQUIVO", help="Arquivo de contexto (repetível).")
    parser.add_argument("--project-name", default=None, dest="project_name",
                        metavar="NOME", help="BUILD: nome do projeto.")
    parser.add_argument("--type", default=None, dest="project_type",
                        choices=["WEB_APP", "INTERNAL_SYSTEM", "GAME"], metavar="TIPO")
    parser.add_argument("--project", default=None, dest="project_id", metavar="ID",
                        help="Vincula a missão à memória do projeto (v5.3).")
    parser.add_argument("--goal", default=None, dest="goal", metavar="TEXTO",
                        help="IMPROVE: novo goal do projeto.")
    parser.add_argument("--auto-apply", action="store_true", dest="auto_apply",
                        help="IMPROVE: aplica o patch sem confirmação (default False).")
    parser.add_argument("--rating", type=int, default=None, choices=[1, 2, 3, 4, 5],
                        help="PROJECT feedback: nota 1-5.")
    parser.add_argument("--note", default=None, help="PROJECT feedback: nota textual.")
    parser.add_argument("--tags", default=None,
                        help="PROJECT feedback: tags separadas por vírgula.")
    parser.add_argument("--mission", default=None, dest="mission_id",
                        help="PROJECT feedback: mission_id de origem.")

    parser.add_argument("--auto-build", action="store_true", dest="auto_build")
    parser.add_argument("--no-confirm", action="store_true", dest="no_confirm")
    parser.add_argument("--no-build", action="store_true", dest="no_build")
    parser.add_argument("--no-validate", action="store_true", dest="no_validate")
    parser.add_argument("--no-vab", action="store_true", dest="no_vab")
    parser.add_argument("--max-per-mode", type=int, default=3, dest="max_per_mode")
    parser.add_argument("--max", type=int, default=8, dest="max_opportunities")
    parser.add_argument("--handoff", default=None, dest="handoff_id")
    parser.add_argument("--no-evidence", action="store_true", dest="no_evidence")
    parser.add_argument("--evidence-provider", default=None, dest="evidence_provider",
                        choices=["mock", "tavily", "serper", "http"])
    parser.add_argument("--history", action="store_true")
    parser.add_argument("-n", type=int, default=5, dest="history_limit")
    parser.add_argument("--last", action="store_true")
    parser.add_argument("--rerun", metavar="ID")
    parser.add_argument("--clean", action="store_true", dest="clean",
                        help="Remove artifacts e reseta memórias de teste.")
    parser.add_argument("--all", action="store_true", dest="clean_all",
                        help="Com --clean: inclui TODAS as raízes de artifacts.")
    parser.add_argument("--dry-run", action="store_true", dest="clean_dry_run",
                        help="Com --clean: apenas conta, não remove.")
    return parser


def _parse_args() -> argparse.Namespace:
    parser = _build_parser()
    args = parser.parse_args()
    if not any([args.history, args.last, args.rerun, args.mission]):
        return _interactive_menu()
    return args


def _interactive_menu() -> argparse.Namespace:
    ns = argparse.Namespace(
        mission=None, build_intent=None, project_target=None, files=[], history=False,
        history_limit=5, last=False, rerun=None, project_name=None, project_type=None,
        project_id=None, goal=None, auto_apply=False, rating=None, note=None,
        tags=None, mission_id=None,
        no_build=False, auto_build=False, no_confirm=False,
        no_validate=False, no_vab=False, max_per_mode=3, max_opportunities=8,
        handoff_id=None, no_evidence=False, evidence_provider=None,
    )
    console.print()
    console.print(Panel(
        "[bold cyan]Fundador IA v5.5.2[/bold cyan] — AI Project Operating System\n\n"
        "  [bold][1][/bold]  Nova Missão (deliberação)\n"
        "  [bold][2][/bold]  Reexecutar Última\n"
        "  [bold][3][/bold]  Ver Histórico\n"
        "  [bold][4][/bold]  Sair",
        title="[bold cyan]🏛  Menu Principal[/bold cyan]", border_style="cyan", padding=(1, 3),
    ))
    choice = console.input("\n[bold]Escolha:[/bold] ").strip()
    if choice == "1":
        ns.mission = console.input("\n[bold]📋 Missão:[/bold] ").strip()
        if not ns.mission:
            _exit_error("Missão não pode ser vazia.")
        fi = console.input("[dim] Arquivos (vírgula ou Enter):[/dim] ").strip()
        if fi:
            ns.files = [f.strip() for f in fi.split(",") if f.strip()]
    elif choice == "2":
        ns.last = True
    elif choice == "3":
        ns.history = True
    elif choice == "4":
        console.print("\n[dim]Encerrando.[/dim]\n")
        sys.exit(0)
    else:
        _exit_error(f"Opção inválida: '{choice}'.")
    return ns


def _exit_error(message: str, exception: Exception | None = None) -> NoReturn:
    detail = str(exception) if exception else ""
    body = message + (f"\n\n[dim]{detail}[/dim]" if detail else "")
    console.print()
    console.print(Panel(body, title="[bold red]⚠  Erro[/bold red]",
                        border_style="red", padding=(1, 2)))
    sys.exit(1)


def _print_warning(message: str) -> None:
    console.print(f"  [bold yellow]⚠  {message}[/bold yellow]")


def _print_success(message: str) -> None:
    console.print(f"  [bold green]✅ {message}[/bold green]")


def _print_info(message: str) -> None:
    console.print(f"  [dim]{message}[/dim]")


def _load_for_rerun(use_last: bool, rerun_id: str | None, override_files: list[str]):
    try:
        from backend.core.history import get_decision_by_id, get_last_decision
    except Exception as e:
        _exit_error("Falha ao carregar histórico.", e)
    entry = None
    if use_last:
        try:
            entry = get_last_decision()
        except Exception as e:
            _exit_error("Falha ao ler histórico.", e)
        if not entry:
            _exit_error('Nenhuma deliberação anterior. Use: python main.py "missão"')
    elif rerun_id:
        try:
            entry = get_decision_by_id(rerun_id)
        except Exception as e:
            _exit_error("Falha ao buscar deliberação.", e)
        if not entry:
            _exit_error(f"Deliberação {rerun_id} não encontrada.")
    assert entry is not None
    mission = entry["mission"]
    files = override_files if override_files else (entry.get("context_files") or [])
    console.print()
    console.print(Panel(
        f"[dim]ID original:[/dim] [bold]{entry['id']}[/bold]\n[dim]Data:[/dim] {entry['timestamp']}",
        title="[bold cyan]🔄 Reexecutando[/bold cyan]", border_style="cyan", padding=(0, 2),
    ))
    return mission, files


def _prepare_context(file_paths: list[str]):
    if not file_paths:
        return "", []
    from backend.tools.file_tools import _PROJECT_ROOT, prepare_context_payload
    project_root: Path = Path(_PROJECT_ROOT)
    try:
        payload = prepare_context_payload(file_paths)
    except Exception as e:
        _exit_error("Falha ao preparar contexto.", e)
    console.print()
    console.print(f"[dim]📁 Contexto:[/dim] {len(payload.included_files)} incluído(s), "
                  f"{len(payload.truncated_files)} truncado(s), {len(payload.omitted_files)} omitido(s)")
    for f in payload.included_files:
        try:
            size_kb = (project_root / f).stat().st_size / 1024
            size_str = f"{size_kb:.1f} KB"
        except OSError:
            size_str = "? KB"
        flag = " [bold yellow](truncado)[/bold yellow]" if f in payload.truncated_files else ""
        console.print(f"   [green]📄[/green] {Path(f).name} [dim]({size_str})[/dim]{flag}")
    for f in payload.omitted_files:
        _print_warning(f"{Path(f).name} omitido — limite de contexto.")
    for w in payload.warnings:
        _print_warning(w)
    console.print()
    return payload.block, payload.included_files


def _show_history(limit: int) -> None:
    try:
        from backend.core.history import get_recent_decisions
        decisions = get_recent_decisions(limit)
    except Exception as e:
        _exit_error("Falha ao ler histórico.", e)
    if not decisions:
        console.print()
        console.print(Panel('[dim]Nenhuma deliberação.[/dim]',
                            title="[bold cyan]📋 Histórico[/bold cyan]", border_style="cyan", padding=(1, 2)))
        return
    table = Table(title=f"Últimas {len(decisions)} Deliberações", show_header=True,
                  header_style="bold cyan", border_style="dim", padding=(0, 1))
    table.add_column("Data/Hora", min_width=18, style="dim")
    table.add_column("ID", min_width=10, style="dim")
    table.add_column("Missão", min_width=34)
    table.add_column("Score", justify="center", min_width=7)
    table.add_column("Veredito", justify="center", min_width=12)
    for d in decisions:
        ms = d["mission"][:55] + ("…" if len(d["mission"]) > 55 else "")
        score = d["average_score"]
        ss = "green" if score >= 7.5 else "yellow" if score >= 6.0 else "red"
        vs = "[green]✅ APPROVED[/green]" if d["final_verdict"] == "APPROVED" else "[red]❌ REJECTED[/red]"
        table.add_row(d["timestamp"], (d.get("id") or "")[:8] + "…", ms,
                      f"[{ss}]{score:.2f}[/{ss}]", vs)
    console.print()
    console.print(table)
    console.print("\n[dim]Dica: python main.py --rerun ID_COMPLETO[/dim]\n")


def _render_header(mission: str, included_files: list[str]) -> None:
    ctx = f"\n\n[dim]Contexto:[/dim] {', '.join(Path(f).name for f in included_files)}" if included_files else ""
    console.print()
    console.print(Panel(
        f"[bold white]Conselho Consultivo Artificial[/bold white]\n\n"
        f"[dim]Missão:[/dim]\n[italic]{mission}[/italic]{ctx}",
        title="[bold cyan]🏛  Fundador IA v5.5.2[/bold cyan]", border_style="cyan", padding=(1, 2),
    ))
    console.print()


def _render_config_warnings() -> None:
    from backend.core.config import settings as app_settings
    warnings = app_settings.validate_provider_config()
    if not warnings:
        return
    console.print()
    console.print(Panel("\n".join(f"• {w}" for w in warnings),
                        title="[bold yellow]⚙  Avisos de Configuração[/bold yellow]",
                        border_style="yellow", padding=(1, 2)))


def _observability_cell(r: JurorResponse) -> str:
    if r.provider_used == "fallback-safe":
        return "[red]fallback-safe[/red] (sem LLM)"
    if r.model_used:
        short = r.model_used.split(":")[0].split("/")[-1]
        base = f"{r.provider_used} ({short})"
    else:
        base = r.provider_used
    if r.fallback_triggered and r.original_provider:
        return f"{base} [yellow]⟲ fallback de {r.original_provider}[/yellow]"
    return base


def _render_juror_row(r: JurorResponse) -> None:
    ss = "green" if r.score >= 7.0 else "yellow" if r.score >= 5.0 else "red"
    vi = "✅" if r.verdict.value == "APPROVE" else "🚫"
    console.print(f"  [bold]{r.juror_name}[/bold] — Score: [{ss}]{r.score:.1f}/10[/{ss}] "
                  f"{vi} {r.verdict.value} [dim][{_observability_cell(r)}][/dim]")


def _render_jurors_table(responses: list[JurorResponse]) -> None:
    table = Table(show_header=True, header_style="bold cyan", border_style="dim", padding=(0, 1))
    table.add_column("Jurado", style="bold", min_width=16)
    table.add_column("Score", justify="center", min_width=8)
    table.add_column("Veredicto", justify="center", min_width=12)
    table.add_column("Provedor", min_width=26)
    table.add_column("Raciocínio", min_width=44)
    for r in responses:
        ss = "green" if r.score >= 7.0 else "yellow" if r.score >= 5.0 else "red"
        vs = "[green]✅ APPROVE[/green]" if r.verdict.value == "APPROVE" else "[red]🚫 VETO[/red]"
        rs = r.reasoning[:80] + ("…" if len(r.reasoning) > 80 else "")
        table.add_row(r.juror_name, f"[{ss}]{r.score:.1f}/10[/{ss}]", vs, _observability_cell(r), rs)
    console.print(table)


def _render_clarification_recap(state: DeliberationState) -> None:
    if not state.clarification or not state.founder_response:
        return
    qs = "\n".join(f"  ❓ {q}" for q in state.clarification.questions)
    a = state.founder_response
    a = a if len(a) <= 300 else a[:297] + "..."
    console.print()
    console.print(Panel(
        f"[bold]Perguntas do Turno 0:[/bold]\n{qs}\n\n[bold]Resposta (resumida):[/bold]\n[italic]{a}[/italic]",
        title="[bold yellow]💬 Histórico de Esclarecimento[/bold yellow]", border_style="yellow", padding=(1, 2)))


def _render_final_verdict(final_state: DeliberationState) -> None:
    decision = final_state.final_decision
    if not decision:
        return
    _render_clarification_recap(final_state)
    approved = decision.verdict == "APPROVED"
    reason = f"\n[dim]Motivo: [/dim][italic]{decision.reason}[/italic]" if decision.reason else ""
    console.print()
    console.print(Panel(
        f"{'✅' if approved else '❌'} Veredito Final: "
        f"{'[bold green]APPROVED[/bold green]' if approved else '[bold red]REJECTED[/bold red]'}\n"
        f"[dim]Score Médio: [/dim][bold]{decision.average_score:.2f}/10.0[/bold]{reason}",
        title="[bold]🎯 Decisão do Conselho[/bold]",
        border_style="green" if approved else "red", padding=(1, 2)))


def _render_clarification(state: DeliberationState) -> None:
    c = state.clarification
    if not c:
        return
    qt = "\n".join(f"  [bold]{i}.[/bold] {q}" for i, q in enumerate(c.questions, 1))
    console.print()
    console.print(Panel(
        f"[dim]Motivo:[/dim] {c.reason}\n\n[bold]Perguntas:[/bold]\n{qt}\n\n"
        f"[dim]Digite 'cancel' para encerrar.[/dim]",
        title="[bold yellow]❓ Esclarecimentos Necessários[/bold yellow]", border_style="yellow", padding=(1, 2)))


async def _collect_juror_responses(mission: str, context_block: str, turn_label: str, extra_context: str = ""):
    from backend.agents.council import JURORS, _evaluate_juror
    from backend.core.llm_client import LLMProviderError
    full = context_block
    if extra_context:
        full = f"{context_block}\n\n--- CONTEXTO ADICIONAL ---\n{extra_context}\n---"
    responses = []
    for juror in JURORS:
        with console.status(f"[cyan]{turn_label} — [{juror['name']}]...[/cyan]", spinner="dots"):
            try:
                response = await _evaluate_juror(juror, mission, full)
            except LLMProviderError as e:
                _exit_error(f"Falha ao consultar [{juror['name']}].\n{e}")
            except RuntimeError as e:
                _exit_error(str(e))
            except Exception as e:
                _exit_error(f"Erro inesperado em [{juror['name']}].", exception=e)
        responses.append(response)
        _render_juror_row(response)
    return responses


async def _run_deliberation(mission: str, context_block: str, included_files: list[str]) -> None:
    from backend.core.council import cancel_deliberation, process_founder_reply, process_turn0
    from backend.core.history import save_council_decision
    console.print(Rule("[bold cyan][TURNO 0 — ANÁLISE INICIAL][/bold cyan]", style="cyan"))
    console.print()
    t0 = await _collect_juror_responses(mission, context_block, "[TURNO 0]")
    state = process_turn0(mission, t0)
    if state.status == "FINAL":
        console.print()
        console.print(Rule("[bold green][DELIBERAÇÃO CONCLUÍDA][/bold green]", style="green"))
        _render_jurors_table(t0)
        _render_final_verdict(state)
        _persist_decision(state, included_files, save_council_decision)
        return
    console.print(Rule("[bold yellow][AGUARDANDO ESCLARECIMENTO][/bold yellow]", style="yellow"))
    _render_clarification(state)
    cancelled_kb = False
    try:
        reply = console.input("\n[bold yellow]📝 Sua resposta (ou /cancel):[/bold yellow] ").strip()
    except KeyboardInterrupt:
        cancelled_kb = True
        reply = ""
        console.print()
        _print_info("Ctrl+C detectado — encerrando...")
    if cancelled_kb or not reply or reply.lower() in _CANCEL_TOKENS:
        reason = ("Ctrl+C." if cancelled_kb else (reply if reply else "Encerrado sem responder."))
        cancelled = cancel_deliberation(state, reason=reason)
        console.print()
        console.print(Panel("[dim]Deliberação encerrada.[/dim]",
                            title="[bold dim]🚫 Cancelado[/bold dim]", border_style="dim", padding=(0, 2)))
        _print_info(f"Motivo: {cancelled.founder_response}")
        console.print()
        sys.exit(0)
    console.print()
    console.print(Rule("[bold cyan][TURNO 1 — DELIBERAÇÃO FINAL][/bold cyan]", style="cyan"))
    console.print()
    t1 = await _collect_juror_responses(mission, context_block, "[TURNO 1]", extra_context=reply)
    final_state = process_founder_reply(state, reply, t1)
    console.print()
    console.print(Rule("[bold green][DELIBERAÇÃO CONCLUÍDA][/bold green]", style="green"))
    console.print()
    console.print("[bold dim]Avaliações — Turno 1[/bold dim]")
    _render_jurors_table(t1)
    _render_final_verdict(final_state)
    _persist_decision(final_state, included_files, save_council_decision)


def _persist_decision(final_state: DeliberationState, included_files: list[str], save_fn) -> None:
    from backend.schemas.council import CouncilDecision as CouncilSchemaDecision
    if not final_state.final_decision:
        return
    fd = final_state.final_decision
    compatible = CouncilSchemaDecision(
        mission=final_state.mission, final_verdict=fd.verdict,
        average_score=fd.average_score, reason=fd.reason,
        juror_responses=final_state.turn1_responses or final_state.turn0_responses,
    )
    console.print()
    with console.status("[dim]Salvando decisão...[/dim]", spinner="dots"):
        try:
            did = save_fn(compatible, included_files)
        except Exception as e:
            _print_warning(f"Falha ao salvar: {e}")
            return
    _print_success(f"Decisão registrada — ID: {did}")
    console.print()


def _project_pipeline_store():
    from backend.core.config import settings as s
    from backend.domain.memory_store import DiskProjectMemoryStore
    return DiskProjectMemoryStore(base_dir=Path(s.PROJECT_MEMORY_DIR))


async def main() -> None:
    args = _parse_args()

    from backend.core.config import settings as _app_settings
    for w in _app_settings.environment_warnings():
        _print_warning(w)

    if args.history:
        _show_history(args.history_limit)
        sys.exit(0)

        # ── CLEAN (v5.5.4) ──
    if args.clean:
        from backend.core.cleanup import clean_all as _clean_all
        from rich.table import Table as _Table
        report = _clean_all(config=_app_settings, dry_run=args.clean_dry_run)
        table = _Table(title="🧹 Limpeza de artifacts & memórias" +
                       (" (dry-run)" if args.clean_dry_run else ""))
        table.add_column("Item", min_width=24)
        table.add_column("Qtd", justify="right")
        table.add_row("Arquivos removidos", str(report.files_removed))
        table.add_row("Diretórios removidos", str(report.dirs_removed))
        table.add_row("Memórias resetadas", str(report.memories_reset))
        console.print(table)
        for w in report.warnings:
            _print_warning(w)
        sys.exit(0)

    if getattr(args, "no_confirm", False):
        _app_settings.COUNCIL_ASSUME_DEFAULTS = True   # v5.5.3

    # ── PROJECT (v5.3.0 + feedback v5.5.0) ──
    if args.mission == "project":
        action = args.build_intent or "list"
        if action == "feedback":
            if not args.project_target:
                _exit_error("Uso: project feedback <project_id> [--rating N] "
                            "[--note '...'] [--tags a,b] [--mission id]")
            from backend.cli import cmd_feedback
            sys.exit(cmd_feedback(
                args.project_target, rating=args.rating, note=args.note,
                tags=[t.strip() for t in (args.tags or "").split(",") if t.strip()],
                mission=args.mission_id,
            ))
        from backend.cli import main as _project_cli
        cli_args = [action]
        if args.project_target:
            cli_args.append(args.project_target)
        sys.exit(_project_cli(cli_args))

    # ── BUILD ──
    if args.mission == "build":
        from backend.build.cli import run_build_mode
        from backend.domain.enums import ProjectType
        ptype = ProjectType(args.project_type) if args.project_type else None
        pipe = None
        if args.project_id:
            from backend.build.pipeline import BuildPipeline
            pipe = BuildPipeline(memory_store=_project_pipeline_store(),
                                 project_id=args.project_id, project_type=ptype)
        code = await run_build_mode(args.build_intent or "", project_name=args.project_name,
                                    project_type=ptype, pipeline=pipe)
        sys.exit(code)

    # ── VALIDATE ──
    if args.mission == "validate":
        from backend.validate.cli import run_validate_mode
        from backend.core.evidence.service import EvidenceService
        evidence_svc = None if args.no_evidence else EvidenceService(provider_name=args.evidence_provider)
        pipe = None
        if args.project_id:
            from backend.validate.pipeline import ValidatePipeline
            pipe = ValidatePipeline(evidence_service=evidence_svc,
                                    memory_store=_project_pipeline_store(),
                                    project_id=args.project_id)
        code = await run_validate_mode(args.build_intent or "", context_files=args.files,
                                       pipeline=pipe, evidence_service=evidence_svc)
        sys.exit(code)

    # ── VALIDATE_AND_BUILD ──
    if args.mission == "validate-and-build":
        from backend.validate_and_build.cli import run_validate_and_build_mode
        pipe = None
        if args.project_id:
            from backend.validate_and_build.pipeline import ValidateAndBuildPipeline
            pipe = ValidateAndBuildPipeline(memory_store=_project_pipeline_store(),
                                            project_id=args.project_id)
        code = await run_validate_and_build_mode(
            args.build_intent or "", context_files=args.files, no_build=args.no_build,
            auto_build=args.auto_build, no_confirm=args.no_confirm, pipeline=pipe)
        sys.exit(code)

    # ── SELF-AUDIT ──
    if args.mission == "self-audit":
        from backend.self_audit.cli import run_self_audit_mode
        code = await run_self_audit_mode(no_build=args.no_build, no_validate=args.no_validate,
                                         no_vab=args.no_vab, max_per_mode=args.max_per_mode)
        sys.exit(code)

    # ── DISCOVER ──
    if args.mission == "discover":
        from backend.discover.cli import run_discover_mode
        from backend.core.evidence.service import EvidenceService
        evidence_svc = None if args.no_evidence else EvidenceService(provider_name=args.evidence_provider)
        code = await run_discover_mode(args.build_intent or "",
                                       max_opportunities=args.max_opportunities,
                                       handoff_id=args.handoff_id,
                                       evidence_service=evidence_svc)
        sys.exit(code)

    # ── GOLDEN ──
    if args.mission == "golden-missions":
        from backend.golden.cli import run_golden_mode
        sys.exit(await run_golden_mode())

    # ── SMOKE (v5.5.0) ──
    if args.mission == "smoke":
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            "smoke_release", Path(__file__).resolve().parent / "scripts" / "smoke_release.py")
        if _spec is None or _spec.loader is None:
            _exit_error("Não foi possível carregar scripts/smoke_release.py.")
        _mod = _ilu.module_from_spec(_spec)
        sys.modules["smoke_release"] = _mod
        _spec.loader.exec_module(_mod)
        sys.exit(_mod.main())

    # ── IMPROVE (v5.4.0 + --auto-apply v5.5.2) ──
    if args.mission == "improve":
        from backend.cli import run_improve_mode
        if not args.project_id:
            _exit_error("IMPROVE exige --project <project_id>.")
        code = await run_improve_mode(
            args.project_id, goal=args.goal,
            auto_apply=getattr(args, "auto_apply", False),
            no_confirm=args.no_confirm,
        )
        sys.exit(code)

    # ── COUNCIL (default) ──
    if args.last or args.rerun:
        mission, prev_files = _load_for_rerun(args.last, args.rerun, args.files)
    else:
        mission = args.mission or ""
        prev_files = args.files
    if not mission:
        _exit_error("Missão não pode ser vazia.")
    _render_config_warnings()
    context_block, included_files = _prepare_context(prev_files)
    _render_header(mission, included_files)
    await _run_deliberation(mission, context_block, included_files)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n\n[dim]Interrompido pelo usuário.[/dim]\n")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        from backend.cli import friendly_error
        console.print()
        console.print(Panel(friendly_error(e), title="[bold red]⚠  Erro[/bold red]",
                            border_style="red", padding=(1, 2)))
        sys.exit(1)