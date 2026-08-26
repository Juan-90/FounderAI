"""
History — Persistência de deliberações do Conselho Consultivo.
Sprint 3: Salva em DECISIONS.md (legível) e decisions_history.json (estruturado).

Localização: backend/core/history.py
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.schemas.council import CouncilDecision

# ─────────────────────────────────────────
# Caminhos
# ─────────────────────────────────────────

_DOCS_DIR: Path = Path(__file__).parent.parent.parent / "docs"
_MD_PATH: Path = _DOCS_DIR / "DECISIONS.md"
_JSON_PATH: Path = _DOCS_DIR / "decisions_history.json"


def _ensure_docs_dir() -> None:
    _DOCS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────
# Salvar
# ─────────────────────────────────────────

def save_council_decision(
    decision: CouncilDecision,
    context_files: list[str] | None = None,
) -> str:
    """
    Persiste a decisão em dois formatos:
      - docs/DECISIONS.md  (Markdown amigável, append)
      - docs/decisions_history.json  (JSON estruturado, lista)

    Args:
        decision: Objeto CouncilDecision a persistir.
        context_files: Arquivos de contexto usados na deliberação.

    Returns:
        ID único da deliberação (UUID4).
    """
    _ensure_docs_dir()

    deliberation_id: str = str(uuid.uuid4())
    timestamp: str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    _append_markdown(decision, deliberation_id, timestamp, context_files or [])
    _append_json(decision, deliberation_id, timestamp, context_files or [])

    return deliberation_id


def _append_markdown(
    decision: CouncilDecision,
    deliberation_id: str,
    timestamp: str,
    context_files: list[str],
) -> None:
    """Faz append formatado no DECISIONS.md."""
    verdict_emoji = "✅" if decision.final_verdict == "APPROVED" else "❌"

    lines: list[str] = [
        "",
        "---",
        "",
        f"## Conselho Consultivo — {timestamp}",
        f"**ID:** `{deliberation_id}`",
        "",
        f"**Missão Avaliada:** {decision.mission}",
        "",
    ]

    if context_files:
        files_str = ", ".join(f"`{f}`" for f in context_files)
        lines += [f"**Arquivos de Contexto:** {files_str}", ""]

    lines += [
        f"**Veredicto Final:** {verdict_emoji} {decision.final_verdict}",
        "",
        f"**Score Médio:** {decision.average_score:.2f}/10.0",
        "",
        "**Avaliações por Jurado:**",
        "",
    ]

    for r in decision.juror_responses:
        verdict_icon = "✅" if r.verdict.value == "APPROVE" else "🚫"
        lines.append(
            f"- **{r.juror_name}** — Score: {r.score:.1f}/10 | "
            f"{verdict_icon} {r.verdict.value}"
        )
        lines.append(f"  > {r.reasoning}")
        lines.append("")

    with open(_MD_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _append_json(
    decision: CouncilDecision,
    deliberation_id: str,
    timestamp: str,
    context_files: list[str],
) -> None:
    """Faz append estruturado no decisions_history.json."""
    # Lê histórico existente
    history: list[dict] = _load_json()

    entry: dict = {
        "id": deliberation_id,
        "timestamp": timestamp,
        "mission": decision.mission,
        "context_files": context_files,
        "final_verdict": decision.final_verdict,
        "average_score": decision.average_score,
        "juror_responses": [
            {
                "juror_name": r.juror_name,
                "score": r.score,
                "verdict": r.verdict.value,
                "reasoning": r.reasoning,
            }
            for r in decision.juror_responses
        ],
    }

    history.append(entry)

    with open(_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────
# Ler histórico
# ─────────────────────────────────────────

def _load_json() -> list[dict]:
    """Carrega o histórico JSON. Retorna lista vazia se inexistente/corrompido."""
    if not _JSON_PATH.exists():
        return []
    try:
        with open(_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def get_recent_decisions(limit: int = 5) -> list[dict]:
    """
    Retorna as últimas N deliberações do histórico JSON.

    Args:
        limit: Número máximo de deliberações a retornar.

    Returns:
        Lista de dicts com os campos da deliberação, ordem mais recente primeiro.
    """
    history = _load_json()
    return history[-limit:][::-1]  # últimas N, ordem decrescente


def get_last_decision() -> dict | None:
    """
    Retorna a deliberação mais recente do histórico JSON.
    Retorna None se o histórico estiver vazio ou inexistente.
    """
    history = _load_json()
    return history[-1] if history else None


def get_decision_by_id(deliberation_id: str) -> dict | None:
    """
    Busca uma deliberação pelo ID único.
    Retorna None se não encontrada.
    """
    for entry in _load_json():
        if entry.get("id") == deliberation_id:
            return entry
    return None