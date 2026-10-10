"""Regressão v5.5.3: ContrarianRiskAgent nunca falha por skeptic_score."""
from __future__ import annotations
import asyncio
from typing import Any
from backend.validate.agents import ContrarianRiskAgent


class _Fake:
    def __init__(self, payload): self._p = payload
    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        return self._p
    async def complete(self, system_prompt, user_prompt, model=None, role=None):
        return ""


def _base(**over): 
    d = {"regulatory_risks": [], "false_positive_risks": [],
         "hidden_costs": [], "reasons_to_kill": []}
    d.update(over); return d


def test_skeptic_ausente_default():
    out = asyncio.run(ContrarianRiskAgent(client=_Fake(_base())).analyze({}, {}, {}, {}))
    assert out["skeptic_score"] == 5


def test_skeptic_texto_regex():
    out = asyncio.run(ContrarianRiskAgent(client=_Fake(_base(skeptic_score="7/10"))).analyze({}, {}, {}, {}))
    assert out["skeptic_score"] == 7


def test_skeptic_fora_de_range_clamp():
    hi = asyncio.run(ContrarianRiskAgent(client=_Fake(_base(skeptic_score=99))).analyze({}, {}, {}, {}))
    lo = asyncio.run(ContrarianRiskAgent(client=_Fake(_base(skeptic_score=0))).analyze({}, {}, {}, {}))
    assert hi["skeptic_score"] == 10 and lo["skeptic_score"] == 1