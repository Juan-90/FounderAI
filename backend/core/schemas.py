"""
Schemas de dados do Fundador IA.
Define as estruturas de entrada e saída de cada agente.
"""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# JurorResponse vive em backend/schemas/council.py (v2.0+)
from backend.schemas.council import JurorResponse


# ─────────────────────────────────────────
# Enums
# ─────────────────────────────────────────

class ClarityLevel(str, Enum):
    LOW  = "Baixo"
    MEDIUM = "Médio"
    HIGH = "Alto"


class Recommendation(str, Enum):
    GO    = "GO"
    PIVOT = "PIVOT"
    KILL  = "KILL"


class FailureProbability(str, Enum):
    LOW    = "Baixa"
    MEDIUM = "Média"
    HIGH   = "Alta"


class ScoreInterpretation(str, Enum):
    EXCELLENT        = "Excelente"
    PROMISING        = "Promissora"
    UNCERTAIN        = "Incerta"
    RISKY            = "Arriscada"
    NOT_RECOMMENDED  = "Não recomendada"


class MissionDecision(str, Enum):
    CONTINUE = "Continuar"
    PIVOT    = "Pivotar"
    ABANDON  = "Abandonar"
    PENDING  = "Pendente"


# ─────────────────────────────────────────
# Evidence Layer
# ─────────────────────────────────────────

class Evidence(BaseModel):
    """Representa uma evidência com rastreabilidade."""
    claim:      str = Field(description="Afirmação ou dado")
    source:     str = Field(description="Fonte da informação")
    confidence: ClarityLevel = Field(description="Nível de confiança")
    date:       Optional[str] = Field(default=None, description="Data da informação")


# ─────────────────────────────────────────
# Council & Deliberation (v3.5 Multi-turno)
# ─────────────────────────────────────────

class ClarificationRequest(BaseModel):
    """Conjunto de perguntas/alertas gerados pelo conselho no Turno 0."""
    reason:    str       = Field(description="Motivo pelo qual o conselho precisa de esclarecimentos.")
    questions: list[str] = Field(description="Lista de perguntas direcionadas ao fundador.")


class CouncilDecision(BaseModel):
    """Resultado final da deliberação do conselho (v3.0)."""
    verdict:       Literal["APPROVED", "REJECTED"]
    average_score: float
    reason:        str


class DeliberationState(BaseModel):
    """Gerencia todo o estado da deliberação multi-turno (v3.5)."""
    mission:          str
    status:           Literal["PENDING_CLARIFICATION", "FINAL", "CANCELLED"] = "PENDING_CLARIFICATION"
    turn0_responses:  list[JurorResponse]                  = Field(default_factory=list)
    clarification:    Optional[ClarificationRequest]       = None
    founder_response: Optional[str]                        = None
    turn1_responses:  Optional[list[JurorResponse]]        = None
    final_decision:   Optional[CouncilDecision]            = None


# ─────────────────────────────────────────
# Agent 1 — Mission Intelligence
# ─────────────────────────────────────────

class MissionInput(BaseModel):
    """Entrada do usuário para o sistema."""
    raw_idea: str = Field(description="Ideia ou missão declarada pelo usuário")


class MissionBrief(BaseModel):
    """Saída do Mission Intelligence."""
    id:         UUID     = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    declared_mission:         str
    identified_problem:       str
    root_problem:             str
    target_audience:          str
    critical_hypotheses:      list[str]
    recommended_reformulations: list[str]
    clarity_level:            ClarityLevel
    pending_questions:        list[str]

    evidences:   list[Evidence] = Field(default_factory=list)
    raw_output:  Optional[str]  = None


# ─────────────────────────────────────────
# Agent 2 — Reality Engine
# ─────────────────────────────────────────

class RealityReport(BaseModel):
    """Saída do Reality Engine."""
    id:               UUID     = Field(default_factory=uuid4)
    mission_brief_id: UUID
    created_at:       datetime = Field(default_factory=datetime.utcnow)

    executive_summary:       str
    market_analysis:         str
    competition_analysis:    str
    differentiation_analysis: str
    risks:                   list[str]
    complexity:              ClarityLevel
    estimated_investment:    str
    validation_time:         str

    recommendation:   Recommendation
    justification:    str
    confidence_level: ClarityLevel

    evidences:  list[Evidence] = Field(default_factory=list)
    raw_output: Optional[str]  = None


# ─────────────────────────────────────────
# Agent 3 — Contrarian Engine
# ─────────────────────────────────────────

class RiskReport(BaseModel):
    """Saída do Contrarian Engine."""
    id:               UUID     = Field(default_factory=uuid4)
    reality_report_id: UUID
    created_at:       datetime = Field(default_factory=datetime.utcnow)

    main_risks:          list[str]
    fragile_assumptions: list[str]
    possible_failures:   list[str]
    negative_scenarios:  list[str]
    hard_questions:      list[str]
    failure_probability: FailureProbability
    recommendations:     list[str]

    raw_output: Optional[str] = None


# ─────────────────────────────────────────
# Agent 4 — Mission Scorecard
# ─────────────────────────────────────────

class MissionScore(BaseModel):
    """Saída do Mission Scorecard."""
    id:               UUID     = Field(default_factory=uuid4)
    mission_brief_id: UUID
    created_at:       datetime = Field(default_factory=datetime.utcnow)

    market:             int = Field(ge=0, le=10)
    competition:        int = Field(ge=0, le=10)
    differentiation:    int = Field(ge=0, le=10)
    mvp_ease:           int = Field(ge=0, le=10)
    technical_viability: int = Field(ge=0, le=10)
    revenue_potential:  int = Field(ge=0, le=10)
    validation_speed:   int = Field(ge=0, le=10)
    overall_risk:       int = Field(ge=0, le=10)

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
        if score >= 80:   return ScoreInterpretation.EXCELLENT
        if score >= 65:   return ScoreInterpretation.PROMISING
        if score >= 50:   return ScoreInterpretation.UNCERTAIN
        if score >= 35:   return ScoreInterpretation.RISKY
        return ScoreInterpretation.NOT_RECOMMENDED

    raw_output: Optional[str] = None


# ─────────────────────────────────────────
# Mission State
# ─────────────────────────────────────────

class MissionState(BaseModel):
    """Estado completo da missão no pipeline de agentes."""
    input:          MissionInput
    mission_brief:  Optional[MissionBrief]  = None
    reality_report: Optional[RealityReport] = None
    risk_report:    Optional[RiskReport]    = None
    mission_score:  Optional[MissionScore]  = None
    final_decision: Optional[MissionDecision] = None
    error:          Optional[str]           = None