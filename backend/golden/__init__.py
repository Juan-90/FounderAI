"""
Golden Missions (v5.0.0 GA) — suíte canônica de validação do ecossistema.
"""

from backend.golden.pack import GoldenMission, get_golden_pack
from backend.golden.runner import GoldenMissionResult, GoldenReport, GoldenRunner

__all__ = [
    "GoldenMission",
    "GoldenMissionResult",
    "GoldenReport",
    "GoldenRunner",
    "get_golden_pack",
]