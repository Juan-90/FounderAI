"""
Prompt Loader — Carrega System Prompts a partir de arquivos externos.
Módulo C2: Prompts versionados em backend/prompts/ para evitar diluição de papéis.
"""

from __future__ import annotations

from pathlib import Path

# Diretório base dos prompts — relativo a este arquivo
_PROMPTS_DIR: Path = Path(__file__).parent.parent / "prompts"

# Mapeamento jurado → arquivo de prompt (versionado)
_PROMPT_FILES: dict[str, str] = {
    "Architect":     "architect_v3.txt",
    "SecurityCoder": "security_coder_v3.txt",
    "Generalist":    "generalist_v3.txt",
}

# Fallbacks mínimos — usados apenas se o arquivo não for encontrado
_FALLBACK_PROMPTS: dict[str, str] = {
    "Architect": (
        "Você é o Architect do Conselho Consultivo do FounderAI. "
        "Avalie exclusivamente a viabilidade técnica da missão. "
        "Responda APENAS no formato JSON especificado."
    ),
    "SecurityCoder": (
        "Você é o SecurityCoder do Conselho Consultivo do FounderAI. "
        "Avalie exclusivamente segurança, privacidade e compliance (LGPD). "
        "Você tem poder de VETO ABSOLUTO. "
        "Responda APENAS no formato JSON especificado."
    ),
    "Generalist": (
        "Você é o Generalist do Conselho Consultivo do FounderAI. "
        "Avalie exclusivamente viabilidade de mercado e modelo de negócio. "
        "Responda APENAS no formato JSON especificado."
    ),
}

import sys

def load_prompt(juror_name: str) -> str:
    """
    Carrega o System Prompt de um jurado a partir do arquivo externo.

    Ordem de resolução:
      1. Arquivo em backend/prompts/<juror_file>.txt
      2. Fallback hardcoded mínimo (com aviso em stderr)
      3. RuntimeError se o jurado não for reconhecido

    Args:
        juror_name: Nome exato do jurado (ex: "Architect").

    Returns:
        Conteúdo do System Prompt como string.

    Raises:
        RuntimeError: Se juror_name não estiver mapeado.
    """
    if juror_name not in _PROMPT_FILES:
        raise RuntimeError(
            f"Jurado '{juror_name}' não reconhecido. "
            f"Jurados válidos: {list(_PROMPT_FILES.keys())}"
        )

    prompt_path: Path = _PROMPTS_DIR / _PROMPT_FILES[juror_name]

    if prompt_path.exists():
        try:
            return prompt_path.read_text(encoding="utf-8").strip()
        except OSError as e:
            
            print(
                f"[WARN] Falha ao ler prompt de '{prompt_path}': {e}. "
                "Usando fallback.",
                file=sys.stderr,
            )

    # Fallback caso o arquivo não exista ou ocorra erro na leitura/decodificação
    return _FALLBACK_PROMPTS.get(juror_name, "")


def list_available_prompts() -> dict[str, dict[str, str]]:
    """
    Lista todos os prompts e seus status (carregado do arquivo ou fallback).
    Útil para diagnóstico e testes.

    Returns:
        Dict com jurador_name → {file, status, path}
    """
    result: dict[str, dict[str, str]] = {}
    for juror, filename in _PROMPT_FILES.items():
        path = _PROMPTS_DIR / filename
        result[juror] = {
            "file": filename,
            "path": str(path),
            "status": "ok" if path.exists() else "fallback",
        }
    return result