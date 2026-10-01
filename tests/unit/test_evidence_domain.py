"""
Testes unitários do domínio de evidências (v5.2.0).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.domain.evidence import (
    Claim,
    EvidenceGraph,
    EvidenceItem,
    EvidenceOrigin,
    Source,
)
from backend.domain.evidence_store import load_evidence_graph, save_evidence_graph


def _now() -> datetime:
    return datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _source(**overrides: Any) -> Source:
    base: dict[str, Any] = {
        "source_id": "src-1",
        "title": "IBGE",
        "url": "https://ibge.gov.br",
        "publisher": "IBGE",
        "retrieved_at": _now(),
        "raw_snippet": "Dados sobre PMEs...",
    }
    base.update(overrides)
    return Source(**base)


def _evidence(**overrides: Any) -> EvidenceItem:
    base: dict[str, Any] = {
        "evidence_id": "ev-1",
        "source_id": "src-1",
        "quote_or_summary": "PMEs representam 30% do PIB.",
    }
    base.update(overrides)
    return EvidenceItem(**base)


def _claim(**overrides: Any) -> Claim:
    base: dict[str, Any] = {
        "claim_id": "cl-1",
        "text": "Há demanda forte de PMEs por relatórios ESG.",
        "origin": EvidenceOrigin.EXTERNAL,
    }
    base.update(overrides)
    return Claim(**base)


# ─────────────────────────────────────────────────────────────
# EvidenceOrigin
# ─────────────────────────────────────────────────────────────

def test_evidence_origin_enum_values() -> None:
    assert EvidenceOrigin.MODEL_OPINION.value == "model_opinion"
    assert EvidenceOrigin.USER_CONTEXT.value == "user_context"
    assert EvidenceOrigin.EXTERNAL.value == "external"


# ─────────────────────────────────────────────────────────────
# Source
# ─────────────────────────────────────────────────────────────

def test_source_instantiation() -> None:
    src = _source()
    assert src.source_id == "src-1"
    assert src.retrieved_at == _now()


def test_source_optional_fields() -> None:
    src = Source(source_id="src-min", retrieved_at=_now())
    assert src.title is None
    assert src.url is None
    assert src.publisher is None
    assert src.raw_snippet is None


# ─────────────────────────────────────────────────────────────
# EvidenceItem
# ─────────────────────────────────────────────────────────────

def test_evidence_item_defaults() -> None:
    ev = _evidence()
    assert ev.origin == EvidenceOrigin.EXTERNAL
    assert ev.confidence == 0.5
    assert ev.tags == []


def test_evidence_item_valida_confidence_range() -> None:
    with pytest.raises(Exception):
        _evidence(confidence=1.5)
    with pytest.raises(Exception):
        _evidence(confidence=-0.1)


# ─────────────────────────────────────────────────────────────
# Claim
# ─────────────────────────────────────────────────────────────

def test_claim_construction() -> None:
    cl = _claim(evidence_ids=["ev-1", "ev-2"], used_in_decision=True)
    assert cl.evidence_ids == ["ev-1", "ev-2"]
    assert cl.used_in_decision is True


def test_claim_defaults() -> None:
    cl = _claim()
    assert cl.confidence == 0.5
    assert cl.evidence_ids == []
    assert cl.used_in_decision is False


# ─────────────────────────────────────────────────────────────
# EvidenceGraph
# ─────────────────────────────────────────────────────────────

def test_evidence_graph_empty() -> None:
    g = EvidenceGraph(mission_id="m-1")
    assert g.mission_id == "m-1"
    assert g.claims == []
    assert g.evidence_items == []
    assert g.sources == []
    assert g.notes == []


def test_evidence_graph_serialization_roundtrip() -> None:
    g = EvidenceGraph(
        mission_id="m-2",
        sources=[_source()],
        evidence_items=[_evidence()],
        claims=[_claim()],
        notes=["observação do analista"],
    )
    data = g.model_dump(mode="json")
    rebuilt = EvidenceGraph.model_validate(data)
    assert rebuilt.mission_id == g.mission_id
    assert len(rebuilt.sources) == 1
    assert rebuilt.sources[0].source_id == "src-1"
    assert rebuilt.notes == ["observação do analista"]


# ─────────────────────────────────────────────────────────────
# evidence_store: save / load
# ─────────────────────────────────────────────────────────────

def test_save_and_load_evidence_graph(tmp_path: Path) -> None:
    graph = EvidenceGraph(
        mission_id="m-3",
        sources=[_source(source_id="s-a"), _source(source_id="s-b", title="Outro")],
        evidence_items=[_evidence(evidence_id="e-1"), _evidence(evidence_id="e-2")],
        claims=[_claim(claim_id="c-1", evidence_ids=["e-1"])],
        notes=["nota 1"],
    )
    save_evidence_graph(tmp_path, graph)

    evidence_dir = tmp_path / "evidence"
    assert evidence_dir.is_dir()
    assert (evidence_dir / "sources.json").exists()
    assert (evidence_dir / "evidence_items.json").exists()
    assert (evidence_dir / "claims.json").exists()
    assert (evidence_dir / "evidence_graph.json").exists()

    sources_raw = json.loads((evidence_dir / "sources.json").read_text(encoding="utf-8"))
    assert len(sources_raw) == 2
    items_raw = json.loads((evidence_dir / "evidence_items.json").read_text(encoding="utf-8"))
    assert len(items_raw) == 2
    claims_raw = json.loads((evidence_dir / "claims.json").read_text(encoding="utf-8"))
    assert claims_raw[0]["claim_id"] == "c-1"

    loaded = load_evidence_graph(tmp_path)
    assert loaded is not None
    assert loaded.mission_id == "m-3"
    assert len(loaded.sources) == 2
    assert loaded.notes == ["nota 1"]


def test_load_nonexistent_returns_none(tmp_path: Path) -> None:
    assert load_evidence_graph(tmp_path) is None


def test_save_creates_evidence_subdir(tmp_path: Path) -> None:
    graph = EvidenceGraph(mission_id="m-4")
    save_evidence_graph(tmp_path, graph)
    assert (tmp_path / "evidence" / "evidence_graph.json").exists()