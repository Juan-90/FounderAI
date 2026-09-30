"""
Testes de integração do Modo DISCOVER (v4.7.0) — fluxo completo + handoff.

O FakeDiscoverClient é reutilizável (responde por conteúdo do prompt), pois o
teste de handoff executa o pipeline duas vezes com o mesmo client.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from backend.discover.pipeline import DiscoverPipeline
from backend.discover.schemas import DiscoverRequest
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.models import MissionState
from backend.validate.schemas import ValidateRequest


class FakeDiscoverClient:
    """Cliente fake reutilizável: frame vs. candidatos por conteúdo do prompt."""

    def __init__(self, candidates: list[dict]) -> None:
        self._frame = {
            "theme": "serviços locais", "audience": "PMEs", "geography": "Brasil",
            "constraints": [], "attractiveness_criteria": ["dor forte", "MVP rápido"],
        }
        self._candidates = candidates

    async def complete(self, system_prompt, user_prompt, model=None, role=None) -> str:
        raise NotImplementedError

    async def complete_json(self, system_prompt, user_prompt, model=None, role=None):
        if "candidatos" in user_prompt.lower():
            return {"candidates": self._candidates}
        return self._frame


class FakeValidate:
    def __init__(self) -> None:
        self.requests: list[ValidateRequest] = []

    async def run(self, request, on_stage=None, mission_id=None) -> MissionState:
        self.requests.append(request)
        return MissionState(
            mission_id="vhand-123", project_id="p", mode=ProjectMode.VALIDATE,
            status=MissionStatus.COMPLETED, current_stage="report",
            mode_payload={"recommendation": {"verdict": "INVESTIGATE", "confidence": 0.6}},
        )


def _cand(title: str, **kw: Any) -> dict:
    base = {
        "title": title, "one_liner": f"resumo de {title}",
        "problem": "dor real caro lento difícil retrabalho",
        "audience": "PMEs de serviços", "why_now": "digitalização acelerada pós-2024",
        "solution_sketch": "MVP web com agendamento", "business_model_hint": "SaaS R$ 49/mês",
        "risks": ["concorrência"], "assumptions": ["PMEs pagam"], "tags": ["b2b", "saas"],
    }
    base.update(kw)
    return base


_CANDIDATES = [
    _cand("Agenda inteligente para barbearias"),
    _cand("Controle de estoque para restaurantes"),
    _cand("Relatórios de carbono para PMEs"),
    _cand("Rede social para tudo"),                       # clichê
    _cand("Agenda inteligente para barbearias e salões"),  # duplicata
]


def _pipe(tmp_path: Path, validate=None) -> DiscoverPipeline:
    return DiscoverPipeline(
        client=FakeDiscoverClient(_CANDIDATES),
        artifact_manager=ArtifactManager(root=tmp_path),
        validate_pipeline=validate,
    )


# ─────────────────────────────────────────────────────────────
# 1) Fluxo completo: ranking + rejeitadas + artefatos
# ─────────────────────────────────────────────────────────────

def test_discover_fluxo_completo_gera_artefatos(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    result = asyncio.run(pipe.run(DiscoverRequest(
        theme="Oportunidades de software para barbearias no Brasil",
        max_opportunities=3,
    )))

    assert 1 <= len(result.opportunities) <= 3
    scores = [p.score for p in result.opportunities]
    assert scores == sorted(scores, reverse=True)
    assert len(result.rejected) >= 2

    assert pipe.last_mission_id is not None
    mid = pipe.last_mission_id
    for fname in ("scope.json", "opportunities.json", "rejected.json",
                  "discover_report.md", "mission_state.json"):
        assert (tmp_path / mid / fname).exists(), f"artefato ausente: {fname}"

    report = (tmp_path / mid / "discover_report.md").read_text(encoding="utf-8")
    assert "# Discover Report" in report
    assert "Rejeitadas pelo Critic" in report

    opps = json.loads((tmp_path / mid / "opportunities.json").read_text(encoding="utf-8"))
    assert len(opps) == len(result.opportunities)


# ─────────────────────────────────────────────────────────────
# 2) Handoff: oportunidade selecionada → ValidatePipeline
# ─────────────────────────────────────────────────────────────

def test_discover_handoff_envia_oportunidade_ao_validate(tmp_path: Path) -> None:
    fake_validate = FakeValidate()
    pipe = _pipe(tmp_path, validate=fake_validate)

    first = asyncio.run(pipe.run(DiscoverRequest(theme="serviços locais")))
    assert first.opportunities
    opp_id = first.opportunities[0].id

    second = asyncio.run(pipe.run(DiscoverRequest(
        theme="serviços locais",
        handoff_to_validate=True,
        selected_opportunity_id=opp_id,
    )))

    assert len(fake_validate.requests) == 1
    vreq = fake_validate.requests[0]
    assert vreq.name == first.opportunities[0].title
    assert vreq.problem == first.opportunities[0].problem

    assert second.handoff is not None
    assert second.handoff["opportunity_id"] == opp_id
    assert second.handoff["validate_mission_id"] == "vhand-123"

    assert pipe.last_mission_id is not None
    mid = pipe.last_mission_id
    state = json.loads((tmp_path / mid / "mission_state.json").read_text(encoding="utf-8"))
    assert state["mode_payload"]["handoff"]["validate_mission_id"] == "vhand-123"
    assert state["mode"] == ProjectMode.DISCOVER.value