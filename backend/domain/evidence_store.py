"""
Persistência do EvidenceGraph em disco (v5.2.0).

Grava em `<output_dir>/evidence/`:
  • sources.json        (projeção de fontes)
  • evidence_items.json (projeção de itens)
  • claims.json         (projeção de alegações)
  • evidence_graph.json (grafo completo, artefato canônico)

`load_evidence_graph` retorna None se o canônico não existir (não falha).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from backend.domain.evidence import EvidenceGraph


_EVIDENCE_DIR = "evidence"
_GRAPH_FILE = "evidence_graph.json"
_SOURCES_FILE = "sources.json"
_ITEMS_FILE = "evidence_items.json"
_CLAIMS_FILE = "claims.json"


def _evidence_dir(output_dir: Path) -> Path:
    return output_dir / _EVIDENCE_DIR


def save_evidence_graph(output_dir: Path, graph: EvidenceGraph) -> None:
    """Persiste o grafo e suas projeções em output_dir/evidence/."""
    evidence_path = _evidence_dir(output_dir)
    evidence_path.mkdir(parents=True, exist_ok=True)

    data = graph.model_dump(mode="json")

    (evidence_path / _GRAPH_FILE).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (evidence_path / _SOURCES_FILE).write_text(
        json.dumps(data["sources"], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (evidence_path / _ITEMS_FILE).write_text(
        json.dumps(data["evidence_items"], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (evidence_path / _CLAIMS_FILE).write_text(
        json.dumps(data["claims"], indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_evidence_graph(output_dir: Path) -> Optional[EvidenceGraph]:
    """Carrega o grafo canônico; retorna None se não existir."""
    graph_file = _evidence_dir(output_dir) / _GRAPH_FILE
    if not graph_file.exists():
        return None
    raw = json.loads(graph_file.read_text(encoding="utf-8"))
    return EvidenceGraph.model_validate(raw)