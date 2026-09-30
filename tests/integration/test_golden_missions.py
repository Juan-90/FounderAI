"""
Suíte de integração das Golden Missions (v5.0.0 GA).

• Bateria CI (dispatcher fake): roda sem LLM/Docker, valida as 7 missões,
  todos os mission_state.json e a consolidação — sem regressões.
• Bateria real (@pytest.mark.golden): só com --run-golden.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from backend.domain.enums import MissionStatus
from backend.domain.models import MissionState
from backend.golden.pack import get_golden_pack
from backend.golden.runner import GoldenRunner


async def _fake_dispatch(m) -> MissionState:
    return MissionState(
        mission_id=uuid.uuid4().hex, project_id="p", mode=m.mode,
        status=MissionStatus.COMPLETED, current_stage="golden",
        mode_payload={"golden_id": m.id},
    )


def test_golden_bateria_completa_sem_regressao(tmp_path: Path) -> None:
    runner = GoldenRunner(root=tmp_path, dispatcher=_fake_dispatch)
    report = asyncio.run(runner.run())

    assert report.total == 7
    assert report.success_count == 7
    assert report.all_passed is True

    # Cada missão persiste seu mission_state.json + golden_report.md
    for r in report.results:
        assert (tmp_path / r.mission_id / "mission_state.json").exists()
        assert (tmp_path / r.mission_id / "golden_report.md").exists()

    # Consolidação da bateria
    assert (tmp_path / report.run_id / "golden_report.md").exists()
    assert (tmp_path / report.run_id / "golden_state.json").exists()

    ids = {r.id for r in report.results}
    assert ids == {m.id for m in get_golden_pack()}


@pytest.mark.golden
def test_golden_missions_reais(tmp_path: Path) -> None:
    runner = GoldenRunner(root=tmp_path)  # dispatcher real (LLM/Docker)
    report = asyncio.run(runner.run())
    assert report.total == 7
    assert (tmp_path / report.run_id / "golden_report.md").exists()
    assert report.all_passed, report.summary