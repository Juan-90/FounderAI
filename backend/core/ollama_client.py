"""
Cliente para comunicação com Ollama (modelos locais).
"""

import json
from typing import AsyncGenerator

import httpx

from backend.core.config import settings


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str = "",
    ) -> str:
        """
        Gera uma resposta via streaming e acumula o resultado.
        Usar streaming evita disconnects em respostas longas (ex: Qwen3 14B).
        """
        tokens: list[str] = []
        async for token in self._stream(model=model, prompt=prompt, system=system):
            tokens.append(token)
        return "".join(tokens)

    async def _stream(
        self,
        model: str,
        prompt: str,
        system: str = "",
    ) -> AsyncGenerator[str, None]:
        """Stream interno — consome tokens linha a linha."""
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": True,
            "options": {
                "temperature": 0.3,
                "num_ctx": 8192,
            },
        }

        async with httpx.AsyncClient(timeout=900.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data: dict = json.loads(line)
                    if token := data.get("response"):
                        yield token
                    if data.get("done"):
                        break

    async def health_check(self) -> bool:
        """Verifica se o Ollama está disponível."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False


# Instância global
ollama = OllamaClient()