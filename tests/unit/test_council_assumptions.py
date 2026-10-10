"""Regressão v5.5.3: premissas padrão p/ Architect/Security em modo não interativo."""
from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest

from backend.agents import council
from backend.core.config import settings


class _Capture:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.kwargs: dict[str, Any] = {}
        self._p = payload

    async def __call__(self, **kw: Any) -> dict[str, Any]:
        self.kwargs = kw
        return dict(self._p)


def _ok() -> dict[str, Any]:
    return {"score": 8.0, "verdict": "APPROVE", "reasoning": "ok"}


def test_architect_recebe_premissas_quando_ligado(monkeypatch: pytest.MonkeyPatch) -> None:
    cap = _Capture(_ok())
    monkeypatch.setattr(council, "call_ollama_json", cap)
    monkeypatch.setattr(settings, "COUNCIL_ASSUME_DEFAULTS", True)
    asyncio.run(council._evaluate_juror({"name": "Architect"}, "missão"))
    assert "PREMISSAS PADRÃO" in cap.kwargs["user_prompt"]


def test_generalist_nao_recebe_premissas(monkeypatch: pytest.MonkeyPatch) -> None:
    cap = _Capture(_ok())
    monkeypatch.setattr(council, "call_ollama_json", cap)
    monkeypatch.setattr(settings, "COUNCIL_ASSUME_DEFAULTS", True)
    asyncio.run(council._evaluate_juror({"name": "Generalist"}, "missão"))
    assert "PREMISSAS PADRÃO" not in cap.kwargs["user_prompt"]


def test_desligado_em_tty_sem_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    class _TTY:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", _TTY())
    monkeypatch.setattr(settings, "COUNCIL_ASSUME_DEFAULTS", False)
    cap = _Capture(_ok())
    monkeypatch.setattr(council, "call_ollama_json", cap)
    asyncio.run(council._evaluate_juror({"name": "Architect"}, "missão"))
    assert "PREMISSAS PADRÃO" not in cap.kwargs["user_prompt"]