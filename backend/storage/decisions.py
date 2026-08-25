"""
Storage — Persiste decisões do Conselho no DECISIONS.md.
Faz append formatado na raiz do projeto.
"""

from datetime import datetime
from pathlib import Path

from backend.schemas.council import CouncilDecision

# Caminho para o DECISIONS.md na raiz do projeto
_DECISIONS_PATH = Path(__file__).parent.parent.parent / "docs" / "DECISIONS.md"


def save_council_decision(decision: CouncilDecision) -> None:
    """
    Faz append de uma decisão do Conselho no DECISIONS.md.
    Cria o arquivo se não existir.
    """
    timestamp: str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

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
        lines.append(f"  > {r.reasoning}")
        lines.append("")

    content: str = "\n".join(lines) + "\n"

    with open(_DECISIONS_PATH, "a", encoding="utf-8") as f:
        f.write(content)

    print(f"💾 Decisão salva em {_DECISIONS_PATH}")