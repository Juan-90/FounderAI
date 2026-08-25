"""
Council — Conselho Consultivo Artificial.
Orquestra 3 jurados fixos que avaliam uma missão sequencialmente.

Regra de Negócio (APPROVED):
  - Média dos scores >= 8.0
  - SecurityCoder NÃO emitiu VETO
  - SecurityCoder score >= 5.0
"""

import asyncio
from typing import List

from backend.agents.llm_client import call_ollama_json
from backend.core.config import settings
from backend.schemas.council import CouncilDecision, JurorResponse, JurorVerdict

# ─────────────────────────────────────────
# Definição dos Jurados
# ─────────────────────────────────────────

JURORS: List[dict] = [
    {
        "name": "Architect",
        "system_prompt": (
            "Você é o Architect, um jurado do Conselho Consultivo do Fundador IA. "
            "Sua especialidade é avaliar a viabilidade técnica e arquitetural de missões. "
            "Você analisa se a solução proposta é tecnicamente exequível, escalável e coerente. "
            "Seja direto, técnico e imparcial. Não seja otimista por padrão."
        ),
    },
    {
        "name": "SecurityCoder",
        "system_prompt": (
            "Você é o SecurityCoder, um jurado do Conselho Consultivo do Fundador IA. "
            "Sua especialidade é segurança, privacidade de dados, compliance e riscos técnicos críticos. "
            "Você tem poder de VETO absoluto: se identificar risco de segurança grave ou problema "
            "regulatório crítico (ex: LGPD, PCI-DSS), emita VETO independente dos outros jurados. "
            "Seja rigoroso. Um score abaixo de 5.0 indica missão tecnicamente inviável do ponto de vista de segurança."
        ),
    },
    {
        "name": "Generalist",
        "system_prompt": (
            "Você é o Generalist, um jurado do Conselho Consultivo do Fundador IA. "
            "Sua especialidade é avaliar o potencial de mercado, modelo de negócio e viabilidade geral. "
            "Você considera o contexto brasileiro: comportamento do consumidor, poder de compra, "
            "burocracia e maturidade do mercado. Seja pragmático e realista."
        ),
    },
]


# ─────────────────────────────────────────
# Orquestrador
# ─────────────────────────────────────────

async def _evaluate_juror(juror: dict, mission: str) -> JurorResponse:
    """Executa a avaliação de um único jurado."""
    user_prompt: str = (
        f"Avalie a seguinte missão como {juror['name']}:\n\n"
        f"MISSÃO: {mission}\n\n"
        f"Responda com seu score (1.0-10.0), veredicto (APPROVE ou VETO) "
        f"e justificativa (máximo 500 caracteres).\n"
        f"Seu juror_name deve ser exatamente: {juror['name']}"
    )

    raw: dict = await call_ollama_json(
        system_prompt=juror["system_prompt"],
        user_prompt=user_prompt,
        model=settings.council_model,
    )

    # Garante que o nome do jurado está correto mesmo se o modelo alterar
    raw["juror_name"] = juror["name"]

    return JurorResponse(**raw)


async def run_council(mission: str) -> CouncilDecision:
    """
    Executa o Conselho Consultivo de forma SEQUENCIAL.
    Preserva RAM ao evitar chamadas paralelas.

    Regra de Negócio:
      APPROVED se: média >= 8.0 AND SecurityCoder não deu VETO AND SecurityCoder score >= 5.0
      Caso contrário: REJECTED
    """
    responses: List[JurorResponse] = []

    # Execução sequencial — um jurado por vez
    for juror in JURORS:
        print(f"  🧑‍⚖️  Jurado [{juror['name']}] avaliando...")
        response = await _evaluate_juror(juror, mission)
        responses.append(response)
        print(f"     Score: {response.score:.1f} | Veredicto: {response.verdict.value}")

    # ── Regra de Negócio ──
    average_score: float = sum(r.score for r in responses) / len(responses)

    security_response: JurorResponse | None = next(
        (r for r in responses if r.juror_name == "SecurityCoder"), None
    )

    security_vetoed: bool = (
        security_response is not None
        and security_response.verdict == JurorVerdict.VETO
    )
    security_score_ok: bool = (
        security_response is not None
        and security_response.score >= 5.0
    )

    if average_score >= 8.0 and not security_vetoed and security_score_ok:
        final_verdict = "APPROVED"
    else:
        final_verdict = "REJECTED"

    return CouncilDecision(
        mission=mission,
        final_verdict=final_verdict,
        average_score=round(average_score, 2),
        juror_responses=responses,
    )