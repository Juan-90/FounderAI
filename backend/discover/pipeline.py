"""
DiscoverPipeline — orquestrador do Modo DISCOVER (v4.7.0).

Consolida: ScopeFramer → Ideation → Normalizer → Ranker → Critic →
DiscoverSynthesizer (top + rejeitadas + report.md) → Handoff VALIDATE
(opcional) → Persistência em artifacts/discover/<mission_id>/.

v4.7.0 hotfix: handoff converte constraints list[str] -> str (ValidateRequest).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Optional, Protocol

from backend.core.config import Settings, settings
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
from backend.domain.models import MissionState
from backend.validate.schemas import ValidateRequest


class ValidatePipelineLike(Protocol):
    async def run(
        self, request: ValidateRequest, on_stage: Any = None,
        mission_id: Optional[str] = None,
    ) -> MissionState: ...


class DiscoverSynthesizer:
    """Compila top oportunidades + rejeitadas + relatório Markdown final."""

    def compile(
        self,
        kept: list[OpportunityProfile],
        rejected: list[dict],
        max_opportunities: int,
        scope: dict[str, Any],
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
    """Orquestra as 5 etapas + síntese + handoff + persistência."""

    def __init__(
        self,
        client: Any | None = None,
        config: Settings | None = None,
        artifact_manager: ArtifactManager | None = None,
        validate_pipeline: ValidatePipelineLike | None = None,
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
        self.last_mission_id: Optional[str] = None
        self.last_handoff: Optional[dict[str, Any]] = None

    @property
    def artifacts(self) -> ArtifactManager:
        return self._artifacts

    def _save(self, state: MissionState, name: str, content: str) -> None:
        artifact = self._artifacts.save_artifact(state.mission_id, name, content)
        state.artifacts.append(artifact)

    @staticmethod
    def _to_validate_request(
        request: DiscoverRequest, opp: OpportunityProfile
    ) -> ValidateRequest:
        # ValidateRequest.constraints é str | None; DiscoverRequest.constraints é list.
        constraints_str = "; ".join(request.constraints) if request.constraints else None
        return ValidateRequest(
            idea_text=(
                f"{opp.title}: {opp.one_liner} Problema: {opp.problem} "
                f"Por quê agora: {opp.why_now}"
            ),
            name=opp.title,
            target_audience=opp.audience,
            problem=opp.problem,
            solution=opp.solution_sketch,
            business_model=opp.business_model_hint,
            constraints=constraints_str,
        )

    async def run(self, request: DiscoverRequest) -> DiscoverResult:
        mission_id = uuid.uuid4().hex
        self.last_mission_id = mission_id

        # 1-5 — Etapas encadeadas
        scope = await self._framer.frame(request)
        raw = await self._ideation.generate(scope, request.seeds)
        raw = raw[: self._config.DISCOVER_INTERNAL_CANDIDATES]
        profiles = self._normalizer.normalize(raw)
        ranked = self._ranker.rank(profiles)
        if request.include_contrarian:
            kept, rejected = self._critic.critique(ranked)
        else:
            kept, rejected = ranked, []

        # Síntese
        top, report_md = self._synth.compile(kept, rejected, request.max_opportunities, scope)
        summary = (
            f"{len(top)} oportunidade(s) selecionada(s) de {len(raw)} candidatas; "
            f"{len(rejected)} rejeitada(s) pelo critic. "
            f"Top: {top[0].title if top else 'n/a'}."
        )
        recommended_next = (
            ["Validar a oportunidade top no modo VALIDATE."]
            if request.handoff_to_validate and top else []
        )

        # Handoff opcional para VALIDATE
        handoff: Optional[dict[str, Any]] = None
        if (
            request.handoff_to_validate
            and request.selected_opportunity_id
            and self._validate is not None
        ):
            selected = next(
                (p for p in ranked if p.id == request.selected_opportunity_id), None
            )
            if selected is not None:
                vstate = await self._validate.run(self._to_validate_request(request, selected))
                handoff = {
                    "opportunity_id": selected.id,
                    "validate_mission_id": vstate.mission_id,
                }
                recommended_next.append(
                    f"Handoff concluído: missão de validação {vstate.mission_id}."
                )
        self.last_handoff = handoff

        result = DiscoverResult(
            opportunities=top, rejected=rejected, ranking_method=RANKING_METHOD,
            summary=summary, recommended_next=recommended_next, handoff=handoff,
        )

        # Persistência
        state = MissionState(
            mission_id=mission_id, project_id=uuid.uuid4().hex,
            mode=ProjectMode.DISCOVER, status=MissionStatus.COMPLETED,
            current_stage="report",
            mode_payload={
                "theme": request.theme, "scope": scope,
                "candidate_count": len(raw), "rejected_count": len(rejected),
                "handoff": handoff, "summary": summary,
            },
        )
        self._save(state, "scope.json", json.dumps(scope, indent=2, ensure_ascii=False))
        self._save(state, "opportunities.json",
                   json.dumps([p.model_dump() for p in top], indent=2, ensure_ascii=False))
        self._save(state, "rejected.json",
                   json.dumps(rejected, indent=2, ensure_ascii=False))
        self._save(state, "discover_report.md", report_md)
        self._artifacts.save_mission_state(state)

        return result