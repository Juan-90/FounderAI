"""
Mission Intelligence — Agente 1
Transforma uma ideia declarada em compreensão clara do problema real.
"""

from pathlib import Path

from backend.core.config import settings
from backend.core.ollama_client import ollama
from backend.core.schemas import ClarityLevel, MissionBrief, MissionInput

# ─────────────────────────────────────────
# Carrega o system prompt do arquivo .md
# ─────────────────────────────────────────

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "mission_intelligence.md"
SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

USER_TEMPLATE: str = """Analise a seguinte ideia e produza o Mission Brief completo.

IDEIA DO FUNDADOR:
{raw_idea}"""


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────

async def run_mission_intelligence(input: MissionInput) -> MissionBrief:
    """
    Executa o Mission Intelligence sobre uma ideia do usuário.
    Retorna um MissionBrief estruturado.
    """
    prompt: str = USER_TEMPLATE.format(raw_idea=input.raw_idea)

    raw_output: str = await ollama.generate(
        model=settings.model_primary,
        prompt=prompt,
        system=SYSTEM_PROMPT,
    )

    return _parse_mission_brief(
        raw_output=raw_output,
        declared_mission=input.raw_idea,
    )


# ─────────────────────────────────────────
# Parser
# ─────────────────────────────────────────

def _parse_mission_brief(raw_output: str, declared_mission: str) -> MissionBrief:
    """
    Faz o parse do output do modelo para o schema MissionBrief.
    Usa os marcadores ### como delimitadores de seção.
    """
    sections: dict[str, str] = _extract_sections(raw_output)

    return MissionBrief(
        declared_mission=sections.get("Missão Declarada", declared_mission),
        identified_problem=sections.get("Problema Raiz Identificado", ""),
        root_problem=sections.get("Problema Raiz Identificado", ""),
        target_audience=sections.get("Usuário-Alvo Principal", ""),
        critical_hypotheses=_extract_list(sections.get("Hipóteses Principais", "")),
        recommended_reformulations=_extract_list(
            sections.get("Reformulações Sugeridas da Missão", "")
        ),
        clarity_level=_parse_confidence(
            sections.get("Nível de Confiança na Análise", "")
        ),
        pending_questions=_extract_list(
            sections.get("Perguntas Estratégicas para o Fundador", "")
        ),
        raw_output=raw_output,
    )


def _extract_sections(text: str) -> dict[str, str]:
    """
    Extrai seções do output usando '### Título' como delimitador.
    Retorna um dict { título: conteúdo }.
    """
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

    # Salva a última seção
    if current_title is not None:
        sections[current_title] = "\n".join(current_lines).strip()

    return sections


def _extract_list(text: str) -> list[str]:
    """
    Extrai itens de lista de um bloco de texto.
    Aceita marcadores: '-', '*', '1.', '2.', etc.
    """
    items: list[str] = []
    for line in text.splitlines():
        clean: str = line.strip().lstrip("-*•").strip()
        # Remove numeração tipo "1. ", "2. "
        if len(clean) > 2 and clean[0].isdigit() and clean[1] in ".)":
            clean = clean[2:].strip()
        if clean:
            items.append(clean)
    return items


def _parse_confidence(text: str) -> ClarityLevel:
    """
    Converte o nível de confiança do modelo para o enum ClarityLevel.
    """
    lower: str = text.lower()
    if "alta" in lower or "high" in lower:
        return ClarityLevel.HIGH
    elif "média" in lower or "media" in lower or "medium" in lower:
        return ClarityLevel.MEDIUM
    return ClarityLevel.LOW
