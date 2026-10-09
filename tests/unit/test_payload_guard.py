"""
Testes das guardas defensivas de payload (v5.5.2).
"""

from __future__ import annotations

from backend.utils.payload_guard import (
    DEFAULT_ARCHITECT_SYSTEM_PROMPT,
    require_clarified_fields,
    require_list,
    require_str,
    safe_system_prompt,
)


def test_safe_system_prompt_com_dict_valido() -> None:
    assert safe_system_prompt({"system_prompt": "Você é o Architect."}) == "Você é o Architect."


def test_safe_system_prompt_sem_chave_nao_levanta_keyerror() -> None:
    # Regressão v5.5.2: KeyError: 'system_prompt'
    assert safe_system_prompt({}) == DEFAULT_ARCHITECT_SYSTEM_PROMPT
    assert safe_system_prompt({"other": 1}) == DEFAULT_ARCHITECT_SYSTEM_PROMPT


def test_safe_system_prompt_com_none_ou_vazio() -> None:
    assert safe_system_prompt({"system_prompt": None}) == DEFAULT_ARCHITECT_SYSTEM_PROMPT
    assert safe_system_prompt({"system_prompt": "   "}) == DEFAULT_ARCHITECT_SYSTEM_PROMPT
    assert safe_system_prompt(None) == DEFAULT_ARCHITECT_SYSTEM_PROMPT


def test_safe_system_prompt_string_directa() -> None:
    assert safe_system_prompt("prompt direto") == "prompt direto"


def test_require_clarified_fields_omitido() -> None:
    # Regressão v5.5.2: ValidateAgentError por clarified_fields ausente
    assert require_clarified_fields({"summary": "x"}) == {}


def test_require_clarified_fields_valido() -> None:
    assert require_clarified_fields({"clarified_fields": {"name": "A"}}) == {"name": "A"}


def test_require_clarified_fields_invalido_vira_dict() -> None:
    assert require_clarified_fields({"clarified_fields": "não-é-dict"}) == {}
    assert require_clarified_fields({"clarified_fields": None}) == {}


def test_require_list_e_str() -> None:
    assert require_list({"gaps": ["a"]}, "gaps") == ["a"]
    assert require_list({}, "gaps") == []
    assert require_str({"summary": "ok"}, "summary") == "ok"
    assert require_str({}, "summary", default="vazio") == "vazio"