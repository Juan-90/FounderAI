"""
Testes unitários do GoldenRunner (v5.0.0 GA) — dispatcher fake, sem LLM/Docker.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.models import MissionState
from backend.golden.pack import get_golden_pack
from backend.golden.runner import GoldenRunner


def _state(status: MissionStatus = MissionStatus.COMPLETED, mid: str | None = None) -> MissionState:
    return MissionState(
        mission_id=mid or uuid.uuid4().hex, project_id="p", mode=ProjectMode.BUILD,
        status=status, current_stage="golden", mode_payload={},
    )


def test_pack_tem_7_missoes_com_modos() -> None:
    pack = get_golden_pack()
    assert len(pack) == 7
    modes = [m.mode for m in pack]
    assert modes.count(ProjectMode.BUILD) == 2
    assert ProjectMode.DISCOVER in modes
    assert ProjectMode.SELF_AUDIT in modes
    g3 = next(m for m in pack if m.id == "G3")
    assert g3.options.get("no_build") is True


def test_golden_runner_todas_passam(tmp_path: Path) -> None:
    runner = GoldenRunner(root=tmp_path, dispatcher=lambda m: _ok_coro())
    report = asyncio.run(runner.run())
    assert report.total == 7
    assert report.success_count == 7
    assert report.all_passed is True
    # consolidação persistida
    assert (tmp_path / report.run_id / "golden_report.md").exists()
    assert (tmp_path / report.run_id / "golden_state.json").exists()
    # por-missão persistido
    first = report.results[0]
    assert (tmp_path / first.mission_id / "mission_state.json").exists()
    assert (tmp_path / first.mission_id / "golden_report.md").exists()


async def _ok_coro() -> MissionState:
    return _state()


def test_golden_runner_falha_parcial_nao_interrompe(tmp_path: Path) -> None:
    calls = {"n": 0}

    async def dispatch(m):
        calls["n"] += 1
        if m.id == "G6":
            raise RuntimeError("sandbox quebrou")
        return _state()

    runner = GoldenRunner(root=tmp_path, dispatcher=dispatch)
    report = asyncio.run(runner.run())
    assert calls["n"] == 7  # não interrompeu
    assert report.success_count == 6
    assert report.all_passed is False
    g6 = next(r for r in report.results if r.id == "G6")
    assert g6.success is False
    assert "sandbox quebrou" in (g6.error or "")
    # missão falha também persiste mission_state
    assert (tmp_path / g6.mission_id / "mission_state.json").exists()