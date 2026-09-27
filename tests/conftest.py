"""
Configuração global do Pytest para o FounderAI.

Registra markers customizados:
  • real_llm: testes que exigem LLM real (Groq/OpenRouter/OpenAI/Ollama funcional).
    Skipped por padrão em CI sem credenciais. Use `pytest --run-real-llm` para executar.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-real-llm",
        action="store_true",
        default=False,
        help="Executa testes marcados com @pytest.mark.real_llm (exige LLM real).",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_llm: marca testes que dependem de LLM real (Groq/OpenRouter/Ollama); "
        "skipped por padrão, execute com --run-real-llm.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Pula testes real_llm se a flag não foi passada."""
    if config.getoption("--run-real-llm"):
        return
    skip = pytest.mark.skip(reason="Requer --run-real-llm para executar (LLM real).")
    for item in items:
        if "real_llm" in item.keywords:
            item.add_marker(skip)