"""
TDDLoop / SelfHealingRunner — orquestrador Sandbox + QAAgent (v4.0 Fase B).

Fluxo (assíncrono no LLM, síncrono na sandbox):
  • Baseline (tentativa 0): source + tests (gerados se ausentes) → Sandbox;
  • Loop de auto-correção (1..max_retries): analyze_failure → generate_fix → Sandbox;
  • Escalação: limite atingido sem sucesso → TDDResult(escalated=True).

O runner Docker é síncrono (subprocess); o QAAgent é async (LLMClient).
Desacoplado do Council: depende apenas de backend.sandbox e backend.qa.agent.
"""

from __future__ import annotations

from backend.core.config import Settings, settings
from backend.qa.agent import QAAgent
from backend.qa.schemas import TDDAttempt, TDDRequest, TDDResult
from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.sandbox.models import SandboxInput, SandboxOutput
from backend.sandbox.runner import SandboxRunner


class TDDLoop:
    """Orquestra o ciclo TDD self-healing sobre a sandbox isolada."""

    def __init__(
        self,
        runner: SandboxRunner | None = None,
        agent: QAAgent | None = None,
        config: Settings | None = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._runner: SandboxRunner = (
            runner if runner is not None else DockerSandboxRunner(self._config)
        )
        self._agent: QAAgent = agent if agent is not None else QAAgent()

    # ── Helpers ──
    @staticmethod
    def _is_success(output: SandboxOutput) -> bool:
        return (
            output.exit_code == 0
            and not output.timed_out
            and output.error is None
        )

    def _execute(
        self,
        source_files: dict[str, str],
        test_files: dict[str, str],
        request: TDDRequest,
    ) -> SandboxOutput:
        files = {**source_files, **test_files}
        sbx_input = SandboxInput(
            files=files,
            command=request.entry_command,
            timeout_seconds=self._config.SANDBOX_TIMEOUT_SECONDS,
            max_output_bytes=self._config.SANDBOX_MAX_OUTPUT_BYTES,
        )
        return self._runner.run(sbx_input)

    # ── Ciclo principal (async) ──
    async def run(self, request: TDDRequest) -> TDDResult:
        """Executa baseline + loop de auto-correção com teto de retries."""
        source = dict(request.source_files)
        tests = (
            dict(request.test_files)
            if request.test_files
            else await self._agent.generate_tests(source, request.goal)
        )

        attempts: list[TDDAttempt] = []

        # ── Baseline (tentativa 0) ──
        baseline = self._execute(source, tests, request)
        attempts.append(
            TDDAttempt(
                attempt_number=0,
                source_code=dict(source),
                tests_code=dict(tests),
                sandbox_result=baseline,
            )
        )
        if self._is_success(baseline):
            return TDDResult(
                success=True,
                final_source_code=source,
                final_tests_code=tests,
                attempts=attempts,
                final_sandbox_result=baseline,
                escalated=False,
                summary="Sucesso na baseline (tentativa 0).",
            )

        # ── Loop de auto-correção (1..max_retries) ──
        last = baseline
        for number in range(1, request.max_retries + 1):
            analysis = await self._agent.analyze_failure(source, tests, last)
            source, tests, patch_summary = await self._agent.generate_fix(
                source, tests, analysis
            )
            last = self._execute(source, tests, request)
            attempts.append(
                TDDAttempt(
                    attempt_number=number,
                    source_code=dict(source),
                    tests_code=dict(tests),
                    sandbox_result=last,
                    analysis=analysis,
                    patch_summary=patch_summary,
                )
            )
            if self._is_success(last):
                return TDDResult(
                    success=True,
                    final_source_code=source,
                    final_tests_code=tests,
                    attempts=attempts,
                    final_sandbox_result=last,
                    escalated=False,
                    summary=f"Sucesso após {number} tentativa(s) de auto-correção.",
                )

        # ── Escalação ──
        return TDDResult(
            success=False,
            final_source_code=source,
            final_tests_code=tests,
            attempts=attempts,
            final_sandbox_result=last,
            escalated=True,
            summary=(
                f"Falha persistente após {request.max_retries} tentativas "
                "de auto-correção. Escalado para revisão humana."
            ),
        )


# Alias de legibilidade da spec
SelfHealingRunner = TDDLoop