"""
TDDLoop — orquestrador self-healing (v4.1 + v4.3 repasse de env).
"""

from __future__ import annotations

from backend.analysis.static_gate import StaticAnalysisGate
from backend.core.config import Settings, settings
from backend.notifications.models import EscalationPayload
from backend.notifications.webhook import EscalationNotifier
from backend.qa.agent import QAAgent
from backend.qa.schemas import TDDAttempt, TDDRequest, TDDResult
from backend.sandbox.docker_runner import DockerSandboxRunner
from backend.sandbox.models import SandboxInput, SandboxOutput
from backend.sandbox.runner import SandboxRunner

_TAIL_CHARS: int = 500


class TDDLoop:
    def __init__(
        self,
        runner: SandboxRunner | None = None,
        agent: QAAgent | None = None,
        config: Settings | None = None,
        static_gate: StaticAnalysisGate | None = None,
        notifier: EscalationNotifier | None = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._runner: SandboxRunner = runner if runner is not None else DockerSandboxRunner(self._config)
        self._agent: QAAgent = agent if agent is not None else QAAgent()
        self._static_gate: StaticAnalysisGate = (
            static_gate if static_gate is not None else StaticAnalysisGate()
        )
        self._notifier: EscalationNotifier = (
            notifier if notifier is not None else EscalationNotifier(self._config)
        )

    @staticmethod
    def _is_success(output: SandboxOutput) -> bool:
        return output.exit_code == 0 and not output.timed_out and output.error is None

    def _execute(self, source_files, test_files, request: TDDRequest) -> SandboxOutput:
        files = {**source_files, **test_files}
        sbx_input = SandboxInput(
            files=files,
            command=request.entry_command,
            timeout_seconds=self._config.SANDBOX_TIMEOUT_SECONDS,
            max_output_bytes=self._config.SANDBOX_MAX_OUTPUT_BYTES,
            env=dict(request.env),
        )
        return self._runner.run(sbx_input)

    async def _notify_escalation(self, request: TDDRequest, result: TDDResult) -> None:
        if not self._config.ESCALATION_WEBHOOK_ENABLED:
            return
        last = result.final_sandbox_result
        payload = EscalationPayload(
            event="tdd_loop.escalated",
            project_name=self._config.app_name,
            mission_id=request.mission_id or "n/a",
            goal=request.goal,
            attempts=len(result.attempts),
            max_retries=request.max_retries,
            final_summary=result.summary,
            last_error=(last.stderr[-_TAIL_CHARS:] if last and last.stderr else None),
            stdout_tail=(last.stdout[-_TAIL_CHARS:] if last else ""),
            stderr_tail=(last.stderr[-_TAIL_CHARS:] if last else ""),
        )
        try:
            await self._notifier.notify(payload)
        except Exception:
            pass

    async def run(self, request: TDDRequest) -> TDDResult:
        source = dict(request.source_files)
        tests = (
            dict(request.test_files)
            if request.test_files
            else await self._agent.generate_tests(source, request.goal)
        )

        static_passed: bool | None = None
        if self._config.STATIC_ANALYSIS_ENABLED:
            gate_result = self._static_gate.run({**source, **tests})
            static_passed = gate_result.passed
            cycles = 0
            while not gate_result.passed and cycles < self._config.STATIC_ANALYSIS_MAX_CYCLES:
                source, tests, _p = await self._agent.generate_fix(source, tests, gate_result.summary)
                gate_result = self._static_gate.run({**source, **tests})
                static_passed = gate_result.passed
                cycles += 1
            if not gate_result.passed:
                return TDDResult(
                    success=False, final_source_code=source, final_tests_code=tests,
                    attempts=[], final_sandbox_result=None, escalated=False,
                    static_gate_passed=False, failure_stage="static_gate",
                    summary=f"Falha estática persistente após {cycles} ciclo(s): {gate_result.summary}",
                )

        attempts: list[TDDAttempt] = []
        baseline = self._execute(source, tests, request)
        attempts.append(TDDAttempt(attempt_number=0, source_code=dict(source),
                                   tests_code=dict(tests), sandbox_result=baseline))
        if self._is_success(baseline):
            return TDDResult(success=True, final_source_code=source, final_tests_code=tests,
                             attempts=attempts, final_sandbox_result=baseline, escalated=False,
                             static_gate_passed=static_passed,
                             summary="Sucesso na baseline (tentativa 0).")

        last = baseline
        for number in range(1, request.max_retries + 1):
            analysis = await self._agent.analyze_failure(source, tests, last)
            source, tests, patch_summary = await self._agent.generate_fix(source, tests, analysis)
            last = self._execute(source, tests, request)
            attempts.append(TDDAttempt(attempt_number=number, source_code=dict(source),
                                       tests_code=dict(tests), sandbox_result=last,
                                       analysis=analysis, patch_summary=patch_summary))
            if self._is_success(last):
                return TDDResult(success=True, final_source_code=source, final_tests_code=tests,
                                 attempts=attempts, final_sandbox_result=last, escalated=False,
                                 static_gate_passed=static_passed,
                                 summary=f"Sucesso após {number} tentativa(s) de auto-correção.")

        result = TDDResult(success=False, final_source_code=source, final_tests_code=tests,
                           attempts=attempts, final_sandbox_result=last, escalated=True,
                           static_gate_passed=static_passed, failure_stage="sandbox",
                           summary=(f"Falha persistente após {request.max_retries} tentativas "
                                    "de auto-correção. Escalado para revisão humana."))
        await self._notify_escalation(request, result)
        return result


SelfHealingRunner = TDDLoop