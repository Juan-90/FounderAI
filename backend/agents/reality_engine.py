"""
Reality Engine — Agente 2
Analisa a viabilidade real de mercado da missão.
Responde: "Essa missão merece ser executada?"
"""

from pathlib import Path

from backend.core.config import settings
from backend.core.ollama_client import ollama
from backend.core.schemas import (
    ClarityLevel,
    MissionBrief,
    RealityReport,
    Recommendation,
)

# ─────────────────────────────────────────
# Carrega o system prompt
# ─────────────────────────────────────────

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "reality_engine.md"
SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

USER_TEMPLATE: str = """/no_think

Analise a seguinte missão e produza o Reality Report completo.

## Missão Declarada
{declared_mission}

## Problema Raiz
{root_problem}

## Usuário-Alvo
{target_audience}

## Hipóteses Críticas
{hypotheses}
"""


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────

async def run_reality_engine(brief: MissionBrief) -> RealityReport:
    """
    Executa o Reality Engine sobre um MissionBrief.
    Retorna um RealityReport estruturado.
    """
    hypotheses_text: str = "\n".join(
        f"- {h}" for h in brief.critical_hypotheses
    )

    prompt: str = USER_TEMPLATE.format(
        declared_mission=brief.declared_mission,
        root_problem=brief.root_problem,
        target_audience=brief.target_audience,
        hypotheses=hypotheses_text,
    )

    raw_output: str = await ollama.generate(
        model=settings.model_reasoning,
        prompt=prompt,
        system=SYSTEM_PROMPT,
    )

    return _parse_reality_report(
        raw_output=raw_output,
        mission_brief_id=brief.id,
    )


# ─────────────────────────────────────────
# Parser
# ─────────────────────────────────────────

def _parse_reality_report(
    raw_output: str,
    mission_brief_id,
) -> RealityReport:
    """
    Faz o parse do output do modelo para o schema RealityReport.
    """
    sections: dict[str, str] = _extract_sections(raw_output)

    return RealityReport(
        mission_brief_id=mission_brief_id,
        executive_summary=sections.get("Resumo Executivo", ""),
        market_analysis=sections.get("Mercado", ""),
        competition_analysis=sections.get("Concorrência", ""),
        differentiation_analysis=sections.get("Oportunidades de Diferenciação", ""),
        risks=_extract_list(sections.get("Riscos Principais", "")),
        complexity=ClarityLevel.MEDIUM,
        estimated_investment=_extract_investment(sections.get("Estimativas", "")),
        validation_time=_extract_validation_time(sections.get("Estimativas", "")),
        recommendation=_parse_recommendation(sections.get("Recomendação Final", "")),
        justification=sections.get("Justificativa da Recomendação", ""),
        confidence_level=_parse_confidence(
            sections.get("Nível de Confiança Geral", "")
        ),
        raw_output=raw_output,
    )


def _extract_sections(text: str) -> dict[str, str]:
    """Extrai seções delimitadas por '### Título'."""
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
    """Extrai itens de lista de um bloco de texto."""
    items: list[str] = []
    for line in text.splitlines():
        clean: str = line.strip().lstrip("-*•").strip()
        if len(clean) > 2 and clean[0].isdigit() and clean[1] in ".)":
            clean = clean[2:].strip()
        if clean:
            items.append(clean)
    return items


def _extract_investment(text: str) -> str:
    """Extrai o valor de investimento da seção Estimativas."""
    for line in text.splitlines():
        lower = line.lower()
        if "investimento" in lower or "mvp" in lower or "r$" in lower:
            return line.strip().lstrip("-*•").strip()
    return text.split("\n")[0].strip() if text else ""


def _extract_validation_time(text: str) -> str:
    """Extrai o tempo de validação da seção Estimativas."""
    for line in text.splitlines():
        lower = line.lower()
        if "validação" in lower or "tempo" in lower or "semana" in lower or "mês" in lower:
            return line.strip().lstrip("-*•").strip()
    lines = text.split("\n")
    return lines[1].strip() if len(lines) > 1 else ""


def _parse_recommendation(text: str) -> Recommendation:
    """Converte o texto de recomendação para o enum."""
    upper: str = text.upper()
    if "GO" in upper and "PIVOT" not in upper:
        return Recommendation.GO
    elif "PIVOT" in upper:
        return Recommendation.PIVOT
    return Recommendation.KILL


def _parse_confidence(text: str) -> ClarityLevel:
    """Converte o nível de confiança para o enum."""
    lower: str = text.lower()
    if "alta" in lower:
        return ClarityLevel.HIGH
    elif "média" in lower or "media" in lower:
        return ClarityLevel.MEDIUM
    return ClarityLevel.LOW