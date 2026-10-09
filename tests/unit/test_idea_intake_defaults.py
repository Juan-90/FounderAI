"""
Regressão v5.5.2: IdeaIntakeAgent tolera clarified_fields omitido pela LLM.
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.validate.agents import IdeaIntakeAgent


class _FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        return self._payload

    async def complete(self, system_prompt, user_prompt, model=None, role=None):
        return ""


def test_idea_intake_tolera_clarified_fields_omitido() -> None:
    agent = IdeaIntakeAgent(client=_FakeClient({"summary": "App de agendamento"}))
    out = asyncio.run(agent.analyze({"idea_text": "agendamento"}))
    assert out["summary"] == "App de agendamento"
    assert out["clarified_fields"] == {}      # default seguro, sem exceção
    assert out["assumptions"] == []
    assert out["gaps"] == []


def test_idea_intake_preserva_clarified_fields_valido() -> None:
    payload = {
        "summary": "S", "assumptions": ["a"], "gaps": ["g"],
        "clarified_fields": {"name": "X", "problem": "dor"},
    }
    agent = IdeaIntakeAgent(client=_FakeClient(payload))
    out = asyncio.run(agent.analyze({"idea_text": "x"}))
    assert out["clarified_fields"] == {"name": "X", "problem": "dor"}


def test_idea_intake_clarified_fields_invalido_vira_dict() -> None:
    agent = IdeaIntakeAgent(client=_FakeClient(
        {"summary": "S", "clarified_fields": "não-é-dict"}))
    out = asyncio.run(agent.analyze({"idea_text": "x"}))
    assert out["clarified_fields"] == {}