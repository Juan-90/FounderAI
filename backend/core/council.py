"""
Council Engine — Motor de Deliberação do Conselho Consultivo.
v3.5 / Fase 1: Multi-turno com diálogo entre jurados e fundador.

Fluxo:
  Turno 0 → evaluate_turn0 → necessita esclarecimento?
              ├── Sim → ClarificationRequest → status=PENDING_CLARIFICATION
              └── Não → veredito final          → status=FINAL

  Turno 1 → process_founder_reply → incorpora resposta → veredito final → status=FINAL

Regras de decisão: compute_final_verdict (v3.0 — backend/core/verdict.py)
  APPROVED se: média >= 7.5, SecurityCoder >= 6.0, nenhum VETO.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from backend.core.schemas import (
    ClarificationRequest,
    CouncilDecision,
    DeliberationState,
)
from backend.core.verdict import compute_final_verdict
from backend.schemas.council import JurorResponse, JurorVerdict


# ─────────────────────────────────────────
# Heurísticas de esclarecimento
# ─────────────────────────────────────────

# Score mínimo abaixo do qual o SecurityCoder sinaliza incerteza técnica
_SECURITY_UNCERTAINTY_THRESHOLD: float = 7.0

# Palavras-chave no reasoning que indicam necessidade de mais informação
_CLARIFICATION_KEYWORDS: frozenset[str] = frozenset({
    "?", "não sei", "não está claro", "preciso saber", "depende",
    "incerto", "indefinido", "falta informação", "falta de detalhe",
    "sem detalhes", "precisa esclarecer", "precisa definir",
    "não especificado", "não mencionado", "ambíguo",
})


def _reasoning_needs_clarification(reasoning: str) -> bool:
    """
    Verifica se o reasoning de um jurado contém sinais de incerteza
    ou necessidade de esclarecimento.
    """
    lower = reasoning.lower()
    return any(kw in lower for kw in _CLARIFICATION_KEYWORDS)


def _collect_clarification_questions(
    juror_responses: List[JurorResponse],
) -> list[str]:
    """
    Extrai perguntas implícitas dos reasonings dos jurados.
    Retorna lista de strings de perguntas formuladas para o fundador.
    """
    questions: list[str] = []

    for r in juror_responses:
        if not _reasoning_needs_clarification(r.reasoning):
            continue

        # Extrai frases interrogativas diretas do reasoning
        for sentence in r.reasoning.replace("?", "?\n").split("\n"):
            sentence = sentence.strip()
            if "?" in sentence and len(sentence) > 10:
                questions.append(f"[{r.juror_name}] {sentence}")

        # Se não encontrou perguntas explícitas, formula uma genérica
        if not questions or questions[-1].startswith(f"[{r.juror_name}]") is False:
            questions.append(
                f"[{r.juror_name}] Poderia fornecer mais detalhes sobre "
                f"os aspectos de {r.juror_name.lower()} da missão?"
            )

    # Remove duplicatas mantendo ordem
    seen: set[str] = set()
    unique: list[str] = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique


# ─────────────────────────────────────────
# Turno 0
# ─────────────────────────────────────────

def evaluate_turn0(
    mission: str,
    juror_responses: List[JurorResponse],
) -> Tuple[bool, Optional[ClarificationRequest]]:
    """
    Avalia se o Turno 0 requer esclarecimento do fundador.

    Critérios para gerar ClarificationRequest:
      1. Qualquer jurado tem reasoning com sinais de incerteza/perguntas.
      2. SecurityCoder emitiu VETO com score < _SECURITY_UNCERTAINTY_THRESHOLD
         (sinal de risco técnico crítico sem informação suficiente).

    Args:
        mission:         Texto da missão avaliada.
        juror_responses: Respostas dos jurados no Turno 0.

    Returns:
        Tuple (needs_clarification: bool, clarification: ClarificationRequest | None)
    """
    needs_clarification = False
    reasons: list[str] = []

    # ── Verifica reasoning de cada jurado ────────────────────────────────────
    for r in juror_responses:
        if _reasoning_needs_clarification(r.reasoning):
            needs_clarification = True
            reasons.append(
                f"{r.juror_name} sinalizou incerteza: "
                f"\"{r.reasoning[:120]}...\""
            )

    # ── Verifica incerteza técnica do SecurityCoder ───────────────────────────
    security = next(
        (r for r in juror_responses if r.juror_name == "SecurityCoder"), None
    )
    if (
        security is not None
        and security.verdict == JurorVerdict.VETO
        and security.score < _SECURITY_UNCERTAINTY_THRESHOLD
    ):
        needs_clarification = True
        reasons.append(
            f"SecurityCoder sinalizou risco técnico/segurança crítico "
            f"(score={security.score:.1f}, VETO). Esclarecimentos necessários."
        )

    if not needs_clarification:
        return False, None

    questions = _collect_clarification_questions(juror_responses)

    # Garante ao menos uma pergunta mesmo sem interrogativas explícitas
    if not questions:
        questions = [
            "Poderia fornecer mais detalhes técnicos e de segurança sobre a missão?",
            "Qual é o escopo exato e os usuários-alvo desta missão?",
        ]

    clarification = ClarificationRequest(
        reason=" | ".join(reasons),
        questions=questions,
    )

    return True, clarification


def process_turn0(
    mission: str,
    juror_responses: List[JurorResponse],
) -> DeliberationState:
    """
    Processa o Turno 0 e retorna o estado atualizado da deliberação.

    Se esclarecimento for necessário:
      → status="PENDING_CLARIFICATION" com ClarificationRequest preenchido.
    Caso contrário:
      → status="FINAL" com veredito calculado via regras v3.0.

    Args:
        mission:         Texto da missão avaliada.
        juror_responses: Respostas dos jurados no Turno 0.

    Returns:
        DeliberationState atualizado.
    """
    needs_clarification, clarification = evaluate_turn0(mission, juror_responses)

    if needs_clarification:
        return DeliberationState(
            mission=mission,
            status="PENDING_CLARIFICATION",
            turn0_responses=juror_responses,
            clarification=clarification,
        )

    # Sem necessidade de esclarecimento → veredito final direto
    verdict_result = compute_final_verdict(juror_responses)

    final_decision = CouncilDecision(
        verdict=verdict_result.final_verdict,       # type: ignore[arg-type]
        average_score=verdict_result.average_score,
        reason=verdict_result.reason,
    )

    return DeliberationState(
        mission=mission,
        status="FINAL",
        turn0_responses=juror_responses,
        clarification=None,
        final_decision=final_decision,
    )


# ─────────────────────────────────────────
# Turno 1
# ─────────────────────────────────────────

def process_founder_reply(
    state: DeliberationState,
    founder_reply: str,
    turn1_responses: List[JurorResponse],
) -> DeliberationState:
    """
    Processa a resposta do fundador (Turno 1) e calcula o veredito final.

    A resposta do fundador é incorporada ao contexto histórico.
    O veredito é calculado com base nas respostas do Turno 1
    (que já consideram o esclarecimento do fundador no prompt).

    Args:
        state:            Estado atual com status=PENDING_CLARIFICATION.
        founder_reply:    Resposta livre do fundador às perguntas do Turno 0.
        turn1_responses:  Novas avaliações dos jurados após o esclarecimento.

    Returns:
        DeliberationState com status="FINAL" e CouncilDecision preenchido.

    Raises:
        ValueError: Se o estado não estiver em PENDING_CLARIFICATION.
    """
    if state.status != "PENDING_CLARIFICATION":
        raise ValueError(
            f"process_founder_reply exige status='PENDING_CLARIFICATION'. "
            f"Estado atual: '{state.status}'."
        )

    if not turn1_responses:
        raise ValueError("turn1_responses não pode ser vazio.")

    # Calcula veredito com as respostas do Turno 1
    verdict_result = compute_final_verdict(turn1_responses)

    final_decision = CouncilDecision(
        verdict=verdict_result.final_verdict,       # type: ignore[arg-type]
        average_score=verdict_result.average_score,
        reason=verdict_result.reason,
    )

    return DeliberationState(
        mission=state.mission,
        status="FINAL",
        turn0_responses=state.turn0_responses,
        clarification=state.clarification,
        founder_response=founder_reply,
        turn1_responses=turn1_responses,
        final_decision=final_decision,
    )


# ─────────────────────────────────────────
# Cancelamento
# ─────────────────────────────────────────

def cancel_deliberation(state: DeliberationState, reason: str = "") -> DeliberationState:
    """
    Cancela uma deliberação em andamento.
    Útil quando o fundador abandona o diálogo.

    Args:
        state:  Estado atual da deliberação.
        reason: Motivo do cancelamento (opcional).

    Returns:
        DeliberationState com status="CANCELLED".
    """
    return DeliberationState(
        mission=state.mission,
        status="CANCELLED",
        turn0_responses=state.turn0_responses,
        clarification=state.clarification,
        founder_response=reason or state.founder_response,
        turn1_responses=state.turn1_responses,
        final_decision=state.final_decision,
    )