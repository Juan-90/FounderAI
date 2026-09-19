"""
tests/unit/test_council_engine.py
Suite de testes — v3.5 Fase 1: Motor de deliberação multi-turno.

Execução:
    pytest tests/unit/test_council_engine.py -v
"""

from __future__ import annotations

import pytest

from backend.core.council import (
    cancel_deliberation,
    evaluate_turn0,
    process_founder_reply,
    process_turn0,
)
from backend.schemas.council import JurorResponse, JurorVerdict


# ─────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────

MISSION = "Criar um app de finanças para MEIs no Brasil."


def _resp(
    name: str,
    score: float,
    verdict: str = "APPROVE",
    reasoning: str = "Missão bem definida e viável.",
) -> JurorResponse:
    return JurorResponse(
        juror_name=name,
        score=score,
        verdict=JurorVerdict(verdict),
        reasoning=reasoning,
    )


def _clear_panel() -> list[JurorResponse]:
    """Respostas sem sinais de incerteza → não gera clarificação."""
    return [
        _resp("Architect",     8.0, reasoning="Arquitetura bem definida. Tecnicamente viável."),
        _resp("SecurityCoder", 7.5, reasoning="LGPD aplicável. Risco controlado com autenticação adequada."),
        _resp("Generalist",    8.5, reasoning="Mercado validado. MEIs representam 15M de pessoas no Brasil."),
    ]


def _uncertain_panel() -> list[JurorResponse]:
    """SecurityCoder com dúvida explícita → gera clarificação."""
    return [
        _resp("Architect",     7.5, reasoning="Viável tecnicamente."),
        _resp("SecurityCoder", 5.0, verdict="VETO",
              reasoning="Não está claro como os dados financeiros serão criptografados. "
                         "Como será feita a autenticação?"),
        _resp("Generalist",    7.0, reasoning="Mercado existe."),
    ]


def _turn1_panel() -> list[JurorResponse]:
    """Respostas do Turno 1 após esclarecimento do fundador."""
    return [
        _resp("Architect",     8.0, reasoning="Após esclarecimento, arquitetura adequada."),
        _resp("SecurityCoder", 7.5, reasoning="Criptografia AES-256 e OAuth2 confirmados. Adequado."),
        _resp("Generalist",    8.5, reasoning="Contexto reforçado pelo fundador. Viável."),
    ]


# ─────────────────────────────────────────
# evaluate_turn0
# ─────────────────────────────────────────

class TestEvaluateTurn0:
    def test_no_clarification_needed_clear_panel(self):
        """Painel claro → não precisa de esclarecimento."""
        needs, clarification = evaluate_turn0(MISSION, _clear_panel())
        assert needs is False
        assert clarification is None

    def test_clarification_needed_on_uncertainty(self):
        """SecurityCoder com VETO e dúvida explícita → precisa esclarecimento."""
        needs, clarification = evaluate_turn0(MISSION, _uncertain_panel())
        assert needs is True
        assert clarification is not None
        assert len(clarification.questions) > 0
        assert len(clarification.reason) > 0

    def test_clarification_contains_security_reason(self):
        """Reason deve mencionar SecurityCoder."""
        _, clarification = evaluate_turn0(MISSION, _uncertain_panel())
        assert clarification is not None
        assert "SecurityCoder" in clarification.reason

    def test_clarification_questions_are_non_empty_strings(self):
        """Todas as perguntas devem ser strings não-vazias."""
        _, clarification = evaluate_turn0(MISSION, _uncertain_panel())
        assert clarification is not None
        for q in clarification.questions:
            assert isinstance(q, str)
            assert len(q.strip()) > 0

    def test_no_clarification_on_empty_responses(self):
        """Lista vazia → sem clarificação (sem dados para analisar)."""
        needs, clarification = evaluate_turn0(MISSION, [])
        assert needs is False
        assert clarification is None


# ─────────────────────────────────────────
# process_turn0
# ─────────────────────────────────────────

