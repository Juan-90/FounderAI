"""
Verdict — Regra de Decisão Final do Conselho Consultivo.
v3.0 / Módulo C3: Função pura isolada para facilitar testes e manutenção.

Limiares v3.0 (recalibrados para reduzir falsos-positivos de veto em modelos menores):
  APPROVED se:
    1. Média dos scores >= 7.5  (era 8.0 no MVP v2.0)
    2. Nenhum jurado emitiu VETO
    3. SecurityCoder score >= 6.0  (era 5.0 no MVP v2.0)
  REJECTED em qualquer outro caso.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

# ─────────────────────────────────────────
# Limiares configuráveis (v3.0)
# ─────────────────────────────────────────

APPROVAL_SCORE_THRESHOLD: float = 7.5   # Média mínima para aprovação
SECURITY_SCORE_THRESHOLD: float = 6.0   # Score mínimo do SecurityCoder


@dataclass(frozen=True)
class VerdictResult:
    """Resultado da avaliação de decisão — imutável e facilmente testável."""
    final_verdict: str   # "APPROVED" ou "REJECTED"
    average_score: float
    reason: str


def compute_final_verdict(juror_responses: list) -> VerdictResult:
    """
    Calcula o veredito final do Conselho de forma pura e determinística.

    Regras v3.0 (todas devem ser satisfeitas para APPROVED):
      1. Média >= APPROVAL_SCORE_THRESHOLD (7.5)
      2. Nenhum jurado emitiu VETO
      3. SecurityCoder score >= SECURITY_SCORE_THRESHOLD (6.0)

    Args:
        juror_responses: Lista de JurorResponse (ou objetos com .juror_name,
                         .score, .verdict). Aceita qualquer duck-typed list.

    Returns:
        VerdictResult com final_verdict, average_score e reason.
    """
    if not juror_responses:
        return VerdictResult(
            final_verdict="REJECTED",
            average_score=0.0,
            reason="Nenhuma resposta de jurado recebida.",
        )

    average_score: float = round(
        sum(r.score for r in juror_responses) / len(juror_responses), 2
    )

    # ── Verifica vetos ────────────────────────────────────────────────────────
    vetoes = [r for r in juror_responses if r.verdict.value == "VETO"]
    if vetoes:
        names = ", ".join(r.juror_name for r in vetoes)
        return VerdictResult(
            final_verdict="REJECTED",
            average_score=average_score,
            reason=f"Rejeitado por Veto de: {names}.",
        )

    # ── Verifica score crítico do SecurityCoder ───────────────────────────────
    security = next(
        (r for r in juror_responses if r.juror_name == "SecurityCoder"), None
    )
    if security is not None and security.score < SECURITY_SCORE_THRESHOLD:
        return VerdictResult(
            final_verdict="REJECTED",
            average_score=average_score,
            reason=(
                f"Rejeitado: SecurityCoder com score crítico "
                f"({security.score:.1f} < {SECURITY_SCORE_THRESHOLD})."
            ),
        )

    # ── Verifica média geral ──────────────────────────────────────────────────
    if average_score < APPROVAL_SCORE_THRESHOLD:
        return VerdictResult(
            final_verdict="REJECTED",
            average_score=average_score,
            reason=(
                f"Rejeitado: Média de pontuação ({average_score:.2f}) "
                f"abaixo do limiar {APPROVAL_SCORE_THRESHOLD}."
            ),
        )

    # ── Aprovado ──────────────────────────────────────────────────────────────
    return VerdictResult(
        final_verdict="APPROVED",
        average_score=average_score,
        reason=f"Aprovado com média {average_score:.2f} e sem vetos.",
    )