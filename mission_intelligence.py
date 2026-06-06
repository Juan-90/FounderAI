"""
Mission Intelligence — Agente 1
Descobre o problema real por trás da missão declarada.
"""

from backend.core.config import settings
from backend.core.ollama_client import ollama
from backend.core.schemas import MissionBrief, MissionInput

SYSTEM_PROMPT = """Você é o Mission Intelligence, o primeiro agente do Fundador IA.

Seu único objetivo é descobrir o PROBLEMA REAL por trás da ideia declarada pelo usuário.

Princípios que você NUNCA viola:
- Buscar a verdade, não agradar o usuário.
- Nunca assumir que a solução proposta é a melhor.
- Sempre investigar o problema raiz.
- Considerar a realidade brasileira quando aplicável.
- Informar incertezas quando existirem.

Você responde APENAS no formato especificado. Sem introduções, sem comentários fora do formato.
"""

OUTPUT_TEMPLATE = """Analise a seguinte ideia e produza um Mission Brief estruturado.

IDEIA DO USUÁRIO:
{raw_idea}

Responda EXATAMENTE neste formato:

# Mission Brief

## Missão Declarada
[Repita a missão como o usuário declarou]

## Problema Identificado
[Qual problema a solução tenta resolver?]

## Problema Raiz Possível
[Qual é o problema mais profundo por trás disso? Questione pressupostos.]

## Público-Alvo
[Quem realmente tem esse problema? Seja específico.]

## Hipóteses Críticas
[Liste 3-5 hipóteses que, se falsas, tornam a missão inviável]
- Hipótese 1: ...
- Hipótese 2: ...
- Hipótese 3: ...

## Reformulações Recomendadas
[Sugira 1-3 formas mais precisas de declarar a missão]
- Opção 1: ...

## Nível de Clareza da Missão
[Baixo / Médio / Alto — com justificativa]

## Perguntas Pendentes
[Liste 3-5 perguntas que precisam ser respondidas antes de avançar]
- Pergunta 1: ...
"""


async def run_mission_intelligence(input: MissionInput) -> MissionBrief:
    """
    Executa o Mission Intelligence sobre uma ideia do usuário.
    Retorna um MissionBrief estruturado.
    """
    prompt = OUTPUT_TEMPLATE.format(raw_idea=input.raw_idea)

    raw_output = await ollama.generate(
        model=settings.model_primary,
        prompt=prompt,
        system=SYSTEM_PROMPT,
    )

    brief = _parse_mission_brief(
        raw_output=raw_output,
        declared_mission=input.raw_idea,
    )

    return brief


def _parse_mission_brief(raw_output: str, declared_mission: str) -> MissionBrief:
    """
    Faz o parse do output do modelo para o schema MissionBrief.
    TODO: Implementar parser robusto com regex ou modelo estruturado.
    """
    from backend.core.schemas import ClarityLevel

    # Parser simples — será melhorado no Sprint 1
    lines = raw_output.split("\n")

    def extract_section(title: str) -> str:
        collecting = False
        content = []
        for line in lines:
            if f"## {title}" in line:
                collecting = True
                continue
            if collecting and line.startswith("## "):
                break
            if collecting and line.strip():
                content.append(line.strip())
        return "\n".join(content)

    def extract_list(title: str) -> list[str]:
        section = extract_section(title)
        items = []
        for line in section.split("\n"):
            clean = line.lstrip("- •").strip()
            if clean:
                items.append(clean)
        return items

    # Detecta nível de clareza
    clarity_text = extract_section("Nível de Clareza da Missão").lower()
    if "alto" in clarity_text:
        clarity = ClarityLevel.HIGH
    elif "médio" in clarity_text or "medio" in clarity_text:
        clarity = ClarityLevel.MEDIUM
    else:
        clarity = ClarityLevel.LOW

    return MissionBrief(
        declared_mission=declared_mission,
        identified_problem=extract_section("Problema Identificado"),
        root_problem=extract_section("Problema Raiz Possível"),
        target_audience=extract_section("Público-Alvo"),
        critical_hypotheses=extract_list("Hipóteses Críticas"),
        recommended_reformulations=extract_list("Reformulações Recomendadas"),
        clarity_level=clarity,
        pending_questions=extract_list("Perguntas Pendentes"),
        raw_output=raw_output,
    )
