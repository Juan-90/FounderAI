"""
Council — Conselho Consultivo Artificial.
Orquestra 3 jurados fixos que avaliam uma missão sequencialmente.

Sprint 2: Suporte a arquivos de contexto injetados nos prompts dos jurados.

Regra de Negócio (APPROVED):
  - Média dos scores >= 8.0
  - SecurityCoder NÃO emitiu VETO
  - SecurityCoder score >= 5.0
"""

from __future__ import annotations

from typing import List

from backend.core.config import settings
from backend.core.llm_client import (
    OllamaInvalidResponseError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    call_ollama_json,
)
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
            "Seja rigoroso. Um score abaixo de 5.0 indica missão inviável do ponto de vista de segurança."
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
# Avaliação individual
# ─────────────────────────────────────────

async def _evaluate_juror(
    juror: dict,
    mission: str,
    context_block: str = "",
) -> JurorResponse:
    """
    Executa a avaliação de um único jurado.

    Args:
        juror: Dicionário com name e system_prompt.
        mission: Texto da missão a ser avaliada.
        context_block: Bloco de contexto de arquivos (opcional).
    """
    context_section = f"\n{context_block}" if context_block else ""

    user_prompt: str = (
        f"Avalie a seguinte missão como {juror['name']}:\n\n"
        f"MISSÃO: {mission}"
        f"{context_section}\n\n"
        f"Responda com seu score (1.0-10.0), veredicto (APPROVE ou VETO) "
        f"e justificativa (máximo 500 caracteres).\n"
        f"Seu juror_name deve ser exatamente: {juror['name']}"
    )

    try:
        raw: dict = await call_ollama_json(
            system_prompt=juror["system_prompt"],
            user_prompt=user_prompt,
            model=settings.council_model,
        )
    except (OllamaUnavailableError, OllamaTimeoutError, OllamaInvalidResponseError) as e:
        raise RuntimeError(f"[{juror['name']}] {e}") from e

    raw["juror_name"] = juror["name"]

    # Trunca reasoning para respeitar limite do schema
    if isinstance(raw.get("reasoning"), str) and len(raw["reasoning"]) > 500:
        raw["reasoning"] = raw["reasoning"][:497] + "..."

    return JurorResponse(**raw)


# ─────────────────────────────────────────
# Orquestrador principal
# ─────────────────────────────────────────

async def run_council(
    mission: str,
    context_files: list[str] | None = None,
) -> CouncilDecision:
    """
    Executa o Conselho Consultivo de forma SEQUENCIAL.

    Args:
        mission: Texto da missão a ser avaliada.
        context_files: Lista opcional de caminhos de arquivos de contexto.

    Regra de Negócio:
        APPROVED se: média >= 8.0 AND SecurityCoder não deu VETO AND SecurityCoder score >= 5.0
    """
    # Monta bloco de contexto uma única vez para todos os jurados
    context_block: str = ""
    if context_files:
        from backend.tools.file_tools import build_context_block
        context_block = build_context_block(context_files)

    responses: List[JurorResponse] = []

    for juror in JURORS:
        print(f"  🧑‍⚖️  Jurado [{juror['name']}] avaliando...")
        response = await _evaluate_juror(juror, mission, context_block)
        responses.append(response)
        print(f"     Score: {response.score:.1f} | Veredicto: {response.verdict.value}")

    # ── Regra de Negócio ──
    average_score: float = round(
        sum(r.score for r in responses) / len(responses), 2
    )

    security: JurorResponse | None = next(
        (r for r in responses if r.juror_name == "SecurityCoder"), None
    )
    security_vetoed: bool = (
        security is not None and security.verdict == JurorVerdict.VETO
    )
    security_score_ok: bool = (
        security is not None and security.score >= 5.0
    )

    final_verdict = (
        "APPROVED"
        if average_score >= 8.0 and not security_vetoed and security_score_ok
        else "REJECTED"
    )

    return CouncilDecision(
        mission=mission,
        final_verdict=final_verdict,
        average_score=average_score,
        juror_responses=responses,
    )