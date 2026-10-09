"""
ImprovePatcher + ImproveQualityRunner (v5.4.0).

Patcher: aplica propostas de um generator injetável (Protocol) sobre o bundle
atual, com limite ESTRITO de arquivos alterados (max_files_touched). Ignora
no-ops (conteúdo idêntico) e marca `truncated` quando trava no limite.

QualityRunner: reutiliza StaticAnalysisGate + TDDLoop (sandbox). Static gate
falhou -> passed=False. TDD passou -> autoriza. TDD falhou após max_retries ->
escalated=True + motivo registrado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from backend.analysis.static_gate import StaticAnalysisGate
from backend.domain.improve import ImprovePlan, ImprovePlanItem
from backend.qa.schemas import TDDRequest


class PatchGeneratorLike(Protocol):
    """Contrato de um gerador de propostas de patch (LLM em produção)."""

    def generate(self, item: ImprovePlanItem, bundle: dict[str, str]) -> dict[str, str]: ...


class StaticGateLike(Protocol):
    def run(self, files: dict[str, str]) -> object: ...


class TDDRunnerLike(Protocol):
    async def run(self, request: TDDRequest) -> object: ...


@dataclass
class ImproveQualityResult:
    passed: bool
    escalated: bool
    reason: str
    attempts: int = 0
    tdd_summary: Optional[str] = None


class ImprovePatcher:
    """Gera o patch {path: content} respeitando max_files."""

    def __init__(self, generator: Optional[PatchGeneratorLike] = None) -> None:
        self._generator = generator
        self.truncated = False
        self.warnings: list[str] = []

    def generate_patch(
        self,
        plan: ImprovePlan,
        current_code_bundle: dict[str, str],
        max_files: int = 8,
    ) -> dict[str, str]:
        patch: dict[str, str] = {}
        for item in plan.items:
            if len(patch) >= max_files:
                self.truncated = True
                self.warnings.append(
                    f"Limite de {max_files} arquivos atingido; propostas restantes descartadas."
                )
                break
            proposals = (
                self._generator.generate(item, {**current_code_bundle, **patch})
                if self._generator is not None else {}
            )
            for path, content in proposals.items():
                if len(patch) >= max_files:
                    self.truncated = True
                    self.warnings.append(f"Limite de {max_files} arquivos atingido em '{path}'.")
                    break
                if current_code_bundle.get(path) == content:
                    continue  # no-op: não conta como alteração
                patch[path] = content
        return patch


class ImproveQualityRunner:
    """Valida o patch via StaticAnalysisGate + TDDLoop (sandbox)."""

    def __init__(
        self,
        static_gate: Optional[StaticGateLike] = None,
        tdd_loop: Optional[TDDRunnerLike] = None,
    ) -> None:
        self._gate: StaticGateLike = static_gate if static_gate is not None else StaticAnalysisGate()
        self._tdd: TDDRunnerLike = tdd_loop if tdd_loop is not None else _default_tdd()

    async def run(
        self,
        patch: dict[str, str],
        source_files: dict[str, str],
        test_files: dict[str, str],
        goal: str,
        max_retries: int = 2,
    ) -> ImproveQualityResult:
        merged = {**source_files, **patch}

        static = self._gate.run({**merged, **test_files})
        if not getattr(static, "passed", False):
            return ImproveQualityResult(
                passed=False, escalated=False,
                reason=f"Static gate reprovou: {getattr(static, 'summary', '')}",
                attempts=0, tdd_summary=None,
            )

        attempts = 0
        last = None
        for _ in range(max_retries + 1):
            attempts += 1
            last = await self._tdd.run(TDDRequest(
                source_files=merged, test_files=test_files, goal=goal,
            ))
            if getattr(last, "success", False):
                return ImproveQualityResult(
                    passed=True, escalated=False, reason="",
                    attempts=attempts, tdd_summary=getattr(last, "summary", None),
                )
        return ImproveQualityResult(
            passed=False, escalated=True,
            reason=f"TDD falhou após {attempts} tentativa(s): {getattr(last, 'summary', '')}",
            attempts=attempts, tdd_summary=getattr(last, "summary", None),
        )


def _default_tdd() -> TDDRunnerLike:
    from backend.qa.orchestrator import TDDLoop
    from backend.core.config import settings
    return TDDLoop(config=settings)