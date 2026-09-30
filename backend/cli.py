"""
Helpers compartilhados de CLI (v5.0.0 GA): erros acionáveis + resumo Rich.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

console = Console()


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