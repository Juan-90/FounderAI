"""
Suíte Golden Missions real (v5.0.0 GA) — roda apenas com --run-golden.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.golden.runner import GoldenRunner


@pytest.mark.golden
def test_golden_missions_reais(tmp_path: Path) -> None:
    runner = GoldenRunner(root=tmp_path)  # dispatcher real (LLM/Docker)
    report = asyncio.run(runner.run())
    assert report.total == 7
    assert (tmp_path / report.run_id / "golden_report.md").exists()
    # GA exige ecossistema saudável: todas as golden missions passam
    assert report.all_passed, report.summary