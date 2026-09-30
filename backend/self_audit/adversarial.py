"""
AdversarialAuditor — regra Creator ≠ Auditor (v4.6.0).

Tenta auditar com um provedor/modelo DIFERENTE do usado na execução
(primário). Se não houver segundo provedor disponível/ativo, marca
adversarial_degraded=True e aplica checagens heurísticas locais
(overclaim, incoerência evidência↔veredito, riscos/lacunas óbvias).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from backend.core.config import Settings, settings
from backend.self_audit.schemas import AdversarialReview, AuditMissionResult

ClientFactory = Callable[[str], Any]


class AdversarialAuditor:
    """Auditor adversarial com fallback heurístico determinístico."""

    def __init__(
        self,
        config: Settings | None = None,
        client_factory: Optional[ClientFactory] = None,
    ) -> None:
        self._config = config if config is not None else settings
        self._client_factory = client_factory

    def _secondary_provider(self) -> tuple[str, bool]:
        primary = self._config.PRIMARY_PROVIDER
        fallback = self._config.FALLBACK_PROVIDER
        candidate = (
            fallback if fallback != primary
            else ("local" if primary != "local" else "groq")
        )
        available = (candidate == "local") or bool(
            (self._config.api_key_for(candidate) or "").strip()
        )
        return candidate, available

    def _make_client(self, candidate: str) -> Any:
        from backend.core.llm_client import LLMClient
        overrides = self._config.model_dump()
        overrides["PRIMARY_PROVIDER"] = candidate
        overrides["FALLBACK_PROVIDER"] = candidate
        return LLMClient(Settings(**overrides))

    def _heuristics(self, results: list[AuditMissionResult]) -> AdversarialReview:
        findings: list[str] = []
        for r in results:
            if r.success and r.objective_checks and any(
                not v for v in r.objective_checks.values()
            ):
                findings.append(
                    f"incoerencia: '{r.mission_name}' success=True mas há check objetivo falho"
                )
            if r.success and not r.objective_checks:
                findings.append(f"overclaim: '{r.mission_name}' success=True sem checks objetivos")
            if (not r.success) and r.error is None:
                findings.append(f"lacuna: '{r.mission_name}' falhou sem erro registrado")
        return AdversarialReview(
            findings=findings,
            severity_counts={"critical": 0, "major": len(findings), "minor": 0},
            overclaim_detected=any(f.startswith("overclaim") for f in findings),
            consistency_score=0.6 if findings else 1.0,
            notes="Auditor degradado: checagens heurísticas locais (sem LLM).",
            adversarial_degraded=True,
        )

    async def audit(
        self,
        results: list[AuditMissionResult],
        audit_dir: Optional[Path] = None,
    ) -> AdversarialReview:
        candidate, available = self._secondary_provider()
        if not available:
            return self._heuristics(results)
        try:
            client = (
                self._client_factory(candidate)
                if self._client_factory is not None
                else self._make_client(candidate)
            )
            data = await client.complete_json(
                system_prompt=(
                    "Você é um auditor adversarial cético, DIFERENTE do criador dos "
                    "relatórios. Aponte overclaim, incoerência entre evidências e "
                    "veredito, e riscos óbvios omitidos. Responda APENAS JSON válido."
                ),
                user_prompt=(
                    "RESULTADOS DA AUTO-AUDITORIA:\n"
                    + json.dumps([r.model_dump() for r in results], ensure_ascii=False)
                    + '\n\nRetorne: {"findings": ["..."], "severity_counts": '
                    '{"critical": 0, "major": 0, "minor": 0}, "overclaim_detected": '
                    'false, "consistency_score": 0.0-1.0, "notes": "..."}'
                ),
            )
            return AdversarialReview(
                findings=list(data.get("findings", [])),
                severity_counts={
                    k: int(v) for k, v in (data.get("severity_counts") or {}).items()
                },
                overclaim_detected=bool(data.get("overclaim_detected", False)),
                consistency_score=float(data.get("consistency_score", 1.0)),
                notes=str(data.get("notes", "")),
                adversarial_degraded=False,
            )
        except Exception as exc:
            review = self._heuristics(results)
            review.notes = f"Auditor LLM ({candidate}) falhou; heurísticas aplicadas. {exc}"
            return review