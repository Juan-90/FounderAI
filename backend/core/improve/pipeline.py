"""
ImprovePipeline — orquestração completa do modo IMPROVE (v5.4.0).

Fluxo:
  1. Carrega ProjectMemory (DiskProjectMemoryStore).
  2. ImproveDiagnoser -> ImprovePlanner.
  3. Gate humano: se (requires_confirmation and not auto_apply) OU risco
     medium/high -> waiting_human=True, salva rascunho do plano e interrompe
     ANTES de modificar código.
  4. Aprovado/auto-apply: ImprovePatcher -> Quality Gate (Static + TDDLoop).
  5. Relatório consolidado em
     artifacts/projects/<project_id>/versions/reports/improve_<vid>.md.

Persistência de memória:
  • Sucesso: evento IMPROVED + ArtifactVersion (code_bundle, relatório, tdd)
    + MemoryLearning por item (correção -> impacto verificado).
  • Falha/escalado: evento BUILD_FAILED/ESCALATED + learning do erro.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from backend.core.config import Settings, settings
from backend.core.improve.diagnoser import ImproveDiagnoser
from backend.core.improve.patcher import (
    ImprovePatcher,
    ImproveQualityResult,
    ImproveQualityRunner,
)
from backend.core.improve.planner import ImprovePlanner
from backend.domain.improve import (
    ImproveDiagnosis,
    ImprovePlan,
    ImproveRequest,
    ImproveResult,
)
from backend.domain.memory import ArtifactKind, MemoryEventType, ProjectMemory
from backend.domain.memory_store import DiskProjectMemoryStore


class ImprovePipeline:
    def __init__(
        self,
        store: Optional[DiskProjectMemoryStore] = None,
        config: Optional[Settings] = None,
        diagnoser: Optional[ImproveDiagnoser] = None,
        planner: Optional[ImprovePlanner] = None,
        patcher: Optional[ImprovePatcher] = None,
        quality_runner: Optional[ImproveQualityRunner] = None,
        initial_bundle: Optional[dict[str, str]] = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._store = store or DiskProjectMemoryStore(
            base_dir=Path(self._config.PROJECT_MEMORY_DIR)
        )
        self._diagnoser = diagnoser or ImproveDiagnoser()
        self._planner = planner or ImprovePlanner()
        self._patcher = patcher or ImprovePatcher()
        self._quality = quality_runner or ImproveQualityRunner()
        self._initial_bundle = initial_bundle

    # ── helpers ──
    def _versions_root(self, project_id: str) -> Path:
        return Path(self._config.PROJECT_MEMORY_DIR) / project_id / "versions"

    def _load_bundle(self, memory: ProjectMemory) -> dict[str, str]:
        if self._initial_bundle is not None:
            return dict(self._initial_bundle)
        latest = max(
            (v for v in memory.artifact_versions if v.kind == ArtifactKind.CODE_BUNDLE),
            key=lambda v: v.created_at, default=None,
        )
        if latest is None:
            return {}
        p = Path(latest.path)
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _split(bundle: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
        tests = {k: v for k, v in bundle.items() if Path(k).name.startswith("test_")}
        sources = {k: v for k, v in bundle.items() if not Path(k).name.startswith("test_")}
        return sources, tests

    def _save_text(self, project_id: str, rel: str, name: str, content: str) -> Path:
        d = self._versions_root(project_id) / rel
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_text(content, encoding="utf-8")
        return p

    def _report_md(
        self, memory: ProjectMemory, diagnosis: ImproveDiagnosis, plan: ImprovePlan,
        quality: Optional[ImproveQualityResult], changed: list[str], applied: bool,
    ) -> str:
        lines = [f"# Improve Report — {memory.name}", "", "## Diagnóstico", diagnosis.summary, "", "## Plano"]
        for i, it in enumerate(plan.items, 1):
            lines.append(f"{i}. {it.title} ({it.risk_level}) — {it.expected_impact}")
        lines += ["", "## Quality Gate"]
        if quality is None:
            lines.append("- (não executado — aguardando confirmação)")
        else:
            lines += [f"- passed: {quality.passed}", f"- escalated: {quality.escalated}",
                      f"- attempts: {quality.attempts}"]
            if quality.reason:
                lines.append(f"- reason: {quality.reason}")
        lines += ["", "## Arquivos alterados"]
        lines += [f"- {c}" for c in changed] if changed else ["- (nenhum)"]
        lines += ["", "## Status", "APLICADO" if applied else "NÃO APLICADO"]
        return "\n".join(lines) + "\n"

    # ── fluxo principal ──
    async def execute(self, request: ImproveRequest) -> ImproveResult:
        memory = self._store.get(request.project_id)
        if memory is None:
            return ImproveResult(
                success=False,
                diagnosis=ImproveDiagnosis(summary="Projeto não encontrado.", risk_level="low"),
                plan=ImprovePlan(items=[], overall_risk="low", requires_confirmation=False),
                summary="Projeto não encontrado.",
            )

        diagnosis = self._diagnoser.diagnose(memory, goal=request.goal)
        plan = self._planner.plan(diagnosis, request)
        vid = uuid.uuid4().hex

        # 3 — Gate humano (interrompe ANTES de modificar)
        interrupt = plan.requires_confirmation and not request.auto_apply
        if interrupt:
            draft = self._save_text(
                memory.project_id, "reports", f"improve_plan_draft_{vid}.md",
                self._report_md(memory, diagnosis, plan, None, [], False),
            )
            return ImproveResult(
                success=False, diagnosis=diagnosis, plan=plan,
                report_path=str(draft), waiting_human=True,
                summary="Plano aguardando confirmação humana.",
            )

        # 4 — Patch + Quality Gate
        bundle = self._load_bundle(memory)
        sources, tests = self._split(bundle)
        patch = self._patcher.generate_patch(plan, bundle, max_files=request.max_files_touched)
        quality = await self._quality.run(
            patch, source_files=sources, test_files=tests,
            goal=request.goal or memory.current_goal or memory.name,
        )
        changed = list(patch.keys())

        if quality.passed:
            applied = {**bundle, **patch}
            bundle_path = self._save_text(
                memory.project_id, "code_bundle", f"code_bundle_{vid}.json",
                json.dumps(applied, indent=2, ensure_ascii=False),
            )
            report_path = self._save_text(
                memory.project_id, "reports", f"improve_{vid}.md",
                self._report_md(memory, diagnosis, plan, quality, changed, True),
            )
            tdd_path = self._save_text(
                memory.project_id, "reports", f"tdd_{vid}.md", quality.tdd_summary or "TDD ok",
            )
            self._store.append_event(
                memory.project_id, MemoryEventType.IMPROVED,
                f"Melhoria aplicada ({len(changed)} arquivo(s))", mission_id=vid,
            )
            self._store.add_artifact_version(
                memory.project_id, ArtifactKind.CODE_BUNDLE, str(bundle_path),
                mission_id=vid, summary="code bundle pós-melhoria",
            )
            self._store.add_artifact_version(
                memory.project_id, ArtifactKind.COMPOSITE_REPORT, str(report_path),
                mission_id=vid, summary="relatório improve",
            )
            self._store.add_artifact_version(
                memory.project_id, ArtifactKind.TEST_REPORT, str(tdd_path),
                mission_id=vid, summary="tdd pós-melhoria",
            )
            for it in plan.items:
                self._store.add_learning(
                    memory.project_id, f"{it.title} -> {it.expected_impact}",
                    "other", mission_id=vid,
                )
            return ImproveResult(
                success=True, diagnosis=diagnosis, plan=plan, changed_files=changed,
                tdd_result={"passed": True, "attempts": quality.attempts},
                report_path=str(report_path), escalated=False, waiting_human=False,
                summary=f"Melhoria aplicada em {len(changed)} arquivo(s).",
            )

        # Falha / escalado
        report_path = self._save_text(
            memory.project_id, "reports", f"improve_{vid}.md",
            self._report_md(memory, diagnosis, plan, quality, changed, False),
        )
        evt = MemoryEventType.ESCALATED if quality.escalated else MemoryEventType.BUILD_FAILED
        self._store.append_event(
            memory.project_id, evt, f"Melhoria falhou: {quality.reason}", mission_id=vid,
        )
        self._store.add_learning(
            memory.project_id, f"Falha na melhoria: {quality.reason}",
            "qa_failure", mission_id=vid,
        )
        return ImproveResult(
            success=False, diagnosis=diagnosis, plan=plan, changed_files=[],
            tdd_result={"passed": False, "attempts": quality.attempts},
            report_path=str(report_path), escalated=quality.escalated,
            waiting_human=False, summary=f"Melhoria não aplicada: {quality.reason}",
        )