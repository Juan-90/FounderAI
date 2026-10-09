"""
ImproveDiagnoser — diagnóstico determinístico sobre a memória do projeto (v5.4.0).

Analisa:
  • eventos BUILD_FAILED / ESCALATED (falhas recorrentes por mensagem);
  • learnings qa_failure / validation_risk (citados explicitamente);
  • gaps em relação ao goal informado vs current_goal;
  • versões MAIS RECENTES dos artefatos-chave (requirements, architecture,
    code_bundle, test_report) como base reutilizável.

Sem LLM: heurísticas puras e reproduzíveis (mesma memória → mesmo diagnóstico).
Classificação de risco:
  high   -> algum ESCALATED, ou >=2 falhas, ou >=3 riscos;
  medium -> 1 falha, ou qualquer learning de QA/risco;
  low    -> demais casos.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Optional

from backend.domain.improve import ImproveDiagnosis, RiskLevel
from backend.domain.memory import ArtifactKind, MemoryEventType, ProjectMemory

_KEY_KINDS = (
    ArtifactKind.REQUIREMENTS,
    ArtifactKind.ARCHITECTURE,
    ArtifactKind.CODE_BUNDLE,
    ArtifactKind.TEST_REPORT,
)

_SPACE_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _SPACE_RE.sub(" ", (text or "").lower()).strip()


class ImproveDiagnoser:
    """Produz ImproveDiagnosis a partir de um ProjectMemory."""

    def diagnose(
        self, project_memory: ProjectMemory, goal: Optional[str] = None
    ) -> ImproveDiagnosis:
        issues: list[str] = []

        # 1 — Falhas recorrentes (eventos)
        failure_events = [
            e for e in project_memory.events
            if e.type in (MemoryEventType.BUILD_FAILED, MemoryEventType.ESCALATED)
        ]
        counts = Counter(_norm(e.message) for e in failure_events)
        recurring = [(msg, n) for msg, n in counts.items() if n >= 2]
        for msg, n in sorted(recurring, key=lambda kv: kv[1], reverse=True):
            issues.append(f"Falha recorrente ({n}x): {msg}")
        if not recurring and failure_events:
            issues.append(f"Falha registrada: {failure_events[-1].message}")

        # 2 — Learnings de QA e riscos (citação explícita)
        qa_learnings = [l for l in project_memory.learnings if l.source == "qa_failure"]
        risk_learnings = [l for l in project_memory.learnings if l.source == "validation_risk"]
        leveraged_learnings = [l.text for l in qa_learnings + risk_learnings]
        for l in qa_learnings:
            issues.append(f"QA: {l.text}")
        for l in risk_learnings[:3]:
            issues.append(f"Risco: {l.text}")

        # 3 — Gaps em relação ao goal
        if goal:
            current = project_memory.current_goal or ""
            if _norm(current) != _norm(goal):
                issues.append(
                    f"Gap de goal: projeto mira '{current or '(nenhum)'}', "
                    f"novo goal '{goal}'."
                )
        elif not project_memory.current_goal:
            issues.append("Projeto sem goal definido — melhoria sem norte.")

        # 4 — Artefatos-chave reutilizáveis (versão mais recente por kind)
        leveraged_artifacts: list[str] = []
        for kind in _KEY_KINDS:
            latest = max(
                (v for v in project_memory.artifact_versions if v.kind == kind),
                key=lambda v: v.created_at,
                default=None,
            )
            if latest is not None:
                leveraged_artifacts.append(latest.path)
        if not leveraged_artifacts:
            issues.append("Sem artefatos versionados — primeira melhoria do projeto.")

        # 5 — Nível de risco
        escalated = any(e.type == MemoryEventType.ESCALATED for e in project_memory.events)
        n_fail = len(failure_events)
        n_risk = len(risk_learnings)
        risk: RiskLevel
        if escalated or n_fail >= 2 or n_risk >= 3:
            risk = "high"
        elif n_fail == 1 or qa_learnings or risk_learnings:
            risk = "medium"
        else:
            risk = "low"

        summary = (
            f"Projeto '{project_memory.name}': {n_fail} falha(s), "
            f"{len(qa_learnings)} learning(s) de QA, {n_risk} risco(s), "
            f"{len(leveraged_artifacts)} artefato(s) reutilizável(is); risco {risk}."
        )
        return ImproveDiagnosis(
            summary=summary,
            top_issues=issues,
            leveraged_learnings=leveraged_learnings,
            leveraged_artifacts=leveraged_artifacts,
            risk_level=risk,
        )