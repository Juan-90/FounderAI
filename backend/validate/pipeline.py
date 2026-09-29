"""
ValidatePipeline — orquestrador do Modo VALIDATE (v4.4.0).

Executa os 7 estágios analíticos em sequência e persiste TODOS os artefatos
em artifacts/validate/<mission_id>/:
  idea_profile.json, market_problem.md, competitors.md,
  technical_feasibility.md, risks_contrarian.md, experiments.md,
  validation_report.md, mission_state.json

O MissionState é criado com mode=VALIDATE e o mode_payload preenchido via
ValidatePayload.build(). Falhas são tratadas graciosamente (status FAILED +
validation_report.md de falha + mission_state.json sempre persistido).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from backend.core.config import Settings, settings
from backend.domain.artifacts import ArtifactManager
from backend.domain.enums import MissionStatus, ProjectMode
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
from backend.validate.schemas import ValidatePayload, ValidateRequest

StageCallback = Callable[[int, str], None]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _md(title: str, data: dict[str, Any]) -> str:
    """Renderiza um dict de estágio como Markdown legível."""
    lines: list[str] = [f"# {title}", ""]
    for key, value in data.items():
        lines.append(f"## {key}")
        if isinstance(value, (list, dict)):
            lines.append("```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```")
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines)


class ValidatePipeline:
    """Orquestra os 7 estágios do Modo VALIDATE."""

    def __init__(
        self,
        client: Any | None = None,
        artifact_manager: ArtifactManager | None = None,
        config: Settings | None = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._artifacts: ArtifactManager = (
            artifact_manager
            if artifact_manager is not None
            else ArtifactManager(root=Path(self._config.VALIDATE_ARTIFACTS_DIR))
        )
        self._intake = IdeaIntakeAgent(client)
        self._problem = ProblemMarketAgent(client)
        self._competitor = CompetitorAgent(client)
        self._tech = TechnicalFeasibilityAgent(client)
        self._contrarian = ContrarianRiskAgent(client)
        self._experiments = ExperimentDesignAgent(client)
        self._synth = ValidationSynthesizer(client)

    @property
    def artifacts(self) -> ArtifactManager:
        return self._artifacts

    @staticmethod
    def _emit(on_stage: Optional[StageCallback], index: int, label: str) -> None:
        if on_stage is not None:
            on_stage(index, label)

    def _advance(self, state: MissionState, stage: str) -> None:
        state.current_stage = stage
        state.updated_at = _utcnow()

    def _save(self, state: MissionState, name: str, content: str) -> None:
        artifact = self._artifacts.save_artifact(state.mission_id, name, content)
        state.artifacts.append(artifact)

    def _save_failure_report(self, state: MissionState, error_msg: str) -> None:
        failure = (
            "# Validation Report (FALHA)\n\n"
            f"Estágio da falha: {state.current_stage}\n\n"
            "## Erro\n```\n" + error_msg + "\n```\n\n"
            "## Limitações\n- Validação interrompida; artefatos parciais podem existir.\n"
        )
        try:
            self._save(state, "validation_report.md", failure)
        except Exception:
            pass

    async def run(
        self,
        request: ValidateRequest,
        on_stage: Optional[StageCallback] = None,
    ) -> MissionState:
        state = MissionState(
            mission_id=__import__("uuid").uuid4().hex,
            project_id=__import__("uuid").uuid4().hex,
            mode=ProjectMode.VALIDATE,
            status=MissionStatus.IN_PROGRESS,
            current_stage="init",
            mode_payload=ValidatePayload.build(),
        )

        try:
            # 1 — Idea Intake
            self._emit(on_stage, 1, "Normalizing Idea...")
            idea_profile = await self._intake.analyze(request.model_dump())
            self._save(state, "idea_profile.json",
                       json.dumps(idea_profile, indent=2, ensure_ascii=False))
            state.mode_payload["idea_profile"] = idea_profile
            self._advance(state, "idea_intake")

            # 2 — Problem & Market
            self._emit(on_stage, 2, "Assessing Problem & Market...")
            problem_market = await self._problem.analyze(idea_profile)
            self._save(state, "market_problem.md", _md("Problem & Market", problem_market))
            state.mode_payload["problem_market"] = problem_market
            self._advance(state, "problem_market")

            # 3 — Competitors
            self._emit(on_stage, 3, "Mapping Competitors...")
            competitors = await self._competitor.analyze(idea_profile, problem_market)
            self._save(state, "competitors.md", _md("Competitive Landscape", competitors))
            state.mode_payload["competitors"] = competitors
            self._advance(state, "competitors")

            # 4 — Technical Feasibility
            self._emit(on_stage, 4, "Evaluating Technical Feasibility...")
            tech = await self._tech.analyze(idea_profile, problem_market, competitors)
            self._save(state, "technical_feasibility.md",
                       _md("Technical Feasibility", tech))
            state.mode_payload["technical_feasibility"] = tech
            self._advance(state, "technical_feasibility")

            # 5 — Contrarian Risk
            self._emit(on_stage, 5, "Running Contrarian Risk Analysis...")
            risks = await self._contrarian.analyze(
                idea_profile, problem_market, competitors, tech
            )
            self._save(state, "risks_contrarian.md", _md("Contrarian Risks", risks))
            state.mode_payload["risks_contrarian"] = risks
            self._advance(state, "risks_contrarian")

            # Lacunas de evidência + hipóteses (derivadas)
            evidence_gaps = list(idea_profile.get("gaps", [])) + list(
                problem_market.get("inferences", [])
            )
            state.mode_payload["evidence_gaps"] = evidence_gaps
            state.mode_payload["hypotheses"] = [
                {"hypothesis": gap, "status": "untested"} for gap in evidence_gaps
            ]

            # 6 — Experiment Design
            self._emit(on_stage, 6, "Designing Experiments...")
            exp = await self._experiments.analyze(idea_profile, problem_market, evidence_gaps)
            self._save(state, "experiments.md", _md("Validation Experiments", exp))
            state.mode_payload["experiments"] = exp["experiments"]
            self._advance(state, "experiments")

            # 7 — Synthesis
            self._emit(on_stage, 7, "Synthesizing Verdict...")
            all_stages = {
                "idea_profile": idea_profile,
                "problem_market": problem_market,
                "competitors": competitors,
                "technical_feasibility": tech,
                "risks_contrarian": risks,
                "experiments": exp["experiments"],
                "evidence_gaps": evidence_gaps,
            }
            rec = await self._synth.synthesize(all_stages)
            verdict = rec.get("verdict") or self._config.VALIDATE_DEFAULT_VERDICT_IF_UNCERTAIN
            rec["verdict"] = verdict
            state.mode_payload["recommendation"] = rec
            state.mode_payload["final_report"] = rec.get("final_report", "")
            self._save(state, "validation_report.md", rec.get("final_report", ""))
            self._advance(state, "report")

            state.status = MissionStatus.COMPLETED

        except Exception as exc:
            state.status = MissionStatus.FAILED
            error_msg = f"{type(exc).__name__}: {exc}"
            state.mode_payload["error"] = error_msg
            state.mode_payload["error_stage"] = state.current_stage
            self._save_failure_report(state, error_msg)
        finally:
            state.updated_at = _utcnow()
            self._artifacts.save_mission_state(state)

        return state