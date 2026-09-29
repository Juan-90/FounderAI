"""
ValidatePipeline — orquestrador do Modo VALIDATE (v4.4.0 + erros detalhados).

v4.4.0 hotfix:
  • Cada agente roda em _run_stage com try/except que imprime no console Rich
    "⚠️  Erro no estágio <Agente>: <detalhes>" e propaga para o handler de run.
  • O handler de run grava a mensagem exata em mode_payload["error"],
    mode_payload["final_report"] e validation_report.md.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

from rich.console import Console

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

console = Console(stderr=True)

StageCallback = Callable[[int, str], None]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _md(title: str, data: dict[str, Any]) -> str:
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
    """Orquestra os 7 estágios do Modo VALIDATE com erros detalhados."""

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

    async def _run_stage(
        self,
        on_stage: Optional[StageCallback],
        index: int,
        label: str,
        agent_name: str,
        coro: Coroutine[Any, Any, Any],
    ) -> Any:
        """Executa um agente com try/except detalhado (log + propagação)."""
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
            mission_id=uuid.uuid4().hex,
            project_id=uuid.uuid4().hex,
            mode=ProjectMode.VALIDATE,
            status=MissionStatus.IN_PROGRESS,
            current_stage="init",
            mode_payload=ValidatePayload.build(),
        )

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
            self._save(state, "market_problem.md", _md("Problem & Market", problem_market))
            state.mode_payload["problem_market"] = problem_market
            self._advance(state, "problem_market")

            # 3 — Competitors
            competitors = await self._run_stage(
                on_stage, 3, "Mapping Competitors...", "CompetitorAgent",
                self._competitor.analyze(idea_profile, problem_market),
            )
            self._save(state, "competitors.md", _md("Competitive Landscape", competitors))
            state.mode_payload["competitors"] = competitors
            self._advance(state, "competitors")

            # 4 — Technical Feasibility
            tech = await self._run_stage(
                on_stage, 4, "Evaluating Technical Feasibility...", "TechnicalFeasibilityAgent",
                self._tech.analyze(idea_profile, problem_market, competitors),
            )
            self._save(state, "technical_feasibility.md", _md("Technical Feasibility", tech))
            state.mode_payload["technical_feasibility"] = tech
            self._advance(state, "technical_feasibility")

            # 5 — Contrarian Risk
            risks = await self._run_stage(
                on_stage, 5, "Running Contrarian Risk Analysis...", "ContrarianRiskAgent",
                self._contrarian.analyze(idea_profile, problem_market, competitors, tech),
            )
            self._save(state, "risks_contrarian.md", _md("Contrarian Risks", risks))
            state.mode_payload["risks_contrarian"] = risks
            self._advance(state, "risks_contrarian")

            # Lacunas de evidência + hipóteses
            evidence_gaps = list(idea_profile.get("gaps", [])) + list(
                problem_market.get("inferences", [])
            )
            state.mode_payload["evidence_gaps"] = evidence_gaps
            state.mode_payload["hypotheses"] = [
                {"hypothesis": gap, "status": "untested"} for gap in evidence_gaps
            ]

            # 6 — Experiment Design
            exp = await self._run_stage(
                on_stage, 6, "Designing Experiments...", "ExperimentDesignAgent",
                self._experiments.analyze(idea_profile, problem_market, evidence_gaps),
            )
            self._save(state, "experiments.md", _md("Validation Experiments", exp))
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
            state.mode_payload["final_report"] = (
                f"# Validation Report (FALHA)\n\n## Erro\n```\n{error_msg}\n```\n"
            )
            self._save_failure_report(state, error_msg)
        finally:
            state.updated_at = _utcnow()
            self._artifacts.save_mission_state(state)

        return state