class TestProcessTurn0:
    def test_clear_panel_goes_to_final(self):
        """Painel claro → status=FINAL com decisão preenchida."""
        state = process_turn0(MISSION, _clear_panel())
        assert state.status == "FINAL"
        assert state.final_decision is not None
        assert state.clarification is None

    def test_clear_panel_verdict_approved(self):
        """Painel com média >= 7.5 e sem vetos → APPROVED."""
        state = process_turn0(MISSION, _clear_panel())
        assert state.final_decision is not None
        assert state.final_decision.verdict == "APPROVED"

    def test_uncertain_panel_pending_clarification(self):
        """Painel com incerteza → status=PENDING_CLARIFICATION."""
        state = process_turn0(MISSION, _uncertain_panel())
        assert state.status == "PENDING_CLARIFICATION"
        assert state.clarification is not None
        assert state.final_decision is None

    def test_turn0_responses_preserved(self):
        """turn0_responses deve ser preservado no estado."""
        panel = _clear_panel()
        state = process_turn0(MISSION, panel)
        assert len(state.turn0_responses) == len(panel)

    def test_mission_preserved(self):
        """Missão deve ser preservada no estado."""
        state = process_turn0(MISSION, _clear_panel())
        assert state.mission == MISSION

    def test_low_average_rejected(self):
        """Média < 7.5 sem clarificação → REJECTED."""
        low_panel = [
            _resp("Architect",     7.0, reasoning="Aceitável."),
            _resp("SecurityCoder", 6.5, reasoning="Segurança básica ok."),
            _resp("Generalist",    7.0, reasoning="Mercado pequeno."),
        ]
        state = process_turn0(MISSION, low_panel)
        assert state.status == "FINAL"
        assert state.final_decision is not None
        assert state.final_decision.verdict == "REJECTED"
        assert "7.17" in state.final_decision.reason or "limiar" in state.final_decision.reason


# ─────────────────────────────────────────
# process_founder_reply
# ─────────────────────────────────────────

class TestProcessFounderReply:
    def _pending_state(self):
        return process_turn0(MISSION, _uncertain_panel())

    def test_final_status_after_reply(self):
        """Após reply do fundador → status=FINAL."""
        state = self._pending_state()
        final = process_founder_reply(state, "Usaremos AES-256 e OAuth2.", _turn1_panel())
        assert final.status == "FINAL"

    def test_founder_response_preserved(self):
        """Resposta do fundador deve ser preservada no estado final."""
        state = self._pending_state()
        reply = "Usaremos AES-256 e OAuth2 com MFA."
        final = process_founder_reply(state, reply, _turn1_panel())
        assert final.founder_response == reply

    def test_turn1_responses_preserved(self):
        """Respostas do Turno 1 devem estar no estado final."""
        state = self._pending_state()
        t1 = _turn1_panel()
        final = process_founder_reply(state, "Esclarecido.", t1)
        assert final.turn1_responses is not None
        assert len(final.turn1_responses) == len(t1)

    def test_turn0_responses_preserved_in_final(self):
        """Respostas do Turno 0 devem ser preservadas após o Turno 1."""
        state = self._pending_state()
        final = process_founder_reply(state, "Ok.", _turn1_panel())
        assert len(final.turn0_responses) == len(_uncertain_panel())

    def test_verdict_approved_after_good_turn1(self):
        """Turno 1 com boas respostas → APPROVED."""
        state = self._pending_state()
        final = process_founder_reply(state, "Detalhes fornecidos.", _turn1_panel())
        assert final.final_decision is not None
        assert final.final_decision.verdict == "APPROVED"

    def test_reason_non_empty_in_final(self):
        """reason nunca deve ser vazio no veredito final."""
        state = self._pending_state()
        final = process_founder_reply(state, "Ok.", _turn1_panel())
        assert final.final_decision is not None
        assert len(final.final_decision.reason.strip()) > 0

    def test_raises_if_status_not_pending(self):
        """Chamar process_founder_reply em estado não-PENDING → ValueError."""
        state = process_turn0(MISSION, _clear_panel())
        assert state.status == "FINAL"
        with pytest.raises(ValueError, match="PENDING_CLARIFICATION"):
            process_founder_reply(state, "Resposta.", _turn1_panel())

    def test_raises_if_empty_turn1_responses(self):
        """turn1_responses vazio → ValueError."""
        state = self._pending_state()
        with pytest.raises(ValueError, match="vazio"):
            process_founder_reply(state, "Ok.", [])


# ─────────────────────────────────────────
# cancel_deliberation
# ─────────────────────────────────────────

class TestCancelDeliberation:
    def test_cancel_sets_status_cancelled(self):
        """Cancelamento deve setar status=CANCELLED."""
        state = process_turn0(MISSION, _uncertain_panel())
        cancelled = cancel_deliberation(state, "Fundador desistiu.")
        assert cancelled.status == "CANCELLED"

    def test_cancel_preserves_mission(self):
        """Missão deve ser preservada no estado cancelado."""
        state = process_turn0(MISSION, _uncertain_panel())
        cancelled = cancel_deliberation(state)
        assert cancelled.mission == MISSION

    def test_cancel_preserves_turn0_responses(self):
        """Respostas do Turno 0 devem ser preservadas."""
        state = process_turn0(MISSION, _uncertain_panel())
        cancelled = cancel_deliberation(state)
        assert len(cancelled.turn0_responses) == len(_uncertain_panel())

    def test_cancel_reason_stored_in_founder_response(self):
        """Motivo do cancelamento vai para founder_response."""
        state = process_turn0(MISSION, _uncertain_panel())
        reason = "Fundador desistiu da missão."
        cancelled = cancel_deliberation(state, reason)
        assert cancelled.founder_response == reason