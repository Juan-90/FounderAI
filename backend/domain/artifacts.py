"""
ArtifactManager — persistência local de artefatos de missão (v4.2.0).

Estrutura em disco:
    <BUILD_ARTIFACTS_DIR>/<mission_id>/<subfolder>/<name>
    <BUILD_ARTIFACTS_DIR>/<mission_id>/mission_state.json

Segurança: todos os segmentos (mission_id, subfolder, name) são sanitizados
contra path traversal (caminhos absolutos e '..') antes de tocar o disco.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from uuid import uuid4

from backend.core.config import Settings, settings
from backend.domain.models import Artifact, MissionState

_STATE_FILENAME: str = "mission_state.json"


class ArtifactManager:
    """Gerencia a escrita de artefatos e do estado de missão no disco."""

    def __init__(
        self,
        config: Settings | None = None,
        root: Path | None = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._root: Path = (
            root if root is not None else Path(self._config.BUILD_ARTIFACTS_DIR)
        )

    @property
    def root(self) -> Path:
        return self._root

    # ── Sanitização ──
    @staticmethod
    def _safe_segment(value: str, field: str, allow_empty: bool = False) -> str:
        """Bloqueia caminhos absolutos e path traversal por segmento."""
        if value is None or not value.strip():
            if allow_empty:
                return ""
            raise ValueError(f"Segmento '{field}' não pode ser vazio.")
        path = Path(value)
        if path.is_absolute() or any(part == ".." for part in path.parts):
            raise ValueError(
                f"Path traversal bloqueado em '{field}': '{value}'"
            )
        return value

    @staticmethod
    def _infer_type(name: str) -> str:
        suffix = Path(name).suffix.lstrip(".").lower()
        return suffix or "text"

    # ── Interface pública ──
    def save_artifact(
        self,
        mission_id: str,
        name: str,
        content: str,
        subfolder: str = "",
    ) -> Artifact:
        """
        Persiste um artefato em <root>/<mission_id>/<subfolder>/<name>.

        Returns:
            Artifact com path relativo à raiz de artefatos.
        """
        safe_mission = self._safe_segment(mission_id, "mission_id")
        safe_name = self._safe_segment(name, "name")
        safe_sub = self._safe_segment(subfolder, "subfolder", allow_empty=True)

        mission_dir = self._root / safe_mission
        target_dir = mission_dir / safe_sub if safe_sub else mission_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        target = target_dir / safe_name
        target.write_text(content, encoding="utf-8")

        rel = PurePosixPath(
            *target.relative_to(self._root).parts
        )
        return Artifact(
            id=uuid4().hex,
            name=safe_name,
            type=self._infer_type(safe_name),
            path=rel.as_posix(),
            content=content,
        )

    def save_mission_state(self, state: MissionState) -> None:
        """Persiste o estado da missão em <root>/<mission_id>/mission_state.json."""
        safe_mission = self._safe_segment(state.mission_id, "mission_id")
        mission_dir = self._root / safe_mission
        mission_dir.mkdir(parents=True, exist_ok=True)
        target = mission_dir / _STATE_FILENAME
        target.write_text(state.model_dump_json(indent=2), encoding="utf-8")