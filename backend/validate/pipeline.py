"""
ValidatePipeline — orquestrador do Modo VALIDATE (v5.3.0 + Memory Hooks + Evidence).

v5.3.0: Injeta memória do projeto no contexto dos agentes (via intent) e
grava eventos/decisões/artefatos ao finalizar.
v5.2.0: Injeta EvidenceService e persiste EvidenceGraph.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from rich.console import Console

from backend.core.config import Settings, settings
from backend.core.evidence.service import EvidenceService
from backend.core.memory_compiler import MemoryContextCompiler
from backend.core.memory_hooks import (
    attach_memory_to_intent,
    build_memory_block,
    record_validate_completion,
    resolve_memory,
)
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode
from backend.domain.evidence import Claim, EvidenceGraph, EvidenceItem, EvidenceOrigin
from backend.domain.evidence_store import save_evidence_graph
from backend.domain.memory_store import DiskProjectMemoryStore
from backend.domain.models import MissionState
from backend.validate.agents import (
    CompetitorAgent,
    ContrarianRiskAgent,
    ExperimentDesignAgent,
    IdeaIntakeAgent,
    ProblemMarketAgent,
    TechnicalFeasibilityAgent,
    ValidationSynthesizer,
)
from backend.validate.schemas import ValidateRequest

console = Console(stderr=True)

StageCallback = Callable[[int, str], None]

_STOPWORDS = frozenset({"de", "da", "do", "das", "dos", "para", "com", "em",
                        "no", "na", "um", "uma", "que", "e", "ou", "por"})


def _kw(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


class ValidatePipeline:
    def __init__(
        self,
        client: Any | None = None,
        artifact_manager: ArtifactManager | None = None,
        config: Settings | None = None,
        evidence_service: Optional[EvidenceService] = None,
        memory_store: Optional[DiskProjectMemoryStore] = None,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._artifacts: ArtifactManager = (
            artifact_manager
            if artifact_manager is not None
            else ArtifactManager(root=Path(self._config.VALIDATE_ARTIFACTS_DIR))
        )
        self._evidence_service = evidence_service
        self._intake = IdeaIntakeAgent(client)
        self._problem = ProblemMarketAgent(client)
        self._competitor = CompetitorAgent(client)
        self._tech = TechnicalFeasibilityAgent(client)
        self._contrarian = ContrarianRiskAgent(client)
        self._experiments = ExperimentDesignAgent(client)
        self._synth = ValidationSynthesizer(client)
        self._memory_store = memory_store
        self._project_id = project_id
        self._project_name = project_name
        self._compiler = MemoryContextCompiler(memory_store) if memory_store else None
        self.last_mission_id: Optional[str] = None

    @property
    def artifacts(self) -> ArtifactManager:
        return self._artifacts

    @staticmethod
    def _emit(on_stage: Optional[StageCallback], index: int, label: str) -> None:
        if on_stage is not None:
            on_stage(index, label)

    def _advance(self, state: MissionState, stage: str) -> None:
        state.current_stage = stage

    def _save(self, state: MissionState, name: str, content: str) -> None:
        artifact = self._artifacts.save_artifact(state.mission_id, name, content)
        state.artifacts.append(artifact)

    async def _run_stage(
        self, on_stage: Optional[StageCallback], index: int, label: str,
        agent_name: str, coro: Any,
    ) -> Any:
        self._emit(on_stage, index, label)
        try:
            return await coro
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            console.print(f"[bold yellow]⚠️  Erro no estágio {agent_name}: {msg}[/bold yellow]")
            raise

    def _save_failure_report(self, state: MissionState, error_msg: str) -> None:
        failure = (
            "# Validation Report (FALHA)\n\n"
            f"Estágio da falha: {state.current_stage}\n\n"
            "## Erro\n```\n" + error_msg + "\n```\n"
        )
        try:
            self._save(state, "validation_report.md", failure)
        except Exception:
            pass

    def _extract_claims(
        self, idea_profile: dict, problem_market: dict, evidence_items: list[EvidenceItem]
    ) -> list[Claim]:
        """Extrai claims principais e vincula a evidências por overlap."""
        claims: list[Claim] = []
        problem = problem_market.get("pain_description", "")
        if problem:
            p_kw = _kw(problem)
            matched = [ev.evidence_id for ev in evidence_items if p_kw & _kw(ev.quote_or_summary)]
            claims.append(Claim(claim_id="cl-problem", text=problem,
                                origin=EvidenceOrigin.MODEL_OPINION, evidence_ids=matched))
        audience = problem_market.get("audience_segment", "") or idea_profile.get(
            "clarified_fields", {}).get("target_audience", "")
        if audience:
            a_kw = _kw(audience)
            matched = [ev.evidence_id for ev in evidence_items if a_kw & _kw(ev.quote_or_summary)]
            claims.append(Claim(claim_id="cl-audience", text=f"Público-alvo: {audience}",
                                origin=EvidenceOrigin.MODEL_OPINION, evidence_ids=matched))
        return claims

    def _identify_evidence_gaps(
        self, problem_market: dict, evidence_items: list[EvidenceItem]
    ) -> list[str]:
        """Identifica lacunas onde claims não têm evidência externa."""
        gaps: list[str] = []
        if not evidence_items:
            gaps.append("Nenhuma evidência externa coletada — todas as alegações são opinião do modelo.")
            return gaps
        problem = problem_market.get("pain_description", "")
        if problem and not any(
            any(kw in ev.quote_or_summary.lower() for kw in problem.lower().split()[:5])
            for ev in evidence_items
        ):
            gaps.append(f"Sem evidência externa para o problema: '{problem[:80]}...'")
        return gaps

    def _evidence_section(
        self, claims: list[Claim], evidence_items: list[EvidenceItem],
        sources: list[Any], gaps: list[str],
    ) -> str:
        from backend.domain.evidence import Source
        src_by_id = {s.source_id: s for s in sources if isinstance(s, Source)}
        ev_by_id = {e.evidence_id: e for e in evidence_items}
        lines = ["", "## Evidence vs Opinion", "", "### Claims com evidência externa"]
        cited = False
        for c in claims:
            for eid in c.evidence_ids:
                ev = ev_by_id.get(eid)
                if ev is None:
                    continue
                src = src_by_id.get(ev.source_id)
                url = src.url if src else None
                publisher = (src.publisher if src else None) or "fonte desconhecida"
                lines.append(f"- {c.text} — \"{ev.quote_or_summary[:80]}\" "
                             f"[Source: {publisher}/{url or 'sem-url'}]")
                cited = True
        if not cited:
            lines.append("- (nenhum claim corroborado por evidência externa)")
        lines += ["", "### Evidence gaps (opinião não corroborada)"]
        if gaps:
            lines += [f"- {g}" for g in gaps]
        else:
            lines.append("- (nenhum)")
        return "\n".join(lines) + "\n"

    async def run(
        self, request: ValidateRequest, on_stage: Optional[StageCallback] = None,
        mission_id: Optional[str] = None,
    ) -> MissionState:
        state = MissionState(
            mission_id=mission_id or uuid.uuid4().hex, project_id=uuid.uuid4().hex,
            mode=ProjectMode.VALIDATE, status=MissionStatus.IN_PROGRESS,
            current_stage="init", mode_payload={"idea_text": request.idea_text},
        )
        self.last_mission_id = state.mission_id

        # Injeção de memória (v5.3.0)
        memory = None
        if (self._memory_store is not None and self._compiler is not None
                and (self._project_id or self._project_name)):
            memory = resolve_memory(self._memory_store, self._project_id, self._project_name)
            if memory is not None:
                block = build_memory_block(self._compiler, memory.project_id)
                request = request.model_copy(update={
                    "idea_text": attach_memory_to_intent(request.idea_text, block)})

        evidence_items: list[EvidenceItem] = []
        sources: list[Any] = []
        claims: list[Claim] = []
        real_gaps: list[str] = []

        try:
            # 1 — Idea Intake
            idea_profile = await self._run_stage(
                on_stage, 1, "Normalizing Idea...", "IdeaIntakeAgent",
                self._intake.analyze(request.model_dump()),
            )
            self._save(state, "idea_profile.json",
                       json.dumps(idea_profile, indent=2, ensure_ascii=False))
            state.mode_payload["idea_profile"] = idea_profile
            self._advance(state, "idea_intake")

            # 2 — Problem & Market
            problem_market = await self._run_stage(
                on_stage, 2, "Assessing Problem & Market...", "ProblemMarketAgent",
                self._problem.analyze(idea_profile),
            )
            self._save(state, "market_problem.md",
                       json.dumps(problem_market, indent=2, ensure_ascii=False))
            state.mode_payload["problem_market"] = problem_market
            self._advance(state, "problem_market")

            # 3 — Competitors
            competitors = await self._run_stage(
                on_stage, 3, "Mapping Competitors...", "CompetitorAgent",
                self._competitor.analyze(idea_profile, problem_market),
            )
            self._save(state, "competitors.md",
                       json.dumps(competitors, indent=2, ensure_ascii=False))
            state.mode_payload["competitors"] = competitors
            self._advance(state, "competitors")

            # Evidence Search (v5.2.0) — após Mercado + Concorrência
            if self._evidence_service is not None and self._evidence_service.enabled:
                queries = self._evidence_service.plan_queries("validate", {
                    "problem": problem_market.get("pain_description", ""),
                    "audience": problem_market.get("audience_segment", ""),
                })
                results = self._evidence_service.search(queries)
                sources, evidence_items = self._evidence_service.to_evidence(results)
                claims = self._extract_claims(idea_profile, problem_market, evidence_items)
                real_gaps = self._identify_evidence_gaps(problem_market, evidence_items)

            # 4 — Technical Feasibility
            tech = await self._run_stage(
                on_stage, 4, "Evaluating Technical Feasibility...", "TechnicalFeasibilityAgent",
                self._tech.analyze(idea_profile, problem_market, competitors),
            )
            self._save(state, "technical_feasibility.md",
                       json.dumps(tech, indent=2, ensure_ascii=False))
            state.mode_payload["technical_feasibility"] = tech
            self._advance(state, "technical_feasibility")

            # 5 — Contrarian Risk
            risks = await self._run_stage(
                on_stage, 5, "Running Contrarian Risk Analysis...", "ContrarianRiskAgent",
                self._contrarian.analyze(idea_profile, problem_market, competitors, tech),
            )
            self._save(state, "risks_contrarian.md",
                       json.dumps(risks, indent=2, ensure_ascii=False))
            state.mode_payload["risks_contrarian"] = risks
            self._advance(state, "risks_contrarian")

            # Evidence gaps (derivados + reais)
            evidence_gaps = (
                list(idea_profile.get("gaps", []))
                + list(problem_market.get("inferences", []))
                + real_gaps
            )
            state.mode_payload["evidence_gaps"] = evidence_gaps
            state.mode_payload["hypotheses"] = [
                {"hypothesis": g, "status": "untested"} for g in evidence_gaps
            ]

            # 6 — Experiment Design
            exp = await self._run_stage(
                on_stage, 6, "Designing Experiments...", "ExperimentDesignAgent",
                self._experiments.analyze(idea_profile, problem_market, evidence_gaps),
            )
            self._save(state, "experiments.md", json.dumps(exp, indent=2, ensure_ascii=False))
            state.mode_payload["experiments"] = exp["experiments"]
            self._advance(state, "experiments")

            # 7 — Synthesis
            all_stages = {
                "idea_profile": idea_profile, "problem_market": problem_market,
                "competitors": competitors, "technical_feasibility": tech,
                "risks_contrarian": risks, "experiments": exp["experiments"],
                "evidence_gaps": evidence_gaps,
            }
            rec = await self._run_stage(
                on_stage, 7, "Synthesizing Verdict...", "ValidationSynthesizer",
                self._synth.synthesize(all_stages),
            )
            verdict = rec.get("verdict") or self._config.VALIDATE_DEFAULT_VERDICT_IF_UNCERTAIN
            rec["verdict"] = verdict

            # Anexa seção "Evidence vs Opinion" (v5.2.0)
            final_report = rec.get("final_report", "")
            if evidence_items or sources or real_gaps:
                final_report += self._evidence_section(claims, evidence_items, sources, real_gaps)
            rec["final_report"] = final_report

            state.mode_payload["recommendation"] = rec
            state.mode_payload["final_report"] = final_report
            self._save(state, "validation_report.md", final_report)
            self._advance(state, "report")
            state.status = MissionStatus.COMPLETED

        except Exception as exc:
            state.status = MissionStatus.FAILED
            error_msg = f"{type(exc).__name__}: {exc}"
            state.mode_payload["error"] = error_msg
            state.mode_payload["error_stage"] = state.current_stage
            self._save_failure_report(state, error_msg)

        finally:
            # Persiste EvidenceGraph (v5.2.0)
            if evidence_items or sources:
                graph = EvidenceGraph(
                    mission_id=state.mission_id, claims=claims,
                    evidence_items=evidence_items, sources=sources,
                    notes=self._evidence_service.warnings if self._evidence_service else [],
                )
                save_evidence_graph(self._artifacts.root / state.mission_id, graph)

            self._artifacts.save_mission_state(state)

            # Gravação de memória (v5.3.0) — fail-open
            if memory is not None and self._memory_store is not None:
                try:
                    record_validate_completion(
                        self._memory_store, memory, state,
                        self._artifacts.root / state.mission_id)
                except Exception:
                    pass

        return state