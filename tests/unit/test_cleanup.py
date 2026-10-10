"""
Testes do módulo cleanup (v5.5.4).
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.cleanup import clean_all
from backend.core.config import Settings


def _cfg(tmp_path: Path) -> Settings:
    return Settings(
        DISCOVER_ARTIFACTS_DIR=str(tmp_path / "discover"),
        VALIDATE_ARTIFACTS_DIR=str(tmp_path / "validate"),
        BUILD_ARTIFACTS_DIR=str(tmp_path / "build"),
        VAB_ARTIFACTS_DIR=str(tmp_path / "vab"),
        SELF_AUDIT_ARTIFACTS_DIR=str(tmp_path / "self_audit"),
        GOLDEN_ARTIFACTS_DIR=str(tmp_path / "golden"),
        PROJECT_MEMORY_DIR=str(tmp_path / "projects"),
    )


def test_clean_remove_artefatos_e_preserva_memory(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    # cria alguns artefatos
    build = tmp_path / "build" / "m1"
    build.mkdir(parents=True)
    (build / "report.md").write_text("r", encoding="utf-8")
    (build / "main.py").write_text("print(1)", encoding="utf-8")
    (build / "__pycache__").mkdir()
    (build / "__pycache__" / "x.pyc").write_text("x", encoding="utf-8")
    # memory.json NÃO deve ser removido
    (tmp_path / "build" / "m1" / "memory.json").write_text("{}", encoding="utf-8")

    report = clean_all(config=cfg, dry_run=False)
    assert report.files_removed >= 2  # report.md + main.py
    assert report.dirs_removed >= 1   # __pycache__
    assert (tmp_path / "build" / "m1" / "memory.json").exists()


def test_clean_reseta_contadores_de_memory(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    projects = tmp_path / "projects" / "p1"
    projects.mkdir(parents=True)
    mem = {"project_id": "p1", "name": "P",
           "events": [{"e": 1}, {"e": 2}],
           "learnings": [{"l": "a"}],
           "artifact_versions": [{"v": 1}],
           "current_goal": "g"}
    (projects / "memory.json").write_text(
        json.dumps(mem, ensure_ascii=False), encoding="utf-8"
    )

    report = clean_all(config=cfg, dry_run=False)
    assert report.memories_reset == 1

    reloaded = json.loads(
        (projects / "memory.json").read_text(encoding="utf-8")
    )
    assert reloaded["events"] == []
    assert reloaded["learnings"] == []
    assert reloaded["artifact_versions"] == []
    assert reloaded["current_goal"] == "g"  # preserva estrutura


def test_clean_dry_run_nao_remove_nada(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    build = tmp_path / "build" / "m1"
    build.mkdir(parents=True)
    f = build / "report.md"
    f.write_text("r", encoding="utf-8")

    report = clean_all(config=cfg, dry_run=True)
    assert report.files_removed == 1
    assert f.exists()  # ainda no disco