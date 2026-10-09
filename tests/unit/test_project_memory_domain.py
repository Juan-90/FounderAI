"""
Testes unitários da Memória de Projeto (v5.3.0).

Cobre: criação, append de eventos, decisões, versionamento com checksum,
gravação atômica e list_projects.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.domain.enums import DeploymentStrategy, ProjectType
from backend.domain.memory import (
    ArtifactKind,
    MemoryEventType,
    ProjectMemory,
)
from backend.domain.memory_store import DiskProjectMemoryStore


def test_create_project_memory(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    memory = store.create(
        name="Barbearia SaaS",
        project_type=ProjectType.WEB_APP,
        deployment_strategy=DeploymentStrategy.PRIVATE,
    )
    assert memory.project_id
    assert memory.name == "Barbearia SaaS"
    assert memory.project_type == ProjectType.WEB_APP
    assert memory.deployment_strategy == DeploymentStrategy.PRIVATE
    assert memory.status == "active"
    assert memory.events == []
    assert memory.decisions == []
    assert memory.artifact_versions == []
    assert memory.learnings == []

    # Persistido em disco
    memory_file = tmp_path / memory.project_id / "memory.json"
    assert memory_file.exists()
    data = json.loads(memory_file.read_text(encoding="utf-8"))
    assert data["name"] == "Barbearia SaaS"


def test_get_project_memory(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    created = store.create(name="Teste")
    loaded = store.get(created.project_id)
    assert loaded is not None
    assert loaded.project_id == created.project_id
    assert loaded.name == created.name


def test_get_nonexistent_returns_none(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    assert store.get("nonexistent-id") is None


def test_append_event(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    memory = store.create(name="Teste")
    event = store.append_event(
        memory.project_id,
        MemoryEventType.BUILD_STARTED,
        "Build iniciado",
        mission_id="m-123",
        data={"stage": "requirements"},
    )
    assert event.event_id
    assert event.type == MemoryEventType.BUILD_STARTED
    assert event.message == "Build iniciado"
    assert event.mission_id == "m-123"
    assert event.data == {"stage": "requirements"}

    # Persistido
    loaded = store.get(memory.project_id)
    assert loaded is not None
    assert len(loaded.events) == 1
    assert loaded.events[0].event_id == event.event_id


def test_add_decision(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    memory = store.create(name="Teste")
    decision = store.add_decision(
        memory.project_id,
        title="Usar FastAPI",
        rationale="Performance e tipagem",
        status="accepted",
        mission_id="m-456",
    )
    assert decision.decision_id
    assert decision.title == "Usar FastAPI"
    assert decision.rationale == "Performance e tipagem"
    assert decision.status == "accepted"
    assert decision.mission_id == "m-456"

    loaded = store.get(memory.project_id)
    assert loaded is not None
    assert len(loaded.decisions) == 1
    assert loaded.decisions[0].decision_id == decision.decision_id


def test_add_artifact_version_with_checksum(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    memory = store.create(name="Teste")

    # Cria arquivo real para calcular checksum
    artifact_file = tmp_path / "requirements.md"
    artifact_file.write_text("# Requirements\n\n- Feature A\n", encoding="utf-8")

    version = store.add_artifact_version(
        memory.project_id,
        ArtifactKind.REQUIREMENTS,
        str(artifact_file),
        mission_id="m-789",
        summary="Primeira versão de requisitos",
    )
    assert version.version_id
    assert version.kind == ArtifactKind.REQUIREMENTS
    assert version.path == str(artifact_file)
    assert version.checksum is not None  # SHA256 calculado
    assert version.mission_id == "m-789"
    assert version.summary == "Primeira versão de requisitos"

    loaded = store.get(memory.project_id)
    assert loaded is not None
    assert len(loaded.artifact_versions) == 1
    assert loaded.artifact_versions[0].version_id == version.version_id


def test_add_artifact_version_without_file(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    memory = store.create(name="Teste")
    version = store.add_artifact_version(
        memory.project_id,
        ArtifactKind.ARCHITECTURE,
        "/nonexistent/path.md",
    )
    assert version.checksum is None  # arquivo não existe


def test_add_learning(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    memory = store.create(name="Teste")
    learning = store.add_learning(
        memory.project_id,
        text="Testes falharam por timeout de 30s",
        source="qa_failure",
        mission_id="m-999",
    )
    assert learning.learning_id
    assert learning.text == "Testes falharam por timeout de 30s"
    assert learning.source == "qa_failure"
    assert learning.mission_id == "m-999"

    loaded = store.get(memory.project_id)
    assert loaded is not None
    assert len(loaded.learnings) == 1


def test_latest_artifact(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    memory = store.create(name="Teste")

    base = datetime.now(timezone.utc)
    for i in range(3):
        store.add_artifact_version(
            memory.project_id,
            ArtifactKind.CODE_BUNDLE,
            f"/path/v{i}.zip",
            summary=f"Versão {i}",
            created_at=base + timedelta(seconds=i + 1),
        )

    latest = store.latest_artifact(memory.project_id, ArtifactKind.CODE_BUNDLE)
    assert latest is not None
    assert latest.summary == "Versão 2"  # maior created_at, determinístico

    assert store.latest_artifact(memory.project_id, ArtifactKind.VALIDATION_REPORT) is None


def test_list_projects(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    store.create(name="Projeto A")
    store.create(name="Projeto B")
    store.create(name="Projeto C")

    projects = store.list_projects()
    assert len(projects) == 3
    names = {p.name for p in projects}
    assert names == {"Projeto A", "Projeto B", "Projeto C"}


def test_list_projects_empty(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    assert store.list_projects() == []


def test_atomic_write_prevents_corruption(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    memory = store.create(name="Teste")

    # Simula corrupção: grava JSON inválido manualmente
    memory_file = tmp_path / memory.project_id / "memory.json"
    memory_file.write_text("{invalid json", encoding="utf-8")

    # get() retorna None (não quebra)
    assert store.get(memory.project_id) is None

    # Nova gravação via save() sobrescreve corretamente
    memory.name = "Recuperado"
    store.save(memory)
    loaded = store.get(memory.project_id)
    assert loaded is not None
    assert loaded.name == "Recuperado"


def test_multiple_events_preserved(tmp_path: Path) -> None:
    store = DiskProjectMemoryStore(base_dir=tmp_path)
    memory = store.create(name="Teste")

    store.append_event(memory.project_id, MemoryEventType.PROJECT_CREATED, "Criado")
    store.append_event(memory.project_id, MemoryEventType.BUILD_STARTED, "Build 1")
    store.append_event(memory.project_id, MemoryEventType.BUILD_SUCCEEDED, "Build 1 OK")

    loaded = store.get(memory.project_id)
    assert loaded is not None
    assert len(loaded.events) == 3
    assert loaded.events[0].type == MemoryEventType.PROJECT_CREATED
    assert loaded.events[2].type == MemoryEventType.BUILD_SUCCEEDED