"""
LLM Client — Wrapper assíncrono para o Ollama local.
Usa streaming via /api/generate para evitar ReadTimeout.
Força resposta em JSON estrito compatível com JurorResponse.
"""

import json

import httpx

from backend.core.config import settings


JUROR_JSON_SCHEMA = """
Você DEVE responder APENAS com um objeto JSON válido, sem texto adicional, sem markdown, sem backticks.
O JSON deve seguir EXATAMENTE esta estrutura:
{
  "juror_name": "string",
  "score": 7.5,
  "verdict": "APPROVE",
  "reasoning": "string com máximo 500 caracteres"
}
Valores válidos para verdict: "APPROVE" ou "VETO"
"""


async def call_ollama_json(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> dict:
    """
    Chama o Ollama via /api/generate com streaming.
    Acumula tokens e parseia o JSON ao final.
    Lança ValueError se a resposta não for JSON válido.
    """
    target_model: str = model or settings.council_model

    full_prompt: str = (
        system_prompt
        + "\n\n"
        + JUROR_JSON_SCHEMA
        + "\n\n"
        + user_prompt
    )

    payload: dict = {
        "model": target_model,
        "prompt": full_prompt,
        "stream": True,
        "options": {
            "temperature": 0.2,
            "num_ctx": 2048,
        },
    }

    base_url: str = settings.ollama_base_url.rstrip("/").removesuffix("/v1")
    url: str = f"{base_url}/api/generate"

    tokens: list[str] = []

    async with httpx.AsyncClient(timeout=900.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                data: dict = json.loads(line)
                if token := data.get("response"):
                    tokens.append(token)
                if data.get("done"):
                    break

    raw_content: str = "".join(tokens).strip()

    # Remove possíveis backticks de markdown
    if raw_content.startswith("```"):
        lines = raw_content.splitlines()
        raw_content = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Modelo não retornou JSON válido.\n"
            f"Conteúdo recebido: {raw_content[:300]}\n"
            f"Erro: {e}"
        )