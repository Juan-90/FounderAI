"""
Modo IMPROVE do FounderAI (v5.4.0).

Diagnóstico → Plano → Aplicação com confirmação, alimentados pela memória
do projeto (eventos, learnings, decisões e versões de artefatos).
"""

from backend.core.improve.diagnoser import ImproveDiagnoser

__all__ = ["ImproveDiagnoser"]