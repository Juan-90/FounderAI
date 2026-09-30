"""
Etapas do Modo DISCOVER (v4.7.0).

ScopeFramer/Ideation usam LLM (injetável). Normalizer/Ranker/Critic são puros
e determinísticos. A ORQUESTRAÇÃO vive em backend/discover/pipeline.py.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from backend.build.agents import LLMBuildClient
from backend.core.llm_client import LLMClient
from backend.discover.schemas import DiscoverRequest, OpportunityProfile

RANKING_METHOD = "weighted_v1"

# Pesos explícitos do ranking (somam 1.0)
RANK_WEIGHTS: dict[str, float] = {
    "dor_percebida": 0.35,
    "viabilidade_mvp": 0.25,
    "potencial_pagamento": 0.25,
    "diferenciacao": 0.15,
}

_PAIN_KEYWORDS = ["dor", "problema", "caro", "lento", "difícil", "dificil",
                  "perde", "prejuizo", "prejuízo", "atraso", "manual", "retrabalho"]

_CLICHES = ["rede social", "uber para", "uber de", "airbnb para", "ia para tudo",
            "ai para tudo", "metaverso", "nft", "blockchain para tudo",
            "plataforma para todos", "solucao generica", "solução genérica"]


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:24] or "opp"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


class ScopeFramerAgent:
    """Etapa 1 — Normaliza tema/público/geografia/restrições/critérios."""

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def frame(self, request: DiscoverRequest) -> dict[str, Any]:
        data = await self._client.complete_json(
            system_prompt=(
                "Você é um estrategista de descoberta de oportunidades. "
                "Responda APENAS JSON válido."
            ),
            user_prompt=(
                f"TEMA: {request.theme}\nPÚBLICO: {request.audience or 'não informado'}\n"
                f"GEOGRAFIA: {request.geography}\nRESTRIÇÕES: {request.constraints}\n"
                'Retorne: {"theme": "...", "audience": "...", "geography": "...", '
                '"constraints": ["..."], "attractiveness_criteria": ["..."]}'
            ),
        )
        return {
            "theme": data.get("theme") or request.theme,
            "audience": data.get("audience") or request.audience,
            "geography": data.get("geography") or request.geography,
            "constraints": list(data.get("constraints") or request.constraints),
            "attractiveness_criteria": list(data.get("attractiveness_criteria") or []),
        }


class OpportunityIdeationAgent:
    """Etapa 2 — Gera 12-16 candidatos brutos (evita ideias genéricas)."""

    def __init__(self, client: LLMBuildClient | None = None) -> None:
        self._client: LLMBuildClient = client if client is not None else LLMClient()

    async def generate(self, scope: dict[str, Any], seeds: list[str]) -> list[dict[str, Any]]:
        data = await self._client.complete_json(
            system_prompt=(
                "Você é um gerador de oportunidades de negócio. Evite clichês e "
                "ideias genéricas vazias. Responda APENAS JSON válido."
            ),
            user_prompt=(
                f"ESCOPO: {json.dumps(scope, ensure_ascii=False)}\nSEEDS: {seeds}\n"
                "Gere de 12 a 16 candidatos. Retorne: "
                '{"candidates": [{"title": "...", "one_liner": "...", "problem": "...", '
                '"audience": "...", "why_now": "...", "solution_sketch": "...", '
                '"business_model_hint": "...", "risks": ["..."], "assumptions": ["..."], '
                '"tags": ["..."]}]}'
            ),
        )
        candidates = data.get("candidates") or []
        return [c for c in candidates if isinstance(c, dict)]


class OpportunityNormalizer:
    """Etapa 3 — Converte candidatos brutos em OpportunityProfile."""

    def normalize(self, raw: list[dict[str, Any]]) -> list[OpportunityProfile]:
        profiles: list[OpportunityProfile] = []
        for i, r in enumerate(raw):
            title = str(r.get("title") or r.get("nome") or "Sem título")
            evidence = r.get("evidence_level")
            profiles.append(OpportunityProfile(
                id=str(r.get("id") or f"opp-{i}-{_slug(title)}"),
                title=title,
                one_liner=str(r.get("one_liner") or r.get("resumo") or ""),
                problem=str(r.get("problem") or r.get("problema") or ""),
                audience=str(r.get("audience") or r.get("publico") or ""),
                why_now=str(r.get("why_now") or r.get("por_que_agora") or ""),
                solution_sketch=str(r.get("solution_sketch") or r.get("solucao") or ""),
                business_model_hint=r.get("business_model_hint"),
                score=0.0,
                score_breakdown={},
                risks=list(r.get("risks") or []),
                assumptions=list(r.get("assumptions") or []),
                evidence_level=evidence if evidence in ("low", "medium", "high") else "low",
                tags=list(r.get("tags") or []),
            ))
        return profiles


class OpportunityRanker:
    """Etapa 4 — Pontua 0.0-1.0 com pesos explícitos em score_breakdown."""

    weights = RANK_WEIGHTS

    def _dims(self, p: OpportunityProfile) -> dict[str, float]:
        dor = _clamp(0.3 + min(0.4, len(p.problem) / 250)
                     + (0.3 if any(k in p.problem.lower() for k in _PAIN_KEYWORDS) else 0.0))
        viab = _clamp(0.4 + (0.3 if p.solution_sketch else 0.0)
                      + (0.3 - min(0.3, 0.05 * len(p.risks))))
        pag = _clamp(0.4 + (0.6 if p.business_model_hint else 0.1))
        dif = _clamp(0.3 + min(0.4, len(p.why_now) / 200) + min(0.3, 0.1 * len(p.tags)))
        return {
            "dor_percebida": round(dor, 3),
            "viabilidade_mvp": round(viab, 3),
            "potencial_pagamento": round(pag, 3),
            "diferenciacao": round(dif, 3),
        }

    def rank(self, profiles: list[OpportunityProfile]) -> list[OpportunityProfile]:
        for p in profiles:
            dims = self._dims(p)
            p.score_breakdown = dims
            p.score = round(sum(self.weights[k] * dims[k] for k in self.weights), 3)
        return sorted(profiles, key=lambda p: p.score, reverse=True)


class OpportunityCritic:
    """Etapa 5 — Contrarian leve: rejeita clichês e duplicatas com motivos."""

    def _is_cliche(self, p: OpportunityProfile) -> Optional[str]:
        blob = f"{p.title} {p.one_liner}".lower()
        for c in _CLICHES:
            if c in blob:
                return f"clichê detectado: '{c}'"
        return None

    def _is_duplicate(self, p: OpportunityProfile, kept: list[OpportunityProfile]) -> Optional[str]:
        np_ = _norm(p.title)
        for k in kept:
            nk = _norm(k.title)
            if not np_ or not nk:
                continue
            if np_ == nk:
                return f"duplicata de '{k.title}'"
            ta, tb = set(np_.split()), set(nk.split())
            inter = len(ta & tb)
            # Contenção: o menor conjunto está >=80% contido no maior
            if inter / min(len(ta), len(tb)) >= 0.8:
                return f"duplicata semântica de '{k.title}'"
        return None

    def critique(
        self, profiles: list[OpportunityProfile]
    ) -> tuple[list[OpportunityProfile], list[dict]]:
        kept: list[OpportunityProfile] = []
        rejected: list[dict] = []
        for p in profiles:
            reason = self._is_cliche(p) or self._is_duplicate(p, kept)
            if reason:
                rejected.append({"id": p.id, "title": p.title, "reason": reason})
            else:
                kept.append(p)
        return kept, rejected