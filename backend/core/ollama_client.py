"""
Cliente para comunicação com Ollama (modelos locais).
"""

import httpx
from typing import AsyncGenerator

from backend.core.config import settings


class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str = "",
        stream: bool = False,
    ) -> str:
        """Gera uma resposta do modelo."""
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_ctx": 8192,
            },
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["response"]

    async def stream_generate(
        self,
        model: str,
        prompt: str,
        system: str = "",
    ) -> AsyncGenerator[str, None]:
        """Gera uma resposta em streaming."""
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
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