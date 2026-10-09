"""
Testes do ImprovePlanner + ImprovePatcher + ImproveQualityRunner (v5.4.0).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from backend.core.improve.patcher import ImprovePatcher, ImproveQualityRunner
from backend.core.improve.planner import ImprovePlanner
from backend.domain.improve import (
    ImproveDiagnosis,
    ImprovePlanItem,
    ImproveRequest,
)


def _diag(**kw: Any) -> ImproveDiagnosis:
    base: dict[str, Any] = {
        "summary": "diag",
        "top_issues": [],
        "leveraged_learnings": [],
        "leveraged_artifacts": [],
        "risk_level": "low",
    }
    base.update(kw)
    return ImproveDiagnosis(**base)


def _req(**kw: Any) -> ImproveRequest:
    base: dict[str, Any] = {"project_id": "p-1"}
    base.update(kw)
    return ImproveRequest(**base)


class _Gen:
    """Generator stub: retorna propostas fixas por item."""

    def __init__(self, proposals: list[dict[str, str]]) -> None:
        self._proposals = proposals
        self.i = 0

    def generate(self, item: ImprovePlanItem, bundle: dict[str, str]) -> dict[str, str]:
        p = self._proposals[self.i % len(self._proposals)]
        self.i += 1
        return p


class _Gate:
    def __init__(self, passed: bool = True) -> None:
        self.passed = passed

    def run(self, files: dict[str, str]) -> Any:
        return SimpleNamespace(passed=self.passed, summary="gate")


class _TDD:
    def __init__(self, results: list[bool]) -> None:
        self._results = results
        self.calls = 0

    async def run(self, request: Any) -> Any:
        self.calls += 1
        ok = self._results[min(self.calls - 1, len(self._results) - 1)]
        return SimpleNamespace(success=ok, escalated=False, summary="tdd")


# ─────────────────────────────────────────────────────────────
# Planner
# ─────────────────────────────────────────────────────────────

def test_planner_gera_1_a_7_itens() -> None:
    diag = _diag(top_issues=[f"QA: defeito {i}" for i in range(10)], risk_level="medium")
    plan = ImprovePlanner().plan(diag, _req())
    assert 1 <= len(plan.items) <= 7


def test_planner_confirma_quando_risco_medium_mesmo_sem_flag() -> None:
    diag = _diag(top_issues=["QA: timeout"], risk_level="medium")
    plan = ImprovePlanner().plan(diag, _req(require_human_confirmation=False))
    assert plan.requires_confirmation is True
    assert plan.overall_risk == "medium"


def test_planner_sem_confirma_quando_low_e_flag_false() -> None:
    diag = _diag(risk_level="low")
    plan = ImprovePlanner().plan(diag, _req(require_human_confirmation=False))
    assert plan.requires_confirmation is False
    assert plan.overall_risk == "low"


def test_planner_overall_risk_herda_diagnostico_high() -> None:
    diag = _diag(top_issues=["Gap de goal: x"], risk_level="high")
    plan = ImprovePlanner().plan(diag, _req())
    assert plan.overall_risk == "high"
    assert plan.requires_confirmation is True


def test_planner_sem_issues_gera_item_preventivo() -> None:
    plan = ImprovePlanner().plan(_diag(), _req())
    assert len(plan.items) == 1
    assert "hardening" in plan.items[0].title.lower()


# ─────────────────────────────────────────────────────────────
# Patcher (travamento de max_files)
# ─────────────────────────────────────────────────────────────

def test_patcher_trava_ao_exceder_max_files() -> None:
    gen = _Gen([{f"file{i}.py": f"conteudo {i}" for i in range(10)}])
    patcher = ImprovePatcher(generator=gen)
    plan = ImprovePlanner().plan(_diag(top_issues=["QA: x"]), _req())
    patch = patcher.generate_patch(plan, current_code_bundle={}, max_files=3)
    assert len(patch) == 3
    assert patcher.truncated is True


def test_patcher_ignora_noop() -> None:
    bundle = {"a.py": "mesmo"}
    gen = _Gen([{"a.py": "mesmo"}])
    patcher = ImprovePatcher(generator=gen)
    plan = ImprovePlanner().plan(_diag(top_issues=["QA: x"]), _req())
    patch = patcher.generate_patch(plan, bundle, max_files=8)
    assert patch == {}
    assert patcher.truncated is False


def test_patcher_aplica_conteudo_novo() -> None:
    gen = _Gen([{"novo.py": "print(1)"}])
    patcher = ImprovePatcher(generator=gen)
    plan = ImprovePlanner().plan(_diag(top_issues=["QA: x"]), _req())
    patch = patcher.generate_patch(plan, {}, max_files=8)
    assert patch == {"novo.py": "print(1)"}


# ─────────────────────────────────────────────────────────────
# Quality Runner (TDDLoop + regressões)
# ─────────────────────────────────────────────────────────────

def test_quality_tdd_sucesso_autoriza() -> None:
    runner = ImproveQualityRunner(static_gate=_Gate(True), tdd_loop=_TDD([True]))
    res = asyncio.run(runner.run({"a.py": "x"}, {"a.py": "old"}, {"t.py": "t"}, goal="g"))
    assert res.passed is True
    assert res.escalated is False
    assert res.attempts == 1


def test_quality_tdd_recupera_no_retry() -> None:
    tdd = _TDD([False, True])
    runner = ImproveQualityRunner(static_gate=_Gate(True), tdd_loop=tdd)
    res = asyncio.run(runner.run({}, {"a.py": "x"}, {"t.py": "t"}, goal="g", max_retries=2))
    assert res.passed is True
    assert res.escalated is False
    assert tdd.calls == 2


def test_quality_tdd_falha_apos_retries_escala() -> None:
    tdd = _TDD([False])
    runner = ImproveQualityRunner(static_gate=_Gate(True), tdd_loop=tdd)
    res = asyncio.run(runner.run({}, {"a.py": "x"}, {"t.py": "t"}, goal="g", max_retries=2))
    assert res.passed is False
    assert res.escalated is True
    assert "3 tentativa(s)" in res.reason
    assert tdd.calls == 3


def test_quality_static_gate_reprova_sem_escalar() -> None:
    runner = ImproveQualityRunner(static_gate=_Gate(False), tdd_loop=_TDD([True]))
    res = asyncio.run(runner.run({}, {"a.py": "x"}, {"t.py": "t"}, goal="g"))
    assert res.passed is False
    assert res.escalated is False
    assert "Static gate" in res.reason