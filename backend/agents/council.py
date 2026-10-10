"""
Council — Conselho Consultivo Artificial.
Módulo C2: System Prompts carregados de arquivos externos versionados (v3).
Módulo C1: Retry para respostas inconsistentes + fallback seguro.
Módulo C3: Decisão final via compute_final_verdict (limiares v3.0).
v3.5 / Fase 3 Bloco 2+: Observabilidade híbrida retrocompatível
  (call_ollama_json wrapper + seam _get_llm_client).
v5.5.2: system prompt defensivo por jurado (_juror_system_prompt).
v5.5.3: premissas padrão seguras p/ Architect/SecurityCoder em modo não
  interativo (--no-confirm ou stdin não-TTY), evitando VETO por falta de
  detalhe técnico (_assume_defaults + _ASSUMPTION_BLOCK).
"""

from __future__ import annotations

import json
import sys
from typing import List

from pydantic import ValidationError
from rich.console import Console

from backend.core.config import settings
from backend.core.llm_client import (
    LLMClient,
    LLMErrorKind,
    LLMProviderError,
    OllamaInvalidResponseError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    _clean_json,
)
from backend.core.prompt_loader import load_prompt
from backend.core.verdict import compute_final_verdict
from backend.schemas.council import CouncilDecision, JurorResponse, JurorVerdict

console = Console(stderr=True)

# ─────────────────────────────────────────
# Fallback seguro (Módulo C1)
# ─────────────────────────────────────────

_FALLBACK_SCORE: float = 4.0
_FALLBACK_VERDICT: JurorVerdict = JurorVerdict.VETO
_FALLBACK_REASONING: str = (
    "[FALLBACK] Resposta inconsistente após retry. "
    "Veredito conservador aplicado automaticamente."
)
_FALLBACK_PROVIDER_TAG: str = "fallback-safe"

_FALLBACK_JUROR_SYSTEM: str = (
    "Você é um jurado especialista do FounderAI. Avalie com rigor, "
    "separe fato de inferência e responda APENAS com JSON válido."
)

# v5.5.3 — premissas padrão p/ jurados técnicos em modo não interativo
_ASSUMPTION_BLOCK: str = (
    "\n\nPREMISSAS PADRÃO (modo não interativo / --no-confirm): se faltarem "
    "detalhes técnicos (stack, escala, integrações, ameaças específicas), "
    "ADOTE premissas padrão seguras e conservadoras (ex.: stack web comum, "
    "volume moderado, autenticação padrão, OWASP top-10) e liste-as brevemente "
    "no reasoning. NÃO emita VETO apenas por falta de detalhe; reserve VETO "
    "para riscos reais e concretos."
)

_TECHNICAL_JURORS = ("Architect", "SecurityCoder")


def _assume_defaults() -> bool:
    """True se --no-confirm (config) ou stdin não-TTY (não interativo)."""
    return bool(settings.COUNCIL_ASSUME_DEFAULTS) or not sys.stdin.isatty()


# ─────────────────────────────────────────
# Definição dos Jurados (Módulo C2)
# ─────────────────────────────────────────

JURORS: List[dict] = [
    {"name": "Architect"},
    {"name": "SecurityCoder"},
    {"name": "Generalist"},
]


def _resolve_jurors() -> List[dict]:
    return [
        {"name": j["name"], "system_prompt": load_prompt(j["name"])}
        for j in JURORS
    ]


def _juror_system_prompt(juror: dict) -> str:
    """System prompt defensivo (v5.5.2): dict -> load_prompt(name) -> fallback."""
    existing = juror.get("system_prompt")
    if isinstance(existing, str) and existing.strip():
        return existing
    try:
        loaded = load_prompt(juror["name"])
        if isinstance(loaded, str) and loaded.strip():
            return loaded
    except Exception:
        pass
    return _FALLBACK_JUROR_SYSTEM


# ─────────────────────────────────────────
# Seam de cliente (Fase 3 Bloco 2)
# ─────────────────────────────────────────

def _get_llm_client() -> LLMClient:
    return LLMClient()


# ─────────────────────────────────────────
# Wrapper híbrido retrocompatível (Fase 3 Bloco 2+)
# ─────────────────────────────────────────

async def call_ollama_json(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    *,
    role: str | None = None,
) -> dict:
    client = _get_llm_client()
    result = await client.complete_verbose(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        role=role,
    )

    cleaned = _clean_json(result.content)
    try:
        parsed: dict = json.loads(cleaned)
    except json.JSONDecodeError:
        raise LLMProviderError(
            f"Modelo não retornou JSON válido.\nConteúdo recebido: {cleaned[:200]}",
            kind=LLMErrorKind.INVALID_JSON,
        ) from None
    if not isinstance(parsed, dict):
        raise LLMProviderError(
            f"JSON retornado não é um objeto: {cleaned[:200]}",
            kind=LLMErrorKind.INVALID_JSON,
        )

    parsed["provider_used"] = result.provider_used
    parsed["model_used"] = result.model_used
    parsed["fallback_triggered"] = result.fallback_triggered
    parsed["original_provider"] = result.original_provider
    return parsed


