"""
tests/integration/test_cli_flow.py
Suite de testes de integração — Fluxo E2E da CLI v3.5.

Testa os 3 fluxos principais sem chamar o LLM real (mocks).

Execução:
    pytest tests/integration/test_cli_flow.py -v --asyncio-mode=auto
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.council import (
    cancel_deliberation,
    process_founder_reply,
    process_turn0,
)
from backend.core.schemas import DeliberationState
from backend.schemas.council import JurorResponse, JurorVerdict


# ─────────────────────────────────────────
# Fixtures compartilhadas
# ─────────────────────────────────────────

MISSION_CLEAR = "Criar um app de controle financeiro para MEIs com Open Banking."
MISSION_VAGUE = "Criar algo com IA para empresas."


def _resp(
    name: str,
    score: float,
    verdict: str = "APPROVE",
    reasoning: str = "Avaliação concluída.",
) -> JurorResponse:
    return JurorResponse(
        juror_name=name,
        score=score,
        verdict=JurorVerdict(verdict),
        reasoning=reasoning,
    )


def _clear_responses() -> list[JurorResponse]:
    """Respostas claras → Turno 0 vai direto para FINAL."""
    return [
        _resp("Architect",     8.0, reasoning="Stack bem definido. Open Banking API disponível."),
        _resp("SecurityCoder", 7.5, reasoning="LGPD aplicável. OAuth2 e criptografia necessários."),
        _resp("Generalist",    8.5, reasoning="MEIs representam 15M de pessoas. Mercado validado."),
    ]


def _uncertain_responses() -> list[JurorResponse]:
    """SecurityCoder com incerteza → gera PENDING_CLARIFICATION."""
    return [
        _resp("Architect",     7.0, reasoning="Tecnicamente possível."),
        _resp("SecurityCoder", 5.0, verdict="VETO",
              reasoning="Não está claro como os dados financeiros serão protegidos. "
                         "Qual criptografia será usada?"),
        _resp("Generalist",    7.5, reasoning="Mercado existe mas precisa de mais detalhes."),
    ]


def _turn1_good_responses() -> list[JurorResponse]:
    """Respostas do Turno 1 após esclarecimento satisfatório."""
    return [
        _resp("Architect",     8.5, reasoning="AES-256 + OAuth2 confirmados. Arquitetura sólida."),
        _resp("SecurityCoder", 7.5, reasoning="Criptografia adequada informada. LGPD endereçada."),
        _resp("Generalist",    8.0, reasoning="Fundador esclareceu público-alvo e modelo de receita."),
    ]


def _turn1_bad_responses() -> list[JurorResponse]:
    """Respostas do Turno 1 com resposta insatisfatória → REJECTED."""
    return [
        _resp("Architect",     6.0, reasoning="Resposta técnica ainda vaga."),
        _resp("SecurityCoder", 5.5, reasoning="Segurança ainda não endereçada adequadamente."),
        _resp("Generalist",    6.5, reasoning="Modelo de negócio ainda pouco claro."),
    ]


# ─────────────────────────────────────────
# Caso 1: Caminho Feliz — Turno 0 → FINAL direto
# ─────────────────────────────────────────

class TestHappyPathTurn0Direct:
    """Missão clara → Turno 0 conclui com status=FINAL sem pedir esclarecimento."""

    def test_state_is_final_after_clear_turn0(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        assert state.status == "FINAL"

    def test_final_decision_is_set(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        assert state.final_decision is not None

    def test_verdict_approved_on_clear_mission(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        assert state.final_decision is not None
        assert state.final_decision.verdict == "APPROVED"

    def test_no_clarification_on_clear_mission(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        assert state.clarification is None

    def test_turn0_responses_preserved(self):
        responses = _clear_responses()
        state = process_turn0(MISSION_CLEAR, responses)
        assert len(state.turn0_responses) == len(responses)

    def test_reason_is_populated(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        assert state.final_decision is not None
        assert len(state.final_decision.reason.strip()) > 0

    def test_average_score_above_threshold(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        assert state.final_decision is not None
        assert state.final_decision.average_score >= 7.5

    def test_mission_preserved_in_state(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        assert state.mission == MISSION_CLEAR


# ─────────────────────────────────────────
# Caso 2: Fluxo Completo 2 Turnos
# ─────────────────────────────────────────

class TestFullTwoTurnFlow:
    """Missão vaga → PENDING → fundador responde → Turno 1 → FINAL."""

    def _pending_state(self) -> DeliberationState:
        return process_turn0(MISSION_VAGUE, _uncertain_responses())

    def test_turn0_is_pending_on_uncertain_mission(self):
        assert self._pending_state().status == "PENDING_CLARIFICATION"

    def test_clarification_is_generated(self):
        state = self._pending_state()
        assert state.clarification is not None
        assert len(state.clarification.questions) > 0

    def test_clarification_has_reason(self):
        state = self._pending_state()
        assert state.clarification is not None
        assert len(state.clarification.reason.strip()) > 0

    def test_turn1_produces_final_state(self):
        state = self._pending_state()
        final = process_founder_reply(state, "AES-256 + OAuth2.", _turn1_good_responses())
        assert final.status == "FINAL"

    def test_turn1_approved_on_good_reply(self):
        state = self._pending_state()
        final = process_founder_reply(
            state, "AES-256 e OAuth2. LGPD com consentimento explícito.", _turn1_good_responses()
        )
        assert final.final_decision is not None
        assert final.final_decision.verdict == "APPROVED"

    def test_turn1_rejected_on_insufficient_reply(self):
        state = self._pending_state()
        final = process_founder_reply(state, "Vamos pensar nisso depois.", _turn1_bad_responses())
        assert final.final_decision is not None
        assert final.final_decision.verdict == "REJECTED"

    def test_founder_response_preserved(self):
        state = self._pending_state()
        reply = "Usaremos AES-256 e OAuth2."
        final = process_founder_reply(state, reply, _turn1_good_responses())
        assert final.founder_response == reply

    def test_turn0_responses_preserved_in_final(self):
        state = self._pending_state()
        final = process_founder_reply(state, "Ok.", _turn1_good_responses())
        assert len(final.turn0_responses) == len(_uncertain_responses())

    def test_turn1_responses_in_final_state(self):
        state = self._pending_state()
        t1 = _turn1_good_responses()
        final = process_founder_reply(state, "Detalhado.", t1)
        assert final.turn1_responses is not None
        assert len(final.turn1_responses) == len(t1)

    def test_full_state_has_both_turns(self):
        state = self._pending_state()
        final = process_founder_reply(state, "Completo.", _turn1_good_responses())
        assert len(final.turn0_responses) > 0
        assert final.turn1_responses is not None
        assert final.founder_response is not None


# ─────────────────────────────────────────
# Caso 3: Cancelamento pelo Fundador
# ─────────────────────────────────────────

class TestCancellationFlow:
    """PENDING_CLARIFICATION → /cancel ou vazio → CANCELLED."""

    def _pending_state(self) -> DeliberationState:
        return process_turn0(MISSION_VAGUE, _uncertain_responses())

    def test_cancel_command_produces_cancelled_state(self):
        cancelled = cancel_deliberation(self._pending_state(), reason="/cancel")
        assert cancelled.status == "CANCELLED"

    def test_empty_input_produces_cancelled_state(self):
        cancelled = cancel_deliberation(
            self._pending_state(), reason="Fundador encerrou sem responder."
        )
        assert cancelled.status == "CANCELLED"

    def test_cancellation_preserves_mission(self):
        cancelled = cancel_deliberation(self._pending_state())
        assert cancelled.mission == MISSION_VAGUE

    def test_cancellation_preserves_turn0_responses(self):
        cancelled = cancel_deliberation(self._pending_state())
        assert len(cancelled.turn0_responses) == len(_uncertain_responses())

    def test_cancellation_preserves_clarification(self):
        cancelled = cancel_deliberation(self._pending_state())
        assert cancelled.clarification is not None

    def test_cancel_reason_stored(self):
        reason = "Fundador desistiu da missão."
        cancelled = cancel_deliberation(self._pending_state(), reason=reason)
        assert cancelled.founder_response == reason

    def test_no_final_decision_after_cancel(self):
        cancelled = cancel_deliberation(self._pending_state())
        assert cancelled.final_decision is None

    def test_cannot_process_reply_after_cancel(self):
        cancelled = cancel_deliberation(self._pending_state())
        with pytest.raises(ValueError, match="PENDING_CLARIFICATION"):
            process_founder_reply(cancelled, "tarde demais.", _turn1_good_responses())

    def test_cancel_from_final_state_works(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        cancelled = cancel_deliberation(state, "Mudei de ideia.")
        assert cancelled.status == "CANCELLED"


# ─────────────────────────────────────────
# Integridade do DeliberationState
# ─────────────────────────────────────────

class TestDeliberationStateIntegrity:
    def test_state_is_pydantic_model(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        assert isinstance(state, DeliberationState)

    def test_status_is_valid_literal(self):
        valid = {"PENDING_CLARIFICATION", "FINAL", "CANCELLED"}
        for responses, mission in [
            (_clear_responses(), MISSION_CLEAR),
            (_uncertain_responses(), MISSION_VAGUE),
        ]:
            state = process_turn0(mission, responses)
            assert state.status in valid

    def test_final_decision_type(self):
        from backend.core.schemas import CouncilDecision
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        assert isinstance(state.final_decision, CouncilDecision)

    def test_clarification_type(self):
        from backend.core.schemas import ClarificationRequest
        state = process_turn0(MISSION_VAGUE, _uncertain_responses())
        assert isinstance(state.clarification, ClarificationRequest)

    def test_turn0_responses_are_juror_responses(self):
        state = process_turn0(MISSION_CLEAR, _clear_responses())
        for r in state.turn0_responses:
            assert isinstance(r, JurorResponse)