"""
Storage — Persiste decisões do Conselho no DECISIONS.md.
Faz append formatado na raiz do projeto.
"""

from datetime import datetime, timezone
from pathlib import Path

from backend.schemas.council import CouncilDecision

# Caminho para o DECISIONS.md no diretório docs/
_DECISIONS_PATH = Path(__file__).parent.parent.parent / "docs" / "DECISIONS.md"


def save_council_decision(decision: CouncilDecision) -> None:
    """
    Faz append de uma decisão do Conselho no DECISIONS.md.
    Cria a pasta e o arquivo se não existirem.
    """
    # Garante que a pasta docs/ existe antes de salvar
    _DECISIONS_PATH.parent.mkdir(parents=True, exist_ok=True)

    timestamp: str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    verdict_emoji: str = "✅" if decision.final_verdict == "APPROVED" else "❌"

    lines: list[str] = [
        "",
        "---",
        "",
        f"## Conselho Consultivo — {timestamp}",
        "",
        f"**Missão Avaliada:** {decision.mission}",
        "",
        f"**Veredicto Final:** {verdict_emoji} {decision.final_verdict}",
        "",
        f"**Score Médio:** {decision.average_score:.2f}/10.0",
        "",
        "**Avaliações por Jurado:**",
        "",
    ]

    for r in decision.juror_responses:
        verdict_icon = "✅" if r.verdict.value == "APPROVE" else "🚫"
        lines.append(f"- **{r.juror_name}** — Score: {r.score:.1f}/10 | {verdict_icon} {r.verdict.value}")
        lines.append(f"  > {r.reasoning.strip()}")
        lines.append("")

    content: str = "\n".join(lines) + "\n"

    with open(_DECISIONS_PATH, "a", encoding="utf-8") as f:
        f.write(content)

    print(f"💾 Decisão salva em {_DECISIONS_PATH}")