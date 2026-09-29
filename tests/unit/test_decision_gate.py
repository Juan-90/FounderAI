"""
Testes unitários do DecisionGate + schemas VALIDATE_AND_BUILD (v4.5.0).

O gate é puro (sem LLM): todos os casos são determinísticos.
"""

from __future__ import annotations

import pytest

from backend.core.config import Settings
from backend.domain.enums import DeploymentStrategy, ProjectMode, ProjectType
from backend.validate_and_build.gate import DecisionGate
from backend.validate_and_build.schemas import (
    BuildGateDecision,
    BuildSeed,
    ValidateAndBuildRequest,
    ValidationVerdictLiteral,
)


def _cfg(require_human: bool = False, min_conf: float = 0.75) -> Settings:
    return Settings(
        VAB_REQUIRE_HUMAN_CONFIRMATION=require_human,
        VAB_MIN_CONFIDENCE_TO_AUTOBUILD=min_conf,
    )


# ─────────────────────────────────────────────────────────────
# Vereditos que NÃO autorizam build
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("verdict", ["DISCARD", "PIVOT", "INVESTIGATE"])
def test_vereditos_sem_build(verdict: ValidationVerdictLiteral) -> None:
    gate = DecisionGate(_cfg())
    d = gate.evaluate(verdict, confidence=0.9, conditions=[])
    assert isinstance(d, BuildGateDecision)
    assert d.should_build is False
    assert d.needs_human_confirmation is False
    assert d.source_verdict == verdict


# ─────────────────────────────────────────────────────────────
# BUILD — auto-build (sem confirmação)
# ─────────────────────────────────────────────────────────────

def test_build_auto_sem_confirmacao() -> None:
    gate = DecisionGate(_cfg(require_human=False, min_conf=0.75))
    d = gate.evaluate("BUILD", confidence=0.9, conditions=[])
    assert d.should_build is True
    assert d.needs_human_confirmation is False


# ─────────────────────────────────────────────────────────────
# BUILD — requer confirmação humana
# ─────────────────────────────────────────────────────────────

def test_build_com_confirmacao_humana_por_politica() -> None:
    gate = DecisionGate(_cfg(require_human=True, min_conf=0.75))
    d = gate.evaluate("BUILD", confidence=0.95, conditions=[])
    assert d.should_build is True
    assert d.needs_human_confirmation is True


def test_build_com_confianca_abaixo_do_minimo() -> None:
    gate = DecisionGate(_cfg(require_human=False, min_conf=0.75))
    d = gate.evaluate("BUILD", confidence=0.6, conditions=[])
    assert d.should_build is True
    assert d.needs_human_confirmation is True


def test_build_com_condicoes_criticas() -> None:
    gate = DecisionGate(_cfg(require_human=False, min_conf=0.75))
    d = gate.evaluate("BUILD", confidence=0.9, conditions=["validar LGPD"])
    assert d.should_build is True
    assert d.needs_human_confirmation is True
    assert d.conditions == ["validar LGPD"]


def test_override_de_min_confidence_por_chamada() -> None:
    gate = DecisionGate(_cfg(require_human=False, min_conf=0.75))
    d = gate.evaluate("BUILD", confidence=0.6, conditions=[], min_confidence=0.5)
    assert d.should_build is True
    assert d.needs_human_confirmation is False


def test_default_de_config_quando_sem_overrides() -> None:
    # Settings default: VAB_REQUIRE_HUMAN_CONFIRMATION=True
    gate = DecisionGate()
    d = gate.evaluate("BUILD", confidence=0.99, conditions=[])
    assert d.should_build is True
    assert d.needs_human_confirmation is True  # política default exige humano


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────

def test_validate_and_build_request_defaults() -> None:
    req = ValidateAndBuildRequest(idea_text="EcoTrack")
    assert req.auto_build is True
    assert req.require_human_confirmation is True
    assert req.min_confidence_to_autobuild == 0.75
    assert req.deployment_strategy == DeploymentStrategy.PRIVATE
    assert req.context_files == []
    assert req.project_type is None


def test_validate_and_build_request_confianca_fora_do_range() -> None:
    with pytest.raises(Exception):
        ValidateAndBuildRequest(idea_text="x", min_confidence_to_autobuild=1.5)


def test_build_seed_defaults() -> None:
    seed = BuildSeed()
    assert seed.idea_profile == {}
    assert seed.recommended_mvp_scope == []
    assert seed.constraints == []
    assert seed.risks_to_mitigate == []
    assert seed.non_goals == []
    assert seed.suggested_project_type is None


def test_build_seed_com_tipo_sugerido() -> None:
    seed = BuildSeed(
        recommended_mvp_scope=["agendamento"],
        suggested_project_type=ProjectType.WEB_APP,
    )
    assert seed.suggested_project_type == ProjectType.WEB_APP


def test_project_mode_inclui_validate_and_build() -> None:
    assert ProjectMode.VALIDATE_AND_BUILD.value == "VALIDATE_AND_BUILD"