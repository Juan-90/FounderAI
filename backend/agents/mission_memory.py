"""
Mission Memory — Agente 5
Persiste missões completas no PostgreSQL.
"""

import json
from datetime import datetime
from uuid import UUID

import asyncpg

from backend.core.config import settings
from backend.core.schemas import MissionState


# ─────────────────────────────────────────
# Conexão
# ─────────────────────────────────────────

async def _get_connection() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )


# ─────────────────────────────────────────
# Save
# ─────────────────────────────────────────

async def save_mission(state: MissionState) -> str:
    """
    Persiste uma missão completa no PostgreSQL.
    Retorna o mission_id como string.
    """
    brief = state.mission_brief
    report = state.reality_report
    risk = state.risk_report
    score = state.mission_score

    if not brief:
        raise ValueError("MissionBrief não encontrado no estado.")

    conn = await _get_connection()
    try:
        mission_id: UUID = brief.id

        await conn.execute(
            """
            INSERT INTO missions (
                id, created_at, raw_idea, declared_mission, decision,
                score_market, score_competition, score_differentiation,
                score_mvp_ease, score_technical, score_revenue,
                score_validation_speed, score_overall_risk, score_final,
                recommendation, interpretation,
                mission_brief, reality_report, risk_report
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10, $11, $12, $13, $14,
                $15, $16, $17, $18, $19
            )
            ON CONFLICT (id) DO UPDATE SET
                updated_at = NOW(),
                decision = EXCLUDED.decision,
                score_final = EXCLUDED.score_final,
                recommendation = EXCLUDED.recommendation
            """,
            mission_id,
            datetime.utcnow(),
            state.input.raw_idea,
            brief.declared_mission,
            state.final_decision.value if state.final_decision else "Pendente",
            score.market if score else None,
            score.competition if score else None,
            score.differentiation if score else None,
            score.mvp_ease if score else None,
            score.technical_viability if score else None,
            score.revenue_potential if score else None,
            score.validation_speed if score else None,
            score.overall_risk if score else None,
            score.final_score if score else None,
            report.recommendation.value if report else None,
            score.interpretation.value if score else None,
            json.dumps(brief.model_dump(mode="json"), ensure_ascii=False),
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False) if report else None,
            json.dumps(risk.model_dump(mode="json"), ensure_ascii=False) if risk else None,
        )

        # Salva hipóteses
        if brief.critical_hypotheses:
            await conn.executemany(
                """
                INSERT INTO hypotheses (mission_id, description)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                [(mission_id, h) for h in brief.critical_hypotheses],
            )

        return str(mission_id)

    finally:
        await conn.close()


# ─────────────────────────────────────────
# Retrieve
# ─────────────────────────────────────────

async def get_mission(mission_id: str) -> dict | None:
    """Recupera uma missão por ID."""
    conn = await _get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM missions WHERE id = $1",
            UUID(mission_id),
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def list_missions(limit: int = 20) -> list[dict]:
    """Lista as missões mais recentes."""
    conn = await _get_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, created_at, declared_mission, recommendation,
                   score_final, interpretation, decision
            FROM missions
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()