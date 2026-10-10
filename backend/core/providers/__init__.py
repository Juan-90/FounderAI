"""
Provedores LLM de nuvem (v5.5.4): OpenRouter + Gemini.

Cada provedor é um módulo standalone que implementa o Protocol do LLMClient
(complete / complete_verbose). A factory de registro fica em llm_client.py.
"""

from backend.core.providers.gemini_provider import GeminiProvider
from backend.core.providers.openrouter_provider import OpenRouterProvider

__all__ = ["GeminiProvider", "OpenRouterProvider"]