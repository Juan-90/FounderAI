"""
QA & Loop TDD Autônomo — FounderAI v4.0 Fase B (Bloco 1).

Pacote autônomo: orquestra sandbox isolada + agente de QA em um ciclo
self-healing com teto estrito de retries e escalação explícita.
"""

from backend.qa.agent import LLMJsonClient, QAAgent, QAAgentError
from backend.qa.orchestrator import SelfHealingRunner, TDDLoop
from backend.qa.schemas import TDDAttempt, TDDRequest, TDDResult

__all__ = [
    "LLMJsonClient",
    "QAAgent",
    "QAAgentError",
    "SelfHealingRunner",
    "TDDAttempt",
    "TDDLoop",
    "TDDRequest",
    "TDDResult",
]