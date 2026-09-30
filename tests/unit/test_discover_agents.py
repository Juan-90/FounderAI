"""
Testes unitários dos agentes/pipeline DISCOVER (v4.7.0). Sem LLM real.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.discover.agents import (
    DiscoverPipeline,
    OpportunityCritic,
    OpportunityNormalizer,
    OpportunityRanker,
    RANK_WEIGHTS,
)
from backend.discover.schemas import DiscoverRequest, OpportunityProfile
from backend.domain.artifacts import ArtifactManager


class FakeDiscoverClient:
    def __init__(self, frame: dict, candidates: list[dict]) -> None:
        self._queue = [frame, {"candidates": candidates}]

    async def complete(self, system_prompt, user_prompt, model=None, role=None) -> str:
        raise NotImplementedError

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        return self._queue.pop(0)


def _cand(title: str, **kw: Any) -> dict:
    base = {
        "title": title, "one_liner": kw.get("one_liner", f"resumo de {title}"),
        "problem": kw.get("problem", "dor real caro lento difícil"),
        "audience": "PMEs", "why_now": "regulação e digitalização crescem",
        "solution_sketch": "MVP web simples", "business_model_hint": "SaaS mensal",
        "risks": [], "assumptions": [], "tags": ["b2b", "saas"],
    }
    base.update(kw)
    return base


_GOOD_CANDIDATES = [
    _cand("Agenda inteligente para barbearias"),
    _cand("Controle de estoque para restaurantes"),
    _cand("Relatórios de carbono para PMEs"),
    _cand("Rede social para tudo"),                      # clichê -> rejeitado
    _cand("Agenda inteligente para barbearias e salões"),  # duplicata semântica
]


# ─────────────────────────────────────────────────────────────
# Normalizer
# ─────────────────────────────────────────────────────────────

def test_normalizer_converte_com_defaults() -> None:
    profiles = OpportunityNormalizer().normalize([_cand("X"), {"title": "Y"}])
    assert len(profiles) == 2
    assert profiles[0].score == 0.0
    assert profiles[0].evidence_level == "low"
    assert profiles[1].id.startswith("opp-1-")


# ─────────────────────────────────────────────────────────────
# Ranker
# ─────────────────────────────────────────────────────────────

def test_ranker_pesos_somam_um() -> None:
    assert abs(sum(RANK_WEIGHTS.values()) - 1.0) < 1e-9


def test_ranker_score_limitado_e_ordenado() -> None:
    profiles = OpportunityNormalizer().normalize(_GOOD_CANDIDATES[:3])
    ranked = OpportunityRanker().rank(profiles)
    assert all(0.0 <= p.score <= 1.0 for p in ranked)
    scores = [p.score for p in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(set(p.score_breakdown) == set(RANK_WEIGHTS) for p in ranked)


# ─────────────────────────────────────────────────────────────
# Critic
# ─────────────────────────────────────────────────────────────

def test_critic_rejeita_cliche_e_duplicata() -> None:
    profiles = OpportunityNormalizer().normalize(_GOOD_CANDIDATES)
    kept, rejected = OpportunityCritic().critique(profiles)
    titles_rej = {r["title"] for r in rejected}
    assert "Rede social para tudo" in titles_rej
    assert "Agenda inteligente para barbearias e salões" in titles_rej
    assert all(r["reason"] for r in rejected)
    assert len(kept) == 3


# ─────────────────────────────────────────────────────────────
# Pipeline (fakes)
# ─────────────────────────────────────────────────────────────

def _pipeline(tmp_path: Path, include_contrarian: bool = True) -> DiscoverPipeline:
    client = FakeDiscoverClient(
        frame={"theme": "serviços locais", "audience": "PMEs",
               "geography": "Brasil", "constraints": [], "attractiveness_criteria": []},
        candidates=_GOOD_CANDIDATES,
    )
    return DiscoverPipeline(
        client=client,
        artifact_manager=ArtifactManager(root=tmp_path),
    )


def test_pipeline_respeita_max_e_persiste(tmp_path: Path) -> None:
    pipe = _pipeline(tmp_path)
    result = asyncio.run(pipe.run(DiscoverRequest(
        theme="serviços locais", max_opportunities=2, include_contrarian=True,
    )))
    assert len(result.opportunities) <= 2
    assert result.ranking_method == "weighted_v1"
    assert result.summary
    assert len(result.rejected) >= 2  # clichê + duplicata

    # Narrowing: last_discover_id é Optional[str]; garante str antes do Path "/"
    assert pipe.last_discover_id is not None
    assert (tmp_path / pipe.last_discover_id / "discover_result.json").exists()


def test_pipeline_sem_contrarian_nao_rejeita(tmp_path: Path) -> None:
    pipe = _pipeline(tmp_path)
    result = asyncio.run(pipe.run(DiscoverRequest(
        theme="serviços locais", include_contrarian=False,
    )))
    assert result.rejected == []
    assert len(result.opportunities) > 0


def test_pipeline_handoff_to_validate(tmp_path: Path) -> None:
    pipe = _pipeline(tmp_path)
    result = asyncio.run(pipe.run(DiscoverRequest(
        theme="serviços locais", handoff_to_validate=True,
    )))
    assert result.recommended_next