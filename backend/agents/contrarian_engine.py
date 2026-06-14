"""
Contrarian Engine — Agente 3
Advogado do diabo. Encontra falhas, riscos e premissas frágeis.
"""

from pathlib import Path

from backend.core.config import settings
from backend.core.ollama_client import ollama
from backend.core.schemas import (
    FailureProbability,
    RealityReport,
    RiskReport,
)

# ─────────────────────────────────────────
# Carrega o system prompt
# ─────────────────────────────────────────

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "contrarian_engine.md"
SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

USER_TEMPLATE: str = """/no_think

Analise o Reality Report abaixo e produza o Risk Report completo.

## Missão
{declared_mission}

## Resumo Executivo do Reality Report
{executive_summary}

## Mercado
{market_analysis}

## Concorrência
{competition_analysis}

## Riscos já mapeados
{risks}

## Recomendação do Reality Engine
{recommendation}
"""


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────

async def run_contrarian_engine(report: RealityReport) -> RiskReport:
    """
    Executa o Contrarian Engine sobre um RealityReport.
    Retorna um RiskReport estruturado.
    """
    risks_text: str = "\n".join(f"- {r}" for r in report.risks)

    prompt: str = USER_TEMPLATE.format(
        declared_mission=report.executive_summary[:200],
        executive_summary=report.executive_summary,
        market_analysis=report.market_analysis,
        competition_analysis=report.competition_analysis,
        risks=risks_text,
        recommendation=report.recommendation.value,
    )

    raw_output: str = await ollama.generate(
        model=settings.model_primary,
        prompt=prompt,
        system=SYSTEM_PROMPT,
    )

    return _parse_risk_report(
        raw_output=raw_output,
        reality_report_id=report.id,
    )


# ─────────────────────────────────────────
# Parser
# ─────────────────────────────────────────

def _parse_risk_report(raw_output: str, reality_report_id) -> RiskReport:
    sections: dict[str, str] = _extract_sections(raw_output)

    return RiskReport(
        reality_report_id=reality_report_id,
        main_risks=_extract_list(sections.get("Principais Riscos Não Mapeados", "")),
        fragile_assumptions=_extract_list(sections.get("Premissas Frágeis", "")),
        possible_failures=_extract_list(sections.get("Possíveis Falhas de Execução", "")),
        negative_scenarios=_extract_list(sections.get("Cenários Negativos Realistas", "")),
        hard_questions=_extract_list(sections.get("Perguntas Difíceis para o Fundador", "")),
        failure_probability=_parse_probability(sections.get("Probabilidade de Falha", "")),
        recommendations=_extract_list(sections.get("O Que Mudaria Esta Análise", "")),
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


def _extract_list(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        clean: str = line.strip().lstrip("-*•0123456789.)").strip()
        if clean:
            items.append(clean)
    return items


def _parse_probability(text: str) -> FailureProbability:
    lower: str = text.lower()
    if "alta" in lower:
        return FailureProbability.HIGH
    elif "média" in lower or "media" in lower:
        return FailureProbability.MEDIUM
    return FailureProbability.LOW