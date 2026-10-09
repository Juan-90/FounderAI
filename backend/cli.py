"""
Helpers compartilhados de CLI (v5.0) + gerenciamento de projetos (v5.3.0).

v5.0: friendly_error (sem stack trace) + summary_panel (resumo Rich).
v5.3: subcomando `project` (list/show/timeline/artifacts).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from backend.core.config import Settings, settings
from backend.domain.memory_store import DiskProjectMemoryStore

console = Console()


# ─────────────────────────────────────────
# v5.0 — erros acionáveis + resumo
# ─────────────────────────────────────────

def friendly_error(exc: Exception) -> str:
    """Mensagem acionável sem stack trace cru."""
    try:
        from backend.core.llm_client import LLMErrorKind, LLMProviderError
        if isinstance(exc, LLMProviderError):
            if exc.kind == LLMErrorKind.UNAVAILABLE:
                return ("Provedor LLM inacessível. Verifique se Ollama/Docker estão "
                        f"rodando ou se a API key existe. ({exc})")
            if exc.kind == LLMErrorKind.TIMEOUT:
                return ("Tempo esgotado consultando o LLM. Aumente "
                        f"LLM_TIMEOUT_SECONDS / LLM_LOCAL_TIMEOUT_SECONDS no .env. ({exc})")
            if exc.kind == LLMErrorKind.HTTP_ERROR:
                return ("Erro HTTP do provedor (chave inválida, modelo fora do catálogo "
                        f"ou rate-limit). Revise o .env. ({exc})")
            return f"Resposta inválida do LLM. Tente novamente ou troque o modelo. ({exc})"
    except Exception:
        pass
    return f"{type(exc).__name__}: {exc}"


def summary_panel(title: str, ok: bool, lines: list[str]) -> None:
    """Resumo Rich consistente ao final de cada execução."""
    style = "green" if ok else "red"
    console.print(Panel(
        "\n".join(f"• {l}" for l in lines),
        title=f"[bold]{title} — [{'OK' if ok else 'FALHA'}][/bold]",
        border_style=style, padding=(1, 2),
    ))


# ─────────────────────────────────────────
# v5.3 — gerenciamento de projetos
# ─────────────────────────────────────────

def _get_store(config: Optional[Settings] = None) -> DiskProjectMemoryStore:
    cfg = config if config is not None else settings
    return DiskProjectMemoryStore(base_dir=Path(cfg.PROJECT_MEMORY_DIR))


def cmd_list(config: Optional[Settings] = None) -> int:
    store = _get_store(config)
    projects = store.list_projects()
    if not projects:
        console.print("[yellow]Nenhum projeto encontrado.[/yellow]")
        return 0
    table = Table(title="Projetos")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Nome", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Eventos", justify="right")
    table.add_column("Atualizado", justify="right")
    for p in projects:
        table.add_row(p.project_id, p.name, p.status, str(len(p.events)),
                      p.updated_at.strftime("%Y-%m-%d %H:%M"))
    console.print(table)
    return 0


def cmd_show(project_id: str, config: Optional[Settings] = None) -> int:
    store = _get_store(config)
    memory = store.get(project_id)
    if memory is None:
        console.print(f"[red]Projeto {project_id} não encontrado.[/red]")
        return 1
    console.print(f"\n[bold cyan]Projeto: {memory.name}[/bold cyan]")
    console.print(f"ID: {memory.project_id}")
    console.print(f"Status: {memory.status}")
    console.print(f"Goal atual: {memory.current_goal or '(não definido)'}")
    console.print(f"Criado: {memory.created_at.strftime('%Y-%m-%d %H:%M')}")
    console.print(f"Atualizado: {memory.updated_at.strftime('%Y-%m-%d %H:%M')}\n")
    if memory.decisions:
        console.print("[bold]Decisões ativas:[/bold]")
        for d in memory.decisions[-5:]:
            console.print(f"  • {d.title}: {d.rationale}")
    else:
        console.print("[dim]Sem decisões registradas.[/dim]")
    if memory.learnings:
        console.print("\n[bold]Aprendizados recentes:[/bold]")
        for l in memory.learnings[-5:]:
            console.print(f"  • [{l.source}] {l.text}")
    else:
        console.print("[dim]Sem aprendizados registrados.[/dim]")
    console.print(f"\n[bold]Artefatos versionados:[/bold] {len(memory.artifact_versions)}")
    console.print(f"[bold]Eventos registrados:[/bold] {len(memory.events)}")
    return 0


def cmd_timeline(project_id: str, config: Optional[Settings] = None) -> int:
    store = _get_store(config)
    memory = store.get(project_id)
    if memory is None:
        console.print(f"[red]Projeto {project_id} não encontrado.[/red]")
        return 1
    if not memory.events:
        console.print("[yellow]Nenhum evento registrado.[/yellow]")
        return 0
    table = Table(title=f"Linha do tempo: {memory.name}")
    table.add_column("Data/Hora", style="cyan", no_wrap=True)
    table.add_column("Tipo", style="magenta")
    table.add_column("Mensagem")
    table.add_column("Missão", style="dim")
    for e in sorted(memory.events, key=lambda x: x.created_at):
        table.add_row(e.created_at.strftime("%Y-%m-%d %H:%M"), e.type.value,
                      e.message, e.mission_id or "-")
    console.print(table)
    return 0


def cmd_artifacts(project_id: str, config: Optional[Settings] = None) -> int:
    store = _get_store(config)
    memory = store.get(project_id)
    if memory is None:
        console.print(f"[red]Projeto {project_id} não encontrado.[/red]")
        return 1
    if not memory.artifact_versions:
        console.print("[yellow]Nenhum artefato versionado.[/yellow]")
        return 0
    table = Table(title=f"Artefatos: {memory.name}")
    table.add_column("Data", style="cyan", no_wrap=True)
    table.add_column("Tipo", style="magenta")
    table.add_column("Caminho")
    table.add_column("Resumo", style="dim")
    for v in sorted(memory.artifact_versions, key=lambda x: x.created_at, reverse=True):
        table.add_row(v.created_at.strftime("%Y-%m-%d %H:%M"), v.kind.value,
                      v.path, v.summary or "-")
    console.print(table)
    return 0


def cmd_feedback(
    project_id: str,
    rating: Optional[int] = None,
    note: Optional[str] = None,
    tags: Optional[list[str]] = None,
    mission: Optional[str] = None,
    config: Optional[Settings] = None,
) -> int:
    """Registra feedback humano (OBSERVE) na Project Memory."""
    from backend.core.memory.feedback_service import FeedbackService
    from backend.domain.feedback import ProjectFeedbackRequest

    cfg = config if config is not None else settings
    store = _get_store(cfg)
    svc = FeedbackService(config=cfg)
    try:
        result = svc.record_feedback(store, ProjectFeedbackRequest(
            project_id=project_id, rating=rating, note=note,
            tags=tags or [], mission_id=mission,
        ))
    except Exception as exc:
        console.print(f"[red]Erro ao registrar feedback:[/red] {friendly_error(exc)}")
        return 1
    
    if not result.accepted:
        console.print(f"[red]Feedback não registrado:[/red] {result.summary}")
        return 1
    console.print(Panel(
        f"[bold]Resumo:[/bold] {result.summary}\n"
        f"[dim]learning_id:[/dim] {result.learning_id}\n"
        f"[dim]event_id:[/dim] {result.event_id}\n"
        "[green]Feedback integrado à Project Memory.[/green]",
        title="[bold green]👁 Feedback registrado (OBSERVE)[/bold green]",
        border_style="green", padding=(1, 2),
    ))
    return 0

def main(args: list[str]) -> int:
    """Entry point do subcomando `project`."""
    if not args:
        console.print("[red]Uso: python main.py project <list|show|timeline|artifacts> [id][/red]")
        return 1
    cmd = args[0]
    if cmd == "list":
        return cmd_list()
    if cmd == "show":
        if len(args) < 2:
            console.print("[red]Uso: project show <project_id>[/red]")
            return 1
        return cmd_show(args[1])
    if cmd == "timeline":
        if len(args) < 2:
            console.print("[red]Uso: project timeline <project_id>[/red]")
            return 1
        return cmd_timeline(args[1])
    if cmd == "artifacts":
        if len(args) < 2:
            console.print("[red]Uso: project artifacts <project_id>[/red]")
            return 1
        return cmd_artifacts(args[1])
    console.print(f"[red]Subcomando desconhecido: {cmd}[/red]")
    return 1


# ─────────────────────────────────────────
# v5.4 — modo IMPROVE
# ─────────────────────────────────────────

def _render_improve(result: Any) -> None:
    from rich.table import Table as _Table
    d = result.diagnosis
    console.print()
    console.print(Panel(
        f"[bold]Resumo:[/bold] {d.summary}\n[bold]Risco:[/bold] {d.risk_level}",
        title="[bold cyan]🔧 Diagnóstico IMPROVE[/bold cyan]", border_style="cyan", padding=(1, 2),
    ))
    if d.top_issues:
        console.print("[bold]Issues:[/bold]")
        for i in d.top_issues[:6]:
            console.print(f"  • {i}")
    t = _Table(title="Plano de Melhoria", show_header=True, header_style="bold magenta",
               border_style="dim", padding=(0, 1))
    t.add_column("#", justify="right", style="dim")
    t.add_column("Ação", min_width=34)
    t.add_column("Risco", justify="center")
    t.add_column("Impacto esperado", min_width=30)
    for i, it in enumerate(result.plan.items, 1):
        t.add_row(str(i), it.title, it.risk_level, it.expected_impact)
    console.print(t)
    status = ("[yellow]WAITING_HUMAN[/yellow]" if result.waiting_human
              else "[green]SUCCESS[/green]" if result.success
              else "[red]ESCALATED[/red]" if result.escalated
              else "[red]FAILED[/red]")
    console.print(f"\n[bold]Status:[/bold] {status} — {result.summary}")
    if result.changed_files:
        console.print(f"[dim]Arquivos alterados:[/dim] {', '.join(result.changed_files)}")


async def run_improve_mode(
    project_id: str,
    goal: Optional[str] = None,
    auto_apply: bool = False,
    no_confirm: bool = False,
    config: Optional[Settings] = None,
) -> int:
    from backend.core.improve.patcher import ImprovePatcher, ImproveQualityRunner
    from backend.core.improve.pipeline import ImprovePipeline
    from backend.domain.improve import ImproveRequest

    cfg = config if config is not None else settings
    if not cfg.IMPROVE_MODE_ENABLED:
        console.print("[red]IMPROVE desabilitado (IMPROVE_MODE_ENABLED=false).[/red]")
        return 1

    store = _get_store(cfg)
    pipe = ImprovePipeline(
        store=store, config=cfg,
        patcher=ImprovePatcher(),
        quality_runner=ImproveQualityRunner(),
    )
    request = ImproveRequest(
        project_id=project_id, goal=goal,
        require_human_confirmation=not no_confirm,
        auto_apply=auto_apply,
        max_files_touched=cfg.IMPROVE_MAX_FILES_TOUCHED,
    )
    try:
        result = await pipe.execute(request)
    except Exception as exc:
        console.print(f"[red]Erro no IMPROVE:[/red] {friendly_error(exc)}")
        return 1
    _render_improve(result)

    if result.waiting_human:
        answer = console.input("\n[bold yellow]Aplicar patch? [y/N]:[/bold yellow] ").strip().lower()
        if answer in ("y", "yes"):
            approved = request.model_copy(update={
                "require_human_confirmation": False, "auto_apply": True})
            try:
                result = await pipe.execute(approved)
            except Exception as exc:
                console.print(f"[red]Erro ao aplicar:[/red] {friendly_error(exc)}")
                return 1
            _render_improve(result)
        else:
            console.print("[dim]Aplicação cancelada; plano mantido como rascunho.[/dim]")
            return 0
    return 0 if result.success else 1
    _render_improve(result)

    if result.waiting_human:
        answer = console.input("\n[bold yellow]Aplicar patch? [y/N]:[/bold yellow] ").strip().lower()
        if answer in ("y", "yes"):
            approved = request.model_copy(update={
                "require_human_confirmation": False, "auto_apply": True})
            result = await pipe.execute(approved)
            _render_improve(result)
        else:
            console.print("[dim]Aplicação cancelada; plano mantido como rascunho.[/dim]")
            return 0
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))