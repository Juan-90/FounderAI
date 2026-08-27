"""
History — Persistência de deliberações do Conselho Consultivo.
Sprint 4: Append seguro que preserva cabeçalho e ADR-002 no DECISIONS.md.

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

# Âncora que marca onde as deliberações dinâmicas devem ser inseridas.
# Tudo acima (incluindo ADR-002) é conteúdo estático e jamais é tocado.
_ANCHOR: str = "<!-- ANCHOR_DELIBERATIONS -->"


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
      - docs/DECISIONS.md  (Markdown, append após âncora)
      - docs/decisions_history.json  (JSON estruturado)

    O cabeçalho e o ADR-002 nunca são modificados.

    Returns:
        ID único da deliberação (UUID4).
    """
    _ensure_docs_dir()

    deliberation_id: str = str(uuid.uuid4())
    timestamp: str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    _append_markdown(decision, deliberation_id, timestamp, context_files or [])
    _append_json(decision, deliberation_id, timestamp, context_files or [])

    return deliberation_id


def _build_md_block(
    decision: CouncilDecision,
    deliberation_id: str,
    timestamp: str,
    context_files: list[str],
) -> str:
    """Monta o bloco Markdown de uma deliberação."""
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

    return "\n".join(lines) + "\n"


def _append_markdown(
    decision: CouncilDecision,
    deliberation_id: str,
    timestamp: str,
    context_files: list[str],
) -> None:
    """
    Insere a deliberação no DECISIONS.md APÓS a âncora.
    Se a âncora não existir, faz append simples no final do arquivo.
    O conteúdo acima da âncora (incluindo ADR-002) nunca é modificado.
    """
    block = _build_md_block(decision, deliberation_id, timestamp, context_files)

    if not _MD_PATH.exists():
        # Cria arquivo mínimo com âncora
        _MD_PATH.write_text(
            "# DECISIONS.md\n\n"
            "> Registro de decisões arquiteturais e estratégicas do projeto.\n\n"
            f"{_ANCHOR}\n",
            encoding="utf-8",
        )

    current = _MD_PATH.read_text(encoding="utf-8")

    if _ANCHOR in current:
        # Insere logo após a âncora, preservando tudo que veio antes
        updated = current.replace(_ANCHOR, _ANCHOR + "\n" + block, 1)
        _MD_PATH.write_text(updated, encoding="utf-8")
    else:
        # Âncora não encontrada — append seguro no final
        with open(_MD_PATH, "a", encoding="utf-8") as f:
            f.write(block)


def _append_json(
    decision: CouncilDecision,
    deliberation_id: str,
    timestamp: str,
    context_files: list[str],
) -> None:
    """Adiciona entrada estruturada no decisions_history.json."""
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
    """Retorna as últimas N deliberações, ordem mais recente primeiro."""
    history = _load_json()
    return history[-limit:][::-1]


def get_last_decision() -> dict | None:
    """Retorna a deliberação mais recente ou None."""
    history = _load_json()
    return history[-1] if history else None


def get_decision_by_id(deliberation_id: str) -> dict | None:
    """Busca uma deliberação pelo ID único."""
    for entry in _load_json():
        if entry.get("id") == deliberation_id:
            return entry
    return None