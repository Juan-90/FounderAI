"""
Council — Conselho Consultivo Artificial.
Módulo C2: System Prompts carregados de arquivos externos versionados (v3).
Módulo C1: Retry para respostas inconsistentes + fallback seguro.
Módulo C3: Decisão final via compute_final_verdict (limiares v3.0).
"""

from __future__ import annotations

from typing import List

from pydantic import ValidationError
from rich.console import Console

from backend.core.config import settings
from backend.core.llm_client import (
    LLMProviderError,
    OllamaInvalidResponseError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    call_ollama_json,
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

# ─────────────────────────────────────────
# Definição dos Jurados (Módulo C2)
# ─────────────────────────────────────────

JURORS: List[dict] = [
    {"name": "Architect"},
    {"name": "SecurityCoder"},
    {"name": "Generalist"},
]


def _resolve_jurors() -> List[dict]:
    """Carrega system_prompts dos arquivos externos em runtime."""
    return [
        {"name": j["name"], "system_prompt": load_prompt(j["name"])}
        for j in JURORS
    ]


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
# Avaliação individual com retry (Módulo C1)
# ─────────────────────────────────────────

async def _evaluate_juror(
    juror: dict,
    mission: str,
    context_block: str = "",
) -> JurorResponse:
    """
    Executa a avaliação de um único jurado.
    Retry em inconsistência → fallback seguro se retry falhar.
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

    # ── Tentativa 1 ──────────────────────────────────────────────────────────
    raw: dict = {}
    first_error: str = ""

    try:
        raw = await call_ollama_json(
            system_prompt=juror["system_prompt"],
            user_prompt=user_prompt,
            model=settings.council_model,
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

    # ── Retry ─────────────────────────────────────────────────────────────────
    console.print(
        f"[bold yellow][WARNING][/bold yellow] Resposta inconsistente para "
        f"[bold]{juror['name']}[/bold]. Executando retry..."
    )

    try:
        raw_retry: dict = await call_ollama_json(
            system_prompt=juror["system_prompt"],
            user_prompt=_correction_prompt(juror["name"], raw, first_error),
            model=settings.council_model,
        )
        raw_retry["juror_name"] = juror["name"]
        if isinstance(raw_retry.get("reasoning"), str) and len(raw_retry["reasoning"]) > 500:
            raw_retry["reasoning"] = raw_retry["reasoning"][:497] + "..."
        return JurorResponse(**raw_retry)

    except Exception as retry_err:
        # ── Fallback seguro ───────────────────────────────────────────────────
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
        )


# ─────────────────────────────────────────
# Orquestrador principal
# ─────────────────────────────────────────

async def run_council(
    mission: str,
    context_files: list[str] | None = None,
) -> CouncilDecision:
    """
    Executa o Conselho Consultivo de forma SEQUENCIAL.
    Decisão final via compute_final_verdict (limiares v3.0).
    """
    context_block: str = ""
    if context_files:
        from backend.tools.file_tools import build_context_block
        context_block = build_context_block(context_files)

    resolved_jurors = _resolve_jurors()
    responses: List[JurorResponse] = []

    for juror in resolved_jurors:
        print(f"  🧑‍⚖️  Jurado [{juror['name']}] avaliando...")
        response = await _evaluate_juror(juror, mission, context_block)
        responses.append(response)
        print(f"     Score: {response.score:.1f} | Veredicto: {response.verdict.value}")

    # ── Decisão final via função pura (Módulo C3) ─────────────────────────────
    result = compute_final_verdict(responses)

    return CouncilDecision(
        mission=mission,
        final_verdict=result.final_verdict,
        average_score=result.average_score,
        reason=result.reason,
        juror_responses=responses,
    )