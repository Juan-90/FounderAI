"""
Mission Scorecard — Agente 4
Transforma análises complexas em pontuação visual 0-100.
"""

from pathlib import Path

from backend.core.config import settings
from backend.core.ollama_client import ollama
from backend.core.schemas import (
    MissionBrief,
    MissionScore,
    RealityReport,
    RiskReport,
)

# ─────────────────────────────────────────
# Carrega o system prompt
# ─────────────────────────────────────────

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "mission_scorecard.md"
SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

USER_TEMPLATE: str = """/no_think

Com base nos documentos abaixo, gere o Mission Scorecard completo.

## Mission Brief
Missão: {declared_mission}
Problema Raiz: {root_problem}
P�blico-Alvo: {target_audience}

## Reality Report (Resumo)
{executive_summary}
Recomendação: {recommendation}

## Risk Report (Resumo)
Probabilidade de Falha: {failure_probability}
Premissas Frágeis:
{fragile_assumptions}
"""


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────

async def run_mission_scorecard(
    brief: MissionBrief,
    report: RealityReport,
    risk: RiskReport,
) -> MissionScore:
    """
    Gera o scorecard consolidado da missão.
    """
    assumptions_text: str = "\n".join(
        f"- {a}" for a in risk.fragile_assumptions[:5]
    )

    prompt: str = USER_TEMPLATE.format(
        declared_mission=brief.declared_mission,
        root_problem=brief.root_problem,
        target_audience=brief.target_audience,
        executive_summary=report.executive_summary,
        recommendation=report.recommendation.value,
        failure_probability=risk.failure_probability.value,
        fragile_assumptions=assumptions_text,
    )

    raw_output: str = await ollama.generate(
        model=settings.model_primary,
        prompt=prompt,
        system=SYSTEM_PROMPT,
    )

    return _parse_mission_score(
        raw_output=raw_output,
        mission_brief_id=brief.id,
    )


# ─────────────────────────────────────────
# Parser
# ─────────────────────────────────────────

def _parse_mission_score(raw_output: str, mission_brief_id) -> MissionScore:
    sections: dict[str, str] = _extract_sections(raw_output)

    return MissionScore(
        mission_brief_id=mission_brief_id,
        market=_extract_score(sections.get("Mercado", "")),
        competition=_extract_score(sections.get("Concorrência", "")),
        differentiation=_extract_score(sections.get("Diferenciação", "")),
        mvp_ease=_extract_score(sections.get("Facilidade de MVP", "")),
        technical_viability=_extract_score(sections.get("Viabilidade Técnica", "")),
        revenue_potential=_extract_score(sections.get("Potencial de Receita", "")),
        validation_speed=_extract_score(sections.get("Velocidade de Validação", "")),
        overall_risk=_extract_score(sections.get("Risco Geral", "")),
        raw_output=raw_output,
    )


def _extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_title: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("### "):
            if current_title is not None:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = line[4:].strip()
            current_lines = []
        else:
            if current_title is not None:
                current_lines.append(line)

    if current_title is not None:
        sections[current_title] = "\n".join(current_lines).strip()

    return sections


def _extract_score(text: str) -> int:
    """Extrai a nota numérica de uma seção. Ex: 'Nota: 7/10' → 7"""
    import re
    for line in text.splitlines():
        match = re.search(r"(\d+)\s*/\s*10", line)
        if match:
            val = int(match.group(1))
            return max(0, min(10, val))
    # Fallback: procura qualquer número isolado
    for line in text.splitlines():
        match = re.search(r"\b(\d)\b", line)
        if match:
            return max(0, min(10, int(match.group(1))))
    return 5  # neutro se não encontrar