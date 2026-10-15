"""
v5.5.7: LLMPatchGenerator usa LLMClient real (ou fake duck-typed) e retorna
dict de patches. O fake satisfaz o Protocol LLMCompleter.
"""
import asyncio
import json

from backend.core.improve.llm_patch_generator import LLMPatchGenerator, _extract_json
from backend.domain.improve import ImprovePlanItem


class _FakeClient:
    """Fake duck-typed que satisfaz o Protocol LLMCompleter."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    async def complete(self, system_prompt, user_prompt, model=None, role=None):
        self.calls += 1
        return self.response


def _item(**over) -> ImprovePlanItem:
    return ImprovePlanItem(
        title="Adicionar validação",
        rationale="evitar entradas inválidas",
        target_files=["main.py"],
        expected_impact="robustez",
        **over,
    )


def test_extrai_json_do_texto_bruto() -> None:
    assert _extract_json('{"files": {"a.py": "x"}}') == {"files": {"a.py": "x"}}
    assert _extract_json('```json\n{"files": {}}\n```') == {"files": {}}
    assert _extract_json("sem json aqui") is None


def test_generator_usa_llmclient_real() -> None:
    fake = _FakeClient(json.dumps({"files": {"main.py": "novo"}}))
    gen = LLMPatchGenerator(client=fake)
    out = gen.generate(_item(), {"main.py": "velho"})
    assert out == {"main.py": "novo"}
    assert fake.calls == 1


def test_generator_retorna_vazio_quando_llm_nao_retorna_json() -> None:
    fake = _FakeClient("desculpe, não consigo gerar código")
    gen = LLMPatchGenerator(client=fake)
    assert gen.generate(_item(), {"main.py": "velho"}) == {}


def test_generator_retorna_vazio_quando_llm_diz_sem_mudanca() -> None:
    fake = _FakeClient(json.dumps({"files": {}}))
    gen = LLMPatchGenerator(client=fake)
    assert gen.generate(_item(), {"main.py": "velho"}) == {}