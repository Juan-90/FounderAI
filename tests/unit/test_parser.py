"""
tests/unit/test_parser.py
Suite de testes — Módulo C1: Validação de consistência score↔verdict.

Execução:
    pytest tests/unit/test_parser.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from backend.schemas.council import JurorResponse, JurorVerdict


# ─────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────

def _make_raw(
    name: str = "Architect",
    score: float = 8.0,
    verdict: str = "APPROVE",
    reasoning: str = "Missão viável.",
) -> dict:
    return {
        "juror_name": name,
        "score": score,
        "verdict": verdict,
        "reasoning": reasoning,
    }


# ─────────────────────────────────────────
# Casos válidos
# ─────────────────────────────────────────

class TestValidResponses:
    def test_approve_high_score(self):
        """APPROVE com score 8.0 deve passar."""
        r = JurorResponse(**_make_raw(score=8.0, verdict="APPROVE"))
        assert r.verdict == JurorVerdict.APPROVE
        assert r.score == 8.0

    def test_approve_boundary_score(self):
        """APPROVE com score exatamente 5.0 deve passar."""
        r = JurorResponse(**_make_raw(score=5.0, verdict="APPROVE"))
        assert r.verdict == JurorVerdict.APPROVE

    def test_veto_low_score(self):
        """VETO com score 3.0 deve passar."""
        r = JurorResponse(**_make_raw(score=3.0, verdict="VETO"))
        assert r.verdict == JurorVerdict.VETO
        assert r.score == 3.0

    def test_veto_boundary_score(self):
        """VETO com score 6.9 deve passar."""
        r = JurorResponse(**_make_raw(score=6.9, verdict="VETO"))
        assert r.verdict == JurorVerdict.VETO

    def test_reasoning_max_length(self):
        """reasoning com 500 chars deve passar."""
        r = JurorResponse(**_make_raw(reasoning="x" * 500))
        assert len(r.reasoning) == 500

    def test_score_minimum(self):
        """Score 1.0 deve ser aceito."""
        r = JurorResponse(**_make_raw(score=1.0, verdict="VETO"))
        assert r.score == 1.0

    def test_score_maximum(self):
        """Score 10.0 com APPROVE deve ser aceito."""
        r = JurorResponse(**_make_raw(score=10.0, verdict="APPROVE"))
        assert r.score == 10.0


# ─────────────────────────────────────────
# Casos inválidos — inconsistência
# ─────────────────────────────────────────

class TestInconsistentResponses:
    def test_veto_with_high_score_fails(self):
        """VETO com score 8.5 deve falhar."""
        with pytest.raises(ValidationError) as exc_info:
            JurorResponse(**_make_raw(score=8.5, verdict="VETO"))
        assert "VETO is not allowed with score >= 7.0" in str(exc_info.value)

    def test_veto_with_score_exactly_7_fails(self):
        """VETO com score exatamente 7.0 deve falhar."""
        with pytest.raises(ValidationError) as exc_info:
            JurorResponse(**_make_raw(score=7.0, verdict="VETO"))
        assert "VETO is not allowed with score >= 7.0" in str(exc_info.value)

    def test_approve_with_low_score_fails(self):
        """APPROVE com score 4.0 deve falhar."""
        with pytest.raises(ValidationError) as exc_info:
            JurorResponse(**_make_raw(score=4.0, verdict="APPROVE"))
        assert "APPROVE is not allowed with score < 5.0" in str(exc_info.value)

    def test_approve_with_score_49_fails(self):
        """APPROVE com score 4.9 deve falhar."""
        with pytest.raises(ValidationError) as exc_info:
            JurorResponse(**_make_raw(score=4.9, verdict="APPROVE"))
        assert "APPROVE is not allowed with score < 5.0" in str(exc_info.value)

    def test_score_below_minimum_fails(self):
        """Score 0.9 deve falhar (ge=1.0)."""
        with pytest.raises(ValidationError):
            JurorResponse(**_make_raw(score=0.9, verdict="VETO"))

    def test_score_above_maximum_fails(self):
        """Score 10.1 deve falhar (le=10.0)."""
        with pytest.raises(ValidationError):
            JurorResponse(**_make_raw(score=10.1, verdict="APPROVE"))

    def test_reasoning_over_500_fails(self):
        """reasoning com 501 chars deve falhar."""
        with pytest.raises(ValidationError):
            JurorResponse(**_make_raw(reasoning="x" * 501))

    def test_invalid_verdict_fails(self):
        """Verdict fora do Enum deve falhar."""
        with pytest.raises(ValidationError):
            JurorResponse(**_make_raw(verdict="MAYBE"))


# ─────────────────────────────────────────
# Retry e fallback (Módulo C1)
# ─────────────────────────────────────────

JUROR = {
    "name": "Architect",
    "system_prompt": "Você é o Architect.",
}
MISSION = "Criar um app de finanças para MEIs."


@pytest.mark.asyncio
async def test_first_call_valid_no_retry():
    """Resposta válida na primeira tentativa — sem retry."""
    valid_raw = _make_raw(score=8.0, verdict="APPROVE")

    with patch(
        "backend.agents.council.call_ollama_json",
        new_callable=AsyncMock,
        return_value=valid_raw,
    ) as mock_call:
        from backend.agents.council import _evaluate_juror
        result = await _evaluate_juror(JUROR, MISSION)

    assert result.verdict == JurorVerdict.APPROVE
    assert result.score == 8.0
    assert mock_call.call_count == 1


@pytest.mark.asyncio
async def test_inconsistent_first_triggers_retry():
    """
    Primeira resposta inconsistente (VETO + 8.5) → retry →
    segunda válida (VETO + 3.0).
    """
    inconsistent = _make_raw(score=8.5, verdict="VETO")
    valid_retry   = _make_raw(score=3.0, verdict="VETO")

    with patch(
        "backend.agents.council.call_ollama_json",
        new_callable=AsyncMock,
        side_effect=[inconsistent, valid_retry],
    ) as mock_call:
        from backend.agents.council import _evaluate_juror
        result = await _evaluate_juror(JUROR, MISSION)

    assert result.verdict == JurorVerdict.VETO
    assert result.score == 3.0
    assert mock_call.call_count == 2


@pytest.mark.asyncio
async def test_fallback_when_retry_also_fails():
    """
    Ambas as respostas inconsistentes → fallback: VETO + score 4.0.
    """
    inconsistent = _make_raw(score=8.5, verdict="VETO")

    with patch(
        "backend.agents.council.call_ollama_json",
        new_callable=AsyncMock,
        side_effect=[inconsistent, inconsistent],
    ):
        from backend.agents.council import _evaluate_juror
        result = await _evaluate_juror(JUROR, MISSION)

    assert result.verdict == JurorVerdict.VETO
    assert result.score == 4.0
    assert "[FALLBACK]" in result.reasoning


@pytest.mark.asyncio
async def test_fallback_on_llm_error_in_retry():
    """
    Primeira resposta inconsistente + retry levanta LLMProviderError →
    fallback seguro.
    """
    from backend.core.llm_client import LLMErrorKind, LLMProviderError

    inconsistent = _make_raw(score=4.0, verdict="APPROVE")

    with patch(
        "backend.agents.council.call_ollama_json",
        new_callable=AsyncMock,
        side_effect=[
            inconsistent,
            LLMProviderError("timeout", kind=LLMErrorKind.TIMEOUT),
        ],
    ):
        from backend.agents.council import _evaluate_juror
        result = await _evaluate_juror(JUROR, MISSION)

    assert result.verdict == JurorVerdict.VETO
    assert result.score == 4.0
    assert "[FALLBACK]" in result.reasoning