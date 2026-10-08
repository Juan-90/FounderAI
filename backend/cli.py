"""
Helpers compartilhados de CLI (v5.0) + gerenciamento de projetos (v5.3.0).

v5.0: friendly_error (sem stack trace) + summary_panel (resumo Rich).
v5.3: subcomando `project` (list/show/timeline/artifacts).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))