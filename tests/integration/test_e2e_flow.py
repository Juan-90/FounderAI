"""
Testes E2E do fluxo completo do FounderAI v3.5 (Fase 3 — 3.5).

Cobre os 5 fluxos exigidos no Bloco Final:
  1. E2E Direto:            Turno 0 → veredito FINAL sem esclarecimento;
  2. E2E Dois Turnos:       PENDING_CLARIFICATION → resposta → Turno 1 → FINAL;
  3. E2E Cancelamento:      PENDING_CLARIFICATION → cancel → CANCELLED;
  4. Injeção Multi-arquivo: incluídos / truncados / omitidos via ContextPayload;
  5. Fallback Cloud→Local:  HTTP 500 no Groq → Ollama local, com metadados
                            de observabilidade íntegros no JurorResponse.

Técnica: máquina de estados real (backend.core.council) + seam
`backend.agents.council._get_llm_client` com httpx.MockTransport (zero I/O real).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from backend.agents import council as agents_council
from backend.core import context as context_module
from backend.core.context import prepare_context_payload
from backend.core.council import (
    cancel_deliberation,
    process_founder_reply,
    process_turn0,
)
from backend.core.config import Settings
from backend.core.llm_client import LLMClient
from backend.schemas.council import JurorResponse, JurorVerdict


# ─────────────────────────────────────────────────────────────
# Fábricas de respostas de jurado
# ─────────────────────────────────────────────────────────────

def _juror(
    name: str,
    score: float,
    reasoning: str,
    verdict: JurorVerdict = JurorVerdict.APPROVE,
) -> JurorResponse:
    return JurorResponse(
        juror_name=name,
        score=score,
        verdict=verdict,
        reasoning=reasoning,
    )


def _clear_responses() -> list[JurorResponse]:
    """Reasonings sem palavras-gatilho de esclarecimento + scores aprováveis."""
    return [
        _juror("Architect", 8.5, "Arquitetura coerente e viável tecnicamente."),
        _juror("SecurityCoder", 8.0, "Sem riscos críticos de segurança identificados."),
        _juror("Generalist", 9.0, "Mercado claro com proposta de valor sólida."),
    ]


def _uncertain_responses() -> list[JurorResponse]:
    """Ao menos um reasoning com gatilho ('depende'/'preciso saber') → Turno 0 pendente."""
    return [
        _juror("Architect", 7.5, "Escopo técnico razoável para um MVP inicial."),
        _juror("SecurityCoder", 7.0, "Controles básicos suficientes nesta etapa."),
        _juror(
            "Generalist",
            6.5,
            "O modelo de receita depende do segmento; preciso saber o público-alvo.",
        ),
    ]


def _make_settings() -> Settings:
    return Settings(
        PRIMARY_PROVIDER="groq",
        FALLBACK_PROVIDER="local",
        LLM_TIMEOUT_SECONDS=5.0,
        GROQ_API_KEY="groq-test-key",
        OPENROUTER_API_KEY="or-test-key",
        OPENAI_API_KEY="oa-test-key",
    )


# ─────────────────────────────────────────────────────────────
# 1) E2E Direto — Turno 0 → FINAL
# ─────────────────────────────────────────────────────────────

def test_e2e_turno0_aprovacao_direta() -> None:
    """Missão clara: veredito final direto no Turno 0, sem esclarecimento."""
    state = process_turn0(
        "Criar um app de controle financeiro para MEIs com mensalidade de R$ 30.",
        _clear_responses(),
    )
    assert state.status == "FINAL"
    assert state.clarification is None
    assert state.final_decision is not None
    assert state.final_decision.verdict == "APPROVED"
    assert state.final_decision.average_score == 8.5


# ─────────────────────────────────────────────────────────────
# 2) E2E Dois Turnos — PENDING → resposta → FINAL
# ─────────────────────────────────────────────────────────────

def test_e2e_dois_turnos_com_esclarecimento() -> None:
    """Missão ambígua: Turno 0 pendente, fundador responde, Turno 1 finaliza."""
    mission = "Criar uma plataforma para melhorar a vida das pessoas."
    state0 = process_turn0(mission, _uncertain_responses())

    assert state0.status == "PENDING_CLARIFICATION"
    assert state0.clarification is not None
    assert isinstance(state0.clarification.questions, list)
    assert state0.final_decision is None

    reply = "O foco são MEIs; monetização por assinatura mensal de R$ 30."
    final_state = process_founder_reply(state0, reply, _clear_responses())

    assert final_state.status == "FINAL"
    assert final_state.founder_response == reply
    assert final_state.turn1_responses is not None
    assert len(final_state.turn1_responses) == 3
    assert final_state.final_decision is not None
    assert final_state.final_decision.verdict == "APPROVED"


# ─────────────────────────────────────────────────────────────
# 3) E2E Cancelamento — PENDING → CANCELLED
# ─────────────────────────────────────────────────────────────

def test_e2e_cancelamento_pelo_fundador() -> None:
    """Cancelamento gracioso transita o estado para CANCELLED."""
    state0 = process_turn0("Missão qualquer.", _uncertain_responses())
    assert state0.status == "PENDING_CLARIFICATION"

    cancelled = cancel_deliberation(state0, reason="Fundador desistiu da avaliação.")

    assert cancelled.status == "CANCELLED"
    assert cancelled.founder_response == "Fundador desistiu da avaliação."
    assert cancelled.final_decision is None


# ─────────────────────────────────────────────────────────────
# 4) Injeção de múltiplos arquivos (ContextPayload)
# ─────────────────────────────────────────────────────────────

def test_e2e_injecao_multipla_de_arquivos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Válidos incluídos, grandes truncados, excedentes omitidos — sem erro.

    Aritmética determinística (max_file_chars=5000):
      small.md  =    16 chars → incluído intacto      (total 16)
      big.md    = 20000 chars → truncado em 5000+42   (total 5058)
      extra.md  =   500 chars → 5058+500 > 5200 e restante (142) <= 200 → omitido
    """
    monkeypatch.setattr(context_module, "_PROJECT_ROOT", tmp_path)
    (tmp_path / "small.md").write_text("contexto pequeno", encoding="utf-8")
    (tmp_path / "big.md").write_text("x" * 20_000, encoding="utf-8")
    (tmp_path / "extra.md").write_text("e" * 500, encoding="utf-8")

    payload = prepare_context_payload(
        ["small.md", "big.md", "extra.md"],
        max_file_chars=5_000,
        max_total_chars=5_200,
    )

    assert payload.included == ["small.md", "big.md"]
    assert payload.truncated == ["big.md"]
    assert payload.omitted == ["extra.md"]
    assert 5_000 < payload.total_chars <= 5_200
    assert "small.md" in payload.formatted_content
    assert "extra.md" not in payload.formatted_content
    assert payload.summary() == "2 incluído(s), 1 truncado(s), 1 omitido(s)"


