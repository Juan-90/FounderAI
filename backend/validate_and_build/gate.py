"""
DecisionGate — lógica pura de decisão VALIDATE→BUILD (v4.5.0).

SEM chamadas de LLM: recebe (verdict, confidence, conditions) e a política
(require_human_confirmation, min_confidence) e devolve BuildGateDecision.

Regras:
  • DISCARD / PIVOT / INVESTIGATE -> should_build=False, needs_human=False.
  • BUILD + confiança>=min + sem condições críticas + sem exigência humana
      -> should_build=True, needs_human=False (auto-build).
  • BUILD + (confiança<min OU condições críticas OU exigência humana)
      -> should_build=True, needs_human=True (aprovado, aguardando humano).

Definição de "condição crítica": qualquer condição não-vazia (postura
conservadora do Guardião do Tempo).
"""

from __future__ import annotations

from typing import Optional, Sequence

from backend.core.config import Settings, settings
from backend.validate_and_build.schemas import (
    BuildGateDecision,
    ValidationVerdictLiteral,
)

_NO_BUILD_VERDICTS = {"DISCARD", "PIVOT", "INVESTIGATE"}


class DecisionGate:
    """Gate de decisão puro e testável (sem LLM)."""

    def __init__(self, config: Settings | None = None) -> None:
        self._config: Settings = config if config is not None else settings

    def evaluate(
        self,
        verdict: ValidationVerdictLiteral,
        confidence: float,
        conditions: Optional[Sequence[str]] = None,
        require_human_confirmation: Optional[bool] = None,
        min_confidence: Optional[float] = None,
    ) -> BuildGateDecision:
        cond = list(conditions or [])
        rhc = (
            require_human_confirmation
            if require_human_confirmation is not None
            else self._config.VAB_REQUIRE_HUMAN_CONFIRMATION
        )
        minc = (
            min_confidence
            if min_confidence is not None
            else self._config.VAB_MIN_CONFIDENCE_TO_AUTOBUILD
        )

        if verdict in _NO_BUILD_VERDICTS:
            return BuildGateDecision(
                should_build=False,
                needs_human_confirmation=False,
                reason=f"Veredito '{verdict}' não autoriza prosseguir para o BUILD.",
                source_verdict=verdict,
                confidence=confidence,
                conditions=cond,
            )

        # verdict == BUILD
        has_critical = len(cond) > 0
        auto_build = (
            confidence >= minc and not has_critical and not rhc
        )

        if auto_build:
            return BuildGateDecision(
                should_build=True,
                needs_human_confirmation=False,
                reason=(
                    f"BUILD autorizado: confiança {confidence:.2f} >= {minc:.2f}, "
                    "sem condições críticas e sem exigência de confirmação humana."
                ),
                source_verdict="BUILD",
                confidence=confidence,
                conditions=cond,
            )

        motivos = []
        if confidence < minc:
            motivos.append(f"confiança {confidence:.2f} < {minc:.2f}")
        if has_critical:
            motivos.append(f"{len(cond)} condição(ões) crítica(s) pendente(s)")
        if rhc:
            motivos.append("política exige confirmação humana")
        return BuildGateDecision(
            should_build=True,
            needs_human_confirmation=True,
            reason="BUILD aprovado, mas aguardando confirmação humana: "
            + "; ".join(motivos) + ".",
            source_verdict="BUILD",
            confidence=confidence,
            conditions=cond,
        )