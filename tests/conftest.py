"""
Configuração de testes do FounderAI.

Markers:
  • real_llm: exige LLM funcional (rodar com --run-real-llm).
  • golden:   suíte Golden Missions real (rodar com --run-golden).
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--run-real-llm", action="store_true", default=False,
                     help="Executa testes que exigem LLM real.")
    parser.addoption("--run-golden", action="store_true", default=False,
                     help="Executa a suíte Golden Missions real.")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "real_llm: exige LLM real (--run-real-llm)")
    config.addinivalue_line("markers", "golden: suíte Golden Missions real (--run-golden)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_real = config.getoption("--run-real-llm")
    run_golden = config.getoption("--run-golden")
    skip_real = pytest.mark.skip(reason="requer --run-real-llm")
    skip_golden = pytest.mark.skip(reason="requer --run-golden")
    for item in items:
        if "real_llm" in item.keywords and not run_real:
            item.add_marker(skip_real)
        if "golden" in item.keywords and not run_golden:
            item.add_marker(skip_golden)