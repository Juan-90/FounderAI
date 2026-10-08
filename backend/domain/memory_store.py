"""
Repositório de persistência da Memória de Projeto (v5.3.0).

DiskProjectMemoryStore: implementação em disco com gravação atômica
(write to temp + os.replace) para prevenir corrupção de JSON em falhas.
Estrutura: artifacts/projects/<project_id>/memory.json + versions/<kind>/.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

from backend.domain.enums import DeploymentStrategy, ProjectType
from backend.domain.memory import (
    ArtifactKind,
    ArtifactVersion,
    MemoryDecision,
    MemoryEvent,
    MemoryEventType,
    MemoryLearning,
    ProjectMemory,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


def _checksum(path: Path) -> Optional[str]:
    """SHA256 do arquivo se existir; None caso contrário."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class ProjectMemoryStore(Protocol):
    """Contrato de um repositório de memória de projeto."""

    def get(self, project_id: str) -> Optional[ProjectMemory]: ...
    def create(self, name: str, project_type: Optional[ProjectType] = None,
               deployment_strategy: Optional[DeploymentStrategy] = None) -> ProjectMemory: ...
    def save(self, memory: ProjectMemory) -> None: ...
    def append_event(self, project_id: str, type: MemoryEventType, message: str,
                     mission_id: Optional[str] = None, data: Optional[dict[str, Any]] = None) -> MemoryEvent: ...
    def add_decision(self, project_id: str, title: str, rationale: str,
                     status: str = "accepted", mission_id: Optional[str] = None) -> MemoryDecision: ...
    def add_artifact_version(self, project_id: str, kind: ArtifactKind, path: str,
                             mission_id: Optional[str] = None, summary: Optional[str] = None) -> ArtifactVersion: ...
    def add_learning(self, project_id: str, text: str, source: str,
                     mission_id: Optional[str] = None) -> MemoryLearning: ...
    def latest_artifact(self, project_id: str, kind: ArtifactKind) -> Optional[ArtifactVersion]: ...
    def list_projects(self) -> list[ProjectMemory]: ...


class DiskProjectMemoryStore:
    """Implementação em disco com gravação atômica."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base = Path(base_dir) if base_dir else Path("artifacts/projects")

    def _project_dir(self, project_id: str) -> Path:
        return self._base / project_id

    def _memory_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "memory.json"

    def _atomic_write(self, path: Path, data: str) -> None:
        """Grava data em path de forma atômica (temp + replace)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_text(data, encoding="utf-8")
            os.replace(tmp, path)  # atômico no POSIX e Windows NT+
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise

    def get(self, project_id: str) -> Optional[ProjectMemory]:
        """Carrega a memória do projeto; None se não existir."""
        path = self._memory_file(project_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ProjectMemory.model_validate(data)
        except (json.JSONDecodeError, Exception):
            return None

    def create(
        self,
        name: str,
        project_type: Optional[ProjectType] = None,
        deployment_strategy: Optional[DeploymentStrategy] = None,
    ) -> ProjectMemory:
        """Cria nova memória de projeto e persiste."""
        now = _utcnow()
        memory = ProjectMemory(
            project_id=_new_id(),
            name=name,
            project_type=project_type,
            deployment_strategy=deployment_strategy,
            created_at=now,
            updated_at=now,
        )
        self.save(memory)
        return memory

    def save(self, memory: ProjectMemory) -> None:
        """Persiste a memória completa (gravação atômica)."""
        memory.updated_at = _utcnow()
        path = self._memory_file(memory.project_id)
        data = memory.model_dump_json(indent=2)
        self._atomic_write(path, data)

    def append_event(
        self,
        project_id: str,
        type: MemoryEventType,
        message: str,
        mission_id: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> MemoryEvent:
        """Adiciona evento à linha do tempo e persiste."""
        memory = self.get(project_id)
        if memory is None:
            raise ValueError(f"Projeto {project_id} não encontrado")
        event = MemoryEvent(
            event_id=_new_id(),
            type=type,
            mission_id=mission_id,
            message=message,
            data=data or {},
            created_at=_utcnow(),
        )
        memory.events.append(event)
        self.save(memory)
        return event

    def add_decision(
        self,
        project_id: str,
        title: str,
        rationale: str,
        status: str = "accepted",
        mission_id: Optional[str] = None,
    ) -> MemoryDecision:
        """Adiciona decisão e persiste."""
        memory = self.get(project_id)
        if memory is None:
            raise ValueError(f"Projeto {project_id} não encontrado")
        decision = MemoryDecision(
            decision_id=_new_id(),
            title=title,
            rationale=rationale,
            status=status,  # type: ignore[arg-type]
            mission_id=mission_id,
            created_at=_utcnow(),
        )
        memory.decisions.append(decision)
        self.save(memory)
        return decision

    def add_artifact_version(
        self,
        project_id: str,
        kind: ArtifactKind,
        path: str,
        mission_id: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> ArtifactVersion:
        """Adiciona versão de artefato (calcula checksum se arquivo existir)."""
        memory = self.get(project_id)
        if memory is None:
            raise ValueError(f"Projeto {project_id} não encontrado")
        artifact_path = Path(path)
        checksum = _checksum(artifact_path)
        version = ArtifactVersion(
            version_id=_new_id(),
            kind=kind,
            path=str(artifact_path),
            checksum=checksum,
            mission_id=mission_id,
            created_at=_utcnow(),
            summary=summary,
        )
        memory.artifact_versions.append(version)
        self.save(memory)
        return version

    def add_learning(
        self,
        project_id: str,
        text: str,
        source: str,
        mission_id: Optional[str] = None,
    ) -> MemoryLearning:
        """Adiciona aprendizado e persiste."""
        memory = self.get(project_id)
        if memory is None:
            raise ValueError(f"Projeto {project_id} não encontrado")
        learning = MemoryLearning(
            learning_id=_new_id(),
            text=text,
            source=source,  # type: ignore[arg-type]
            mission_id=mission_id,
            created_at=_utcnow(),
        )
        memory.learnings.append(learning)
        self.save(memory)
        return learning

    def latest_artifact(
        self, project_id: str, kind: ArtifactKind
    ) -> Optional[ArtifactVersion]:
        """Retorna a versão mais recente de um tipo de artefato."""
        memory = self.get(project_id)
        if memory is None:
            return None
        candidates = [v for v in memory.artifact_versions if v.kind == kind]
        if not candidates:
            return None
        return max(candidates, key=lambda v: v.created_at)

    def list_projects(self) -> list[ProjectMemory]:
        """Lista todos os projetos com memória válida."""
        if not self._base.exists():
            return []
        projects: list[ProjectMemory] = []
        for project_dir in self._base.iterdir():
            if not project_dir.is_dir():
                continue
            memory_file = project_dir / "memory.json"
            if not memory_file.exists():
                continue
            try:
                data = json.loads(memory_file.read_text(encoding="utf-8"))
                memory = ProjectMemory.model_validate(data)
                projects.append(memory)
            except (json.JSONDecodeError, Exception):
                continue
        return projects