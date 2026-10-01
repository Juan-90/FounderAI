"""
DiscoverPipeline — orquestrador do Modo DISCOVER (v5.2.0 + Evidence).

ScopeFramer → Ideation → Evidence Search → Normalizer → Ranker → Critic →
DiscoverSynthesizer → Handoff VALIDATE (opcional) → Persistência.

v5.2.0: Injeta EvidenceService (opcional) entre ideação e ranking; calcula
evidence_level (Literal low/medium/high); vincula claims; relatório com
seção "Evidências Externas e Sinais de Mercado"; persiste EvidenceGraph.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Literal, Optional, Protocol

from backend.core.config import Settings, settings
from backend.core.evidence.service import EvidenceService
from backend.discover.agents import (
    RANKING_METHOD,
    OpportunityCritic,
    OpportunityIdeationAgent,
    OpportunityNormalizer,
    OpportunityRanker,
    ScopeFramerAgent,
)
from backend.discover.schemas import (
    DiscoverRequest,
    DiscoverResult,
    OpportunityProfile,
)
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.evidence import (
    Claim,
    EvidenceGraph,
    EvidenceItem,
    EvidenceOrigin,
    Source,
)
from backend.domain.evidence_store import save_evidence_graph
from backend.domain.models import MissionState
from backend.validate.schemas import ValidateRequest

EvidenceLevel = Literal["low", "medium", "high"]

_STOPWORDS = frozenset({"de", "da", "do", "das", "dos", "para", "com", "em",
                        "no", "na", "um", "uma", "que", "e", "ou", "por"})


def _kw(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


class ValidatePipelineLike(Protocol):
    async def run(
        self, request: ValidateRequest, on_stage: Any = None,
        mission_id: Optional[str] = None,
    ) -> MissionState: ...


def _compute_evidence_level(items: list[EvidenceItem]) -> EvidenceLevel:
    if not items:
        return "low"
    avg_conf = sum(i.confidence for i in items) / len(items)
    if len(items) >= 3 and avg_conf >= 0.7:
        return "high"
    return "medium"


def _link_claims_to_opportunities(
    opp: OpportunityProfile, items: list[EvidenceItem]
) -> list[str]:
    opp_kw = _kw(f"{opp.title} {opp.one_liner}")
    if not opp_kw:
        return []
    return [ev.evidence_id for ev in items if opp_kw & _kw(ev.quote_or_summary)]


class DiscoverSynthesizer:
    def compile(
        self,
        kept: list[OpportunityProfile],
        rejected: list[dict],
        max_opportunities: int,
        scope: dict[str, Any],
        evidence_items: Optional[list[EvidenceItem]] = None,
        sources: Optional[list[Source]] = None,
    ) -> tuple[list[OpportunityProfile], str]:
        top = kept[:max_opportunities]
        lines = [
            "# Discover Report", "",
            "## Escopo",
            f"- Tema: {scope.get('theme', 'n/a')}",
            f"- Público: {scope.get('audience') or 'não informado'}",
            f"- Geografia: {scope.get('geography', 'n/a')}",
            f"- Critérios: {', '.join(scope.get('attractiveness_criteria', [])) or 'padrão'}",
            "",
            "## Oportunidades Ranqueadas",
        ]
        if top:
            for i, p in enumerate(top, 1):
                lines.append(f"{i}. **{p.title}** — score {p.score:.2f} (evidência {p.evidence_level})")
                lines.append(f"   - {p.one_liner}")
        else:
            lines.append("- (nenhuma oportunidade aprovada)")

        lines += ["", "## Evidências Externas e Sinais de Mercado"]
        if evidence_items and sources:
            lines.append(f"- {len(evidence_items)} evidência(s) de {len(sources)} fonte(s).")
            for src in sources[:5]:
                lines.append(f"  - **{src.title or 'Sem título'}** ({src.publisher or 'fonte desconhecida'})")
                if src.url:
                    lines.append(f"    - URL: {src.url}")
        else:
            lines.append("- (nenhuma evidência externa coletada)")

        lines += ["", "## Rejeitadas pelo Critic"]
        if rejected:
            for r in rejected:
                lines.append(f"- {r['title']}: {r['reason']}")
        else:
            lines.append("- (nenhuma)")
        lines += [
            "", "## Próximos passos",
            '- Validar a top: python main.py validate "<título: one_liner>"',
            '- Ou handoff direto: python main.py discover "<tema>" --handoff <id>',
        ]
        return top, "\n".join(lines) + "\n"


class DiscoverPipeline:
    def __init__(
        self,
        client: Any | None = None,
        config: Settings | None = None,
        artifact_manager: ArtifactManager | None = None,
        validate_pipeline: ValidatePipelineLike | None = None,
        evidence_service: Optional[EvidenceService] = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._artifacts: ArtifactManager = (
            artifact_manager
            if artifact_manager is not None
            else ArtifactManager(root=Path(self._config.DISCOVER_ARTIFACTS_DIR))
        )
        self._framer = ScopeFramerAgent(client)
        self._ideation = OpportunityIdeationAgent(client)
        self._normalizer = OpportunityNormalizer()
        self._ranker = OpportunityRanker()
        self._critic = OpportunityCritic()
        self._synth = DiscoverSynthesizer()
        self._validate = validate_pipeline
        self._evidence = evidence_service
        self.last_mission_id: Optional[str] = None
        self.last_handoff: Optional[dict[str, Any]] = None

    @property
    def artifacts(self) -> ArtifactManager:
        return self._artifacts

    def _save(self, state: MissionState, name: str, content: str) -> None:
        artifact = self._artifacts.save_artifact(state.mission_id, name, content)
        state.artifacts.append(artifact)

    @staticmethod
    def _to_validate_request(request: DiscoverRequest, opp: OpportunityProfile) -> ValidateRequest:
        constraints_str = "; ".join(request.constraints) if request.constraints else None
        return ValidateRequest(
            idea_text=(f"{opp.title}: {opp.one_liner} Problema: {opp.problem} "
                       f"Por quê agora: {opp.why_now}"),
            name=opp.title, target_audience=opp.audience, problem=opp.problem,
            solution=opp.solution_sketch, business_model=opp.business_model_hint,
            constraints=constraints_str,
        )

    async def run(self, request: DiscoverRequest) -> DiscoverResult:
        mission_id = uuid.uuid4().hex
        self.last_mission_id = mission_id

        scope = await self._framer.frame(request)
        raw = await self._ideation.generate(scope, request.seeds)
        raw = raw[: self._config.DISCOVER_INTERNAL_CANDIDATES]

        # Evidence Search (v5.2.0)
        evidence_items: list[EvidenceItem] = []
        sources: list[Source] = []
        if self._evidence is not None and self._evidence.enabled:
            queries = self._evidence.plan_queries("discover", scope)
            results = self._evidence.search(queries)
            sources, evidence_items = self._evidence.to_evidence(results)

        profiles = self._normalizer.normalize(raw)

        # Enrich with evidence (v5.2.0)
        for opp in profiles:
            linked = _link_claims_to_opportunities(opp, evidence_items)
            opp.evidence_level = (
                _compute_evidence_level([e for e in evidence_items if e.evidence_id in linked])
                if linked else "low"
            )

        ranked = self._ranker.rank(profiles)
        if request.include_contrarian:
            kept, rejected = self._critic.critique(ranked)
        else:
            kept, rejected = ranked, []

        top, report_md = self._synth.compile(
            kept, rejected, request.max_opportunities, scope,
            evidence_items=evidence_items, sources=sources,
        )
        summary = (
            f"{len(top)} oportunidade(s) selecionada(s) de {len(raw)} candidatas; "
            f"{len(rejected)} rejeitada(s) pelo critic. Top: {top[0].title if top else 'n/a'}."
        )
        recommended_next = (
            ["Validar a oportunidade top no modo VALIDATE."]
            if request.handoff_to_validate and top else []
        )

        handoff: Optional[dict[str, Any]] = None
        if (request.handoff_to_validate and request.selected_opportunity_id
                and self._validate is not None):
            selected = next((p for p in ranked if p.id == request.selected_opportunity_id), None)
            if selected is not None:
                vstate = await self._validate.run(self._to_validate_request(request, selected))
                handoff = {"opportunity_id": selected.id,
                           "validate_mission_id": vstate.mission_id}
                recommended_next.append(f"Handoff concluído: missão {vstate.mission_id}.")
        self.last_handoff = handoff

        result = DiscoverResult(
            opportunities=top, rejected=rejected, ranking_method=RANKING_METHOD,
            summary=summary, recommended_next=recommended_next, handoff=handoff,
        )

        state = MissionState(
            mission_id=mission_id, project_id=uuid.uuid4().hex,
            mode=ProjectMode.DISCOVER, status=MissionStatus.COMPLETED,
            current_stage="report",
            mode_payload={"theme": request.theme, "scope": scope,
                          "candidate_count": len(raw), "rejected_count": len(rejected),
                          "handoff": handoff, "summary": summary},
        )
        self._save(state, "scope.json", json.dumps(scope, indent=2, ensure_ascii=False))
        self._save(state, "opportunities.json",
                   json.dumps([p.model_dump() for p in top], indent=2, ensure_ascii=False))
        self._save(state, "rejected.json", json.dumps(rejected, indent=2, ensure_ascii=False))
        self._save(state, "discover_report.md", report_md)
        self._artifacts.save_mission_state(state)

        # Persiste EvidenceGraph (v5.2.0)
        if evidence_items or sources:
            claims = [
                Claim(claim_id=f"cl-{i}", text=opp.one_liner,
                      origin=EvidenceOrigin.MODEL_OPINION,
                      evidence_ids=_link_claims_to_opportunities(opp, evidence_items))
                for i, opp in enumerate(top, 1)
            ]
            graph = EvidenceGraph(
                mission_id=mission_id, claims=claims,
                evidence_items=evidence_items, sources=sources,
                notes=self._evidence.warnings if self._evidence else [],
            )
            save_evidence_graph(self._artifacts.root / mission_id, graph)

        return result