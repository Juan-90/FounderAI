"""
Rotinas de limpeza (v5.5.4).

clean_all(): remove arquivos temporários e de build em artifacts/,
e reseta o contador de eventos/learnings em memory.json (mantém a estrutura
do projeto p/ não quebrar histórico de decisões).

Retorna um CleanReport com contagens p/ o CLI renderizar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.core.config import Settings, settings


@dataclass
class CleanReport:
    files_removed: int = 0
    dirs_removed: int = 0
    memories_reset: int = 0
    warnings: list[str] = field(default_factory=list)


_CLEANABLE_EXTENSIONS = (
    ".py", ".js", ".ts", ".json", ".md", ".html", ".css",
    ".log", ".tmp", ".zip", ".pyc",
)
_CLEANABLE_DIRS = ("build", "dist", "node_modules", "__pycache__", ".pytest_cache")


def _iter_cleanable(roots: list[Path]) -> tuple[list[Path], list[Path]]:
    """Retorna (arquivos_a_remover, diretorios_a_remover)."""
    files: list[Path] = []
    dirs: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in _CLEANABLE_EXTENSIONS:
                # preserva memory.json (é histórico, não build)
                if p.name == "memory.json":
                    continue
                files.append(p)
            elif p.is_dir() and p.name in _CLEANABLE_DIRS:
                dirs.append(p)
    return files, dirs


def _reset_memory_counters(memory_file: Path) -> bool:
    """Zera events/learnings/artifact_versions de um memory.json (preserva id/goal)."""
    try:
        data = json.loads(memory_file.read_text(encoding="utf-8"))
        changed = False
        for key in ("events", "learnings", "artifact_versions"):
            if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                data[key] = []
                changed = True
        if changed:
            memory_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        return changed
    except (OSError, json.JSONDecodeError):
        return False


def clean_all(
    config: Optional[Settings] = None,
    dry_run: bool = False,
) -> CleanReport:
    """Remove arquivos de build em artifacts/ e reseta memórias.

    dry_run=True: apenas conta, não remove nada.
    """
    cfg = config if config is not None else settings
    report = CleanReport()

    # 1 — Raízes a limpar
    roots: list[Path] = []
    for path_str in (
        cfg.DISCOVER_ARTIFACTS_DIR,
        cfg.VALIDATE_ARTIFACTS_DIR,
        cfg.BUILD_ARTIFACTS_DIR,
        cfg.VAB_ARTIFACTS_DIR,
        cfg.SELF_AUDIT_ARTIFACTS_DIR,
        cfg.GOLDEN_ARTIFACTS_DIR,
    ):
        roots.append(Path(path_str))

    files, dirs = _iter_cleanable(roots)

    if not dry_run:
        for f in files:
            try:
                f.unlink()
                report.files_removed += 1
            except OSError as exc:
                report.warnings.append(f"falha ao remover {f}: {exc}")
        for d in dirs:
            try:
                import shutil
                shutil.rmtree(d)
                report.dirs_removed += 1
            except OSError as exc:
                report.warnings.append(f"falha ao remover {d}: {exc}")
    else:
        report.files_removed = len(files)
        report.dirs_removed = len(dirs)

    # 2 — Reset de memory.json (preserva estrutura, zera eventos/learnings)
    projects_dir = Path(cfg.PROJECT_MEMORY_DIR)
    if projects_dir.exists():
        for mem in projects_dir.glob("*/memory.json"):
            if dry_run or _reset_memory_counters(mem):
                report.memories_reset += 1

    return report