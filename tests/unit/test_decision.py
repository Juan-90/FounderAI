"""
tests/unit/test_decision.py
Suite de testes — Módulo C3: compute_final_verdict (limiares v3.0).

Execução:
    pytest tests/unit/test_decision.py -v
"""

from __future__ import annotations

import pytest

from backend.core.verdict import (
    APPROVAL_SCORE_THRESHOLD,
    SECURITY_SCORE_THRESHOLD,
    VerdictResult,
    compute_final_verdict,
)
from backend.schemas.council import JurorResponse, JurorVerdict


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _make_response(
    name: str,
    score: float,
    verdict: str | JurorVerdict = "APPROVE",
    reasoning: str = "Ok.",
) -> JurorResponse:
    return JurorResponse(
        juror_name=name,
        score=score,
        verdict=JurorVerdict(verdict) if isinstance(verdict, str) else verdict,
        reasoning=reasoning,
    )


def _council(
    architect_score: float = 8.0,
    security_score: float = 8.0,
    generalist_score: float = 8.0,
    architect_verdict: str = "APPROVE",
    security_verdict: str = "APPROVE",
    generalist_verdict: str = "APPROVE",
) -> list[JurorResponse]:
    return [
        _make_response("Architect",     architect_score,  architect_verdict),
        _make_response("SecurityCoder", security_score,   security_verdict),
        _make_response("Generalist",    generalist_score, generalist_verdict),
    ]


# ─────────────────────────────────────────
# Casos especificados pelo Módulo C3
# ─────────────────────────────────────────

class TestOfficialScenarios:
    def test_caso1_todos_aprovam_nota_alta(self):
        """Caso 1: média 8.0, SecurityCoder 8.0, sem vetos → APPROVED."""
        result = compute_final_verdict(_council(8.0, 8.0, 8.0))
        assert result.final_verdict == "APPROVED"
        assert result.average_score == 8.0
        assert "Aprovado" in result.reason

    def test_caso2_media_baixa_sem_veto(self):
        """Caso 2: notas 7.0/7.0/7.0 → média 7.0 < 7.5 → REJECTED por média."""
        result = compute_final_verdict(_council(7.0, 7.0, 7.0))
        assert result.final_verdict == "REJECTED"
        assert result.average_score == 7.0
        assert "7.0" in result.reason or "limiar" in result.reason.lower()

    def test_caso3_media_alta_com_veto_architect(self):
        """Caso 3: Architect dá VETO → REJECTED por veto, independente da média."""
        # Architect com VETO deve ter score < 7.0 (regra C1)
        result = compute_final_verdict(
            _council(6.5, 8.0, 8.0, architect_verdict="VETO")
        )
        assert result.final_verdict == "REJECTED"
        assert "Architect" in result.reason
        assert "Veto" in result.reason or "veto" in result.reason.lower()

    def test_caso4_security_score_critico_sem_veto(self):
        """Caso 4: SecurityCoder score 5.5 < 6.0 sem VETO, média 7.8 → REJECTED."""
        # SecurityCoder APPROVE com score 5.5 é válido pelo C1 (>= 5.0)
        result = compute_final_verdict(_council(8.0, 5.5, 9.5))
        assert result.final_verdict == "REJECTED"
        assert "5.5" in result.reason or "SecurityCoder" in result.reason

    def test_caso5_limiar_exato_approved(self):
        """Caso 5: média exata 7.5 e SecurityCoder 6.0 → APPROVED."""
        # 7.5 + 6.0 + 9.0 = 22.5 / 3 = 7.5 exato
        result = compute_final_verdict(_council(7.5, 6.0, 9.0))
        assert result.final_verdict == "APPROVED"
        assert result.average_score == 7.5


# ─────────────────────────────────────────
# Limiares e edge cases
# ─────────────────────────────────────────

class TestThresholdEdgeCases:
    def test_media_abaixo_por_margem_minima(self):
        """Média 7.49 deve ser REJECTED."""
        # 7.49 + 6.0 + 9.0 = 22.49 / 3 ≈ 7.4967
        result = compute_final_verdict(_council(7.49, 6.0, 8.99))
        assert result.final_verdict == "REJECTED"

    def test_security_score_exatamente_no_limiar(self):
        """SecurityCoder score exatamente 6.0 não deve rejeitar.
        Média: (8.0 + 6.0 + 9.0) / 3 = 7.67 >= 7.5 → APPROVED.
        """
        result = compute_final_verdict(_council(8.0, 6.0, 9.0))
        assert result.final_verdict == "APPROVED"
        assert result.average_score == round((8.0 + 6.0 + 9.0) / 3, 2)

    def test_security_score_abaixo_do_limiar(self):
        """SecurityCoder score 5.9 deve rejeitar mesmo sem veto."""
        result = compute_final_verdict(_council(9.0, 5.9, 9.0))
        assert result.final_verdict == "REJECTED"
        assert "SecurityCoder" in result.reason

    def test_veto_generalist_rejeita(self):
        """VETO do Generalist deve rejeitar independente dos outros."""
        result = compute_final_verdict(
            _council(9.0, 9.0, 6.5, generalist_verdict="VETO")
        )
        assert result.final_verdict == "REJECTED"
        assert "Generalist" in result.reason

    def test_multiple_vetos_exibe_todos(self):
        """Múltiplos vetos devem aparecer no reason."""
        result = compute_final_verdict(
            _council(6.5, 6.5, 6.5,
                     architect_verdict="VETO",
                     generalist_verdict="VETO")
        )
        assert result.final_verdict == "REJECTED"
        assert "Architect" in result.reason
        assert "Generalist" in result.reason

    def test_empty_responses_rejected(self):
        """Lista vazia deve retornar REJECTED com reason."""
        result = compute_final_verdict([])
        assert result.final_verdict == "REJECTED"
        assert result.average_score == 0.0
        assert len(result.reason) > 0


# ─────────────────────────────────────────
# Tipo e imutabilidade do retorno
# ─────────────────────────────────────────

class TestReturnType:
    def test_returns_verdict_result(self):
        """compute_final_verdict deve retornar VerdictResult."""
        result = compute_final_verdict(_council())
        assert isinstance(result, VerdictResult)

    def test_verdict_result_is_frozen(self):
        """VerdictResult deve ser imutável (frozen dataclass)."""
        result = compute_final_verdict(_council())
        with pytest.raises((AttributeError, TypeError)):
            result.final_verdict = "APPROVED"  # type: ignore

    def test_reason_is_non_empty_string(self):
        """reason nunca deve ser None ou vazio."""
        for scores in [(8.0, 8.0, 8.0), (6.0, 6.0, 6.0)]:
            result = compute_final_verdict(
                _council(*scores)
            )
            assert isinstance(result.reason, str)
            assert len(result.reason.strip()) > 0

    def test_average_score_precision(self):
        """average_score deve ter até 2 casas decimais."""
        result = compute_final_verdict(_council(7.1, 8.3, 9.2))
        # 7.1 + 8.3 + 9.2 = 24.6 / 3 = 8.2
        assert result.average_score == round((7.1 + 8.3 + 9.2) / 3, 2)


# ─────────────────────────────────────────
# Constantes dos limiares
# ─────────────────────────────────────────

class TestThresholdConstants:
    def test_approval_threshold_is_75(self):
        """Limiar de aprovação deve ser 7.5 (v3.0)."""
        assert APPROVAL_SCORE_THRESHOLD == 7.5

    def test_security_threshold_is_60(self):
        """Limiar do SecurityCoder deve ser 6.0 (v3.0)."""
        assert SECURITY_SCORE_THRESHOLD == 6.0