"""
Schemas de dados do Fundador IA.
Define as estruturas de entrada e saída de cada agente.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ─────────────────────────────────────────
# Enums
# ─────────────────────────────────────────

class ClarityLevel(str, Enum):
    LOW = "Baixo"
    MEDIUM = "Médio"
    HIGH = "Alto"


class Recommendation(str, Enum):
    GO = "GO"
    PIVOT = "PIVOT"
    KILL = "KILL"


class FailureProbability(str, Enum):
    LOW = "Baixa"
    MEDIUM = "Média"
    HIGH = "Alta"


class ScoreInterpretation(str, Enum):
    EXCELLENT = "Excelente"
    PROMISING = "Promissora"
    UNCERTAIN = "Incerta"
    RISKY = "Arriscada"
    NOT_RECOMMENDED = "Não recomendada"


class MissionDecision(str, Enum):
    CONTINUE = "Continuar"
    PIVOT = "Pivotar"
    ABANDON = "Abandonar"
    PENDING = "Pendente"


# ─────────────────────────────────────────
# Evidence Layer
# ─────────────────────────────────────────

class Evidence(BaseModel):
    """Representa uma evidência com rastreabilidade."""
    claim: str = Field(description="Afirmação ou dado")
    source: str = Field(description="Fonte da informação")
    confidence: ClarityLevel = Field(description="Nível de confiança")
    date: Optional[str] = Field(default=None, description="Data da informação")


# ─────────────────────────────────────────
# Agent 1 — Mission Intelligence
# ─────────────────────────────────────────

class MissionInput(BaseModel):
    """Entrada do usuário para o sistema."""
    raw_idea: str = Field(description="Ideia ou missão declarada pelo usuário")


class MissionBrief(BaseModel):
    """Saída do Mission Intelligence."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    declared_mission: str
    identified_problem: str
    root_problem: str
    target_audience: str
    critical_hypotheses: list[str]
    recommended_reformulations: list[str]
    clarity_level: ClarityLevel
    pending_questions: list[str]

    # Evidence Layer
    evidences: list[Evidence] = Field(default_factory=list)

    # Raw output do modelo (para debug)
    raw_output: Optional[str] = None


# ─────────────────────────────────────────
# Agent 2 — Reality Engine
# ─────────────────────────────────────────

class RealityReport(BaseModel):
    """Saída do Reality Engine."""
    id: UUID = Field(default_factory=uuid4)
    mission_brief_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    executive_summary: str
    market_analysis: str
    competition_analysis: str
    differentiation_analysis: str
    risks: list[str]
    complexity: ClarityLevel
    estimated_investment: str
    validation_time: str

    recommendation: Recommendation
    justification: str
    confidence_level: ClarityLevel

    evidences: list[Evidence] = Field(default_factory=list)
    raw_output: Optional[str] = None


# ─────────────────────────────────────────
# Agent 3 — Contrarian Engine
# ─────────────────────────────────────────

class RiskReport(BaseModel):
    """Saída do Contrarian Engine."""
    id: UUID = Field(default_factory=uuid4)
    reality_report_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    main_risks: list[str]
    fragile_assumptions: list[str]
    possible_failures: list[str]
    negative_scenarios: list[str]
    hard_questions: list[str]
    failure_probability: FailureProbability
    recommendations: list[str]

    raw_output: Optional[str] = None


# ─────────────────────────────────────────
# Agent 4 — Mission Scorecard
# ─────────────────────────────────────────

class MissionScore(BaseModel):
    """Saída do Mission Scorecard."""
    id: UUID = Field(default_factory=uuid4)
    mission_brief_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    market: int = Field(ge=0, le=10)
    competition: int = Field(ge=0, le=10)
    differentiation: int = Field(ge=0, le=10)
    mvp_ease: int = Field(ge=0, le=10)
    technical_viability: int = Field(ge=0, le=10)
    revenue_potential: int = Field(ge=0, le=10)
    validation_speed: int = Field(ge=0, le=10)
    overall_risk: int = Field(ge=0, le=10)

    @property
    def final_score(self) -> int:
        scores = [
            self.market, self.competition, self.differentiation,
            self.mvp_ease, self.technical_viability, self.revenue_potential,
            self.validation_speed, self.overall_risk,
        ]
        return int(sum(scores) / len(scores) * 10)

    @property
    def interpretation(self) -> ScoreInterpretation:
        score = self.final_score
        if score >= 80:
            return ScoreInterpretation.EXCELLENT
        elif score >= 65:
            return ScoreInterpretation.PROMISING
        elif score >= 50:
            return ScoreInterpretation.UNCERTAIN
        elif score >= 35:
            return ScoreInterpretation.RISKY
        else:
            return ScoreInterpretation.NOT_RECOMMENDED

    raw_output: Optional[str] = None


# ─────────────────────────────────────────
# Mission State (LangGraph)
# ─────────────────────────────────────────

class MissionState(BaseModel):
    """Estado completo da missão no grafo LangGraph."""
    input: MissionInput
    mission_brief: Optional[MissionBrief] = None
    reality_report: Optional[RealityReport] = None
    risk_report: Optional[RiskReport] = None
    mission_score: Optional[MissionScore] = None
    final_decision: Optional[MissionDecision] = None
    error: Optional[str] = None