# ─────────────────────────────────────────────────────────────
# 5) Fallback Cloud → Local com observabilidade íntegra
# ─────────────────────────────────────────────────────────────

def test_e2e_fallback_cloud_para_local_com_metadados(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 500 no Groq chaveia para Ollama local mantendo resposta e metadados."""
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if request.url.host == "api.groq.com":
            return httpx.Response(500, json={"error": "indisponível"})
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({
                            "score": 8.0,
                            "verdict": "APPROVE",
                            "reasoning": "Análise sólida e consistente.",
                        }),
                    }
                }]
            },
        )

    client = LLMClient(_make_settings(), transport=httpx.MockTransport(handler))
    monkeypatch.setattr(agents_council, "_get_llm_client", lambda: client)

    juror = {"name": "Architect", "system_prompt": "Você é o Architect do conselho."}
    response = asyncio.run(agents_council._evaluate_juror(juror, "Missão X", ""))

    # Resposta íntegra vinda do Local
    assert response.juror_name == "Architect"
    assert response.score == 8.0
    assert response.verdict == JurorVerdict.APPROVE

    # Observabilidade: cadeia Groq (500) → Local
    assert [r.url.host for r in recorded] == ["api.groq.com", "localhost"]
    assert response.provider_used == "local"
    assert response.model_used == "gemma2:2b"
    assert response.fallback_triggered is True
    assert response.original_provider == "groq"