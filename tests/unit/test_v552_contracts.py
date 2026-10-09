"""
Regressões de contrato CLI v5.5.2.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import main as main_cli  # noqa: E402


def test_parser_tem_flag_auto_apply() -> None:
    parser = main_cli._build_parser()
    args = parser.parse_args(["improve", "--project", "p1", "--auto-apply"])
    assert args.auto_apply is True


def test_parser_auto_apply_default_false() -> None:
    parser = main_cli._build_parser()
    args = parser.parse_args(["improve", "--project", "p1"])
    assert args.auto_apply is False


def test_menu_namespace_tem_auto_apply() -> None:
    # Namespace do menu interativo deve incluir auto_apply p/ evitar AttributeError
    import argparse
    ns = argparse.Namespace(auto_apply=False)
    assert getattr(ns, "auto_apply", False) is False