# ─────────────────────────────────────────
# Prompt de correção para retry (Módulo C1)
# ─────────────────────────────────────────

def _correction_prompt(juror_name: str, raw: dict, error_msg: str) -> str:
    return (
        f"Sua resposta anterior foi rejeitada por inconsistência:\n"
        f"  score={raw.get('score')} | verdict={raw.get('verdict')}\n"
        f"  Motivo: {error_msg}\n\n"
        f"Regras obrigatórias:\n"
        f"  - Se verdict=VETO, o score DEVE ser menor que 7.0\n"
        f"  - Se verdict=APPROVE, o score DEVE ser maior ou igual a 5.0\n\n"
        f"Corrija e retorne um JSON válido para {juror_name}."
    )


# ─────────────────────────────────────────
# Avaliação individual com retry (C1) + observabilidade (Bloco 2)
# ─────────────────────────────────────────

async def _evaluate_juror(
    juror: dict,
    mission: str,
    context_block: str = "",
) -> JurorResponse:
    context_section = f"\n{context_block}" if context_block else ""
    system_prompt = _juror_system_prompt(juror)  # v5.5.2: nunca KeyError

    user_prompt: str = (
        f"Avalie a seguinte missão como {juror['name']}:\n\n"
        f"MISSÃO: {mission}"
        f"{context_section}\n\n"
        f"Responda com seu score (1.0-10.0), veredicto (APPROVE ou VETO) "
        f"e justificativa (máximo 500 caracteres).\n"
        f"Seu juror_name deve ser exatamente: {juror['name']}"
    )

    # v5.5.3: premissas padrão p/ jurados técnicos em modo não interativo
    if juror["name"] in _TECHNICAL_JURORS and _assume_defaults():
        user_prompt += _ASSUMPTION_BLOCK

    role = juror["name"]

    # ── Tentativa 1 ──
    raw: dict = {}
    first_error: str = ""

    try:
        raw = await call_ollama_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=settings.council_model,
            role=role,
        )
    except (LLMProviderError, OllamaUnavailableError,
            OllamaTimeoutError, OllamaInvalidResponseError) as e:
        raise RuntimeError(f"[{juror['name']}] {e}") from e

    raw["juror_name"] = juror["name"]
    if isinstance(raw.get("reasoning"), str) and len(raw["reasoning"]) > 500:
        raw["reasoning"] = raw["reasoning"][:497] + "..."

    try:
        return JurorResponse(**raw)
    except (ValidationError, Exception) as e:
        first_error = str(e)

    # ── Retry ─
    console.print(
        f"[bold yellow][WARNING][/bold yellow] Resposta inconsistente para "
        f"[bold]{juror['name']}[/bold]. Executando retry..."
    )

    try:
        raw_retry: dict = await call_ollama_json(
            system_prompt=system_prompt,
            user_prompt=_correction_prompt(juror["name"], raw, first_error),
            model=settings.council_model,
            role=role,
        )
        raw_retry["juror_name"] = juror["name"]
        if isinstance(raw_retry.get("reasoning"), str) and len(raw_retry["reasoning"]) > 500:
            raw_retry["reasoning"] = raw_retry["reasoning"][:497] + "..."
        return JurorResponse(**raw_retry)

    except Exception as retry_err:
        console.print(
            f"[bold red][FALLBACK][/bold red] Retry falhou para "
            f"[bold]{juror['name']}[/bold]: {retry_err}\n"
            f"  Aplicando: VETO / score={_FALLBACK_SCORE}"
        )
        return JurorResponse(
            juror_name=juror["name"],
            score=_FALLBACK_SCORE,
            verdict=_FALLBACK_VERDICT,
            reasoning=_FALLBACK_REASONING,
            provider_used=_FALLBACK_PROVIDER_TAG,
            model_used=_FALLBACK_PROVIDER_TAG,
            fallback_triggered=False,
            original_provider=None,
        )


# ─────────────────────────────────────────
# Orquestrador principal
# ─────────────────────────────────────────

async def run_council(
    mission: str,
    context_files: list[str] | None = None,
) -> CouncilDecision:
    context_block: str = ""
    if context_files:
        from backend.tools.file_tools import build_context_block
        context_block = build_context_block(context_files)

    resolved_jurors = _resolve_jurors()
    responses: List[JurorResponse] = []

    for juror in resolved_jurors:
        print(f"  🧑‍️  Jurado [{juror['name']}] avaliando...")
        response = await _evaluate_juror(juror, mission, context_block)
        responses.append(response)
        print(f"     Score: {response.score:.1f} | Veredicto: {response.verdict.value}")

    result = compute_final_verdict(responses)

    return CouncilDecision(
        mission=mission,
        final_verdict=result.final_verdict,
        average_score=result.average_score,
        reason=result.reason,
        juror_responses=responses,
    )