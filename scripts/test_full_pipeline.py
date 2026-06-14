"""
Teste do pipeline completo do Fundador IA.
Roda todos os 5 agentes em sequência.

Uso:
    python -m scripts.test_full_pipeline
    python -m scripts.test_full_pipeline "Minha ideia aqui"
"""

import asyncio
import sys

sys.path.insert(0, ".")


async def main() -> None:
    from backend.agents.contrarian_engine import run_contrarian_engine
    from backend.agents.mission_intelligence import run_mission_intelligence
    from backend.agents.mission_memory import save_mission
    from backend.agents.mission_scorecard import run_mission_scorecard
    from backend.agents.reality_engine import run_reality_engine
    from backend.core.ollama_client import ollama
    from backend.core.schemas import MissionInput, MissionState

    # ── 1. Verifica Ollama ──
    print("🔌 Verificando conexão com Ollama...")
    if not await ollama.health_check():
        print("❌ Ollama não está acessível.")
        sys.exit(1)
    print("✅ Ollama conectado.\n")

    raw_idea: str = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "Quero criar um app de finanças para MEIs no Brasil."
    )

    print(f"💡 Ideia: {raw_idea}")
    print("═" * 60)

    state = MissionState(input=MissionInput(raw_idea=raw_idea))

    # ── Agente 1: Mission Intelligence ──
    print("\n⏳ [1/5] Mission Intelligence...")
    state.mission_brief = await run_mission_intelligence(state.input)
    print(f"✅ Clareza: {state.mission_brief.clarity_level.value}")

    # ── Agente 2: Reality Engine ──
    print("\n⏳ [2/5] Reality Engine...")
    state.reality_report = await run_reality_engine(state.mission_brief)
    print(f"✅ Recomendação: {state.reality_report.recommendation.value}")

    # ── Agente 3: Contrarian Engine ──
    print("\n⏳ [3/5] Contrarian Engine...")
    state.risk_report = await run_contrarian_engine(state.reality_report)
    print(f"✅ Probabilidade de Falha: {state.risk_report.failure_probability.value}")

    # ── Agente 4: Mission Scorecard ──
    print("\n⏳ [4/5] Mission Scorecard...")
    state.mission_score = await run_mission_scorecard(
        state.mission_brief,
        state.reality_report,
        state.risk_report,
    )
    print(f"✅ Score Final: {state.mission_score.final_score}/100 — {state.mission_score.interpretation.value}")

    # ── Agente 5: Mission Memory ──
    print("\n⏳ [5/5] Mission Memory (salvando no PostgreSQL)...")
    try:
        mission_id = await save_mission(state)
        print(f"✅ Missão salva! ID: {mission_id}")
    except Exception as e:
        print(f"⚠️  PostgreSQL indisponível ({e}). Missão não persistida.")

    # ── Resultado Final ──
    print("\n" + "═" * 60)
    print("🎯 RESULTADO FINAL")
    print("═" * 60)

    score = state.mission_score
    report = state.reality_report
    risk = state.risk_report

    print(f"\n📋 Missão: {raw_idea}")
    print(f"🎯 Recomendação: {report.recommendation.value}")
    print(f"⚠️  Probabilidade de Falha: {risk.failure_probability.value}")
    print(f"\n📊 SCORECARD")
    print(f"   Mercado:              {score.market}/10")
    print(f"   Concorrência:         {score.competition}/10")
    print(f"   Diferenciação:        {score.differentiation}/10")
    print(f"   Facilidade de MVP:    {score.mvp_ease}/10")
    print(f"   Viabilidade Técnica:  {score.technical_viability}/10")
    print(f"   Potencial de Receita: {score.revenue_potential}/10")
    print(f"   Velocidade Validação: {score.validation_speed}/10")
    print(f"   Risco Geral:          {score.overall_risk}/10")
    print(f"   {'─'*30}")
    print(f"   SCORE FINAL:          {score.final_score}/100")
    print(f"   INTERPRETAÇÃO:        {score.interpretation.value}")

    print(f"\n❓ Perguntas Difíceis ({len(risk.hard_questions)}):")
    for q in risk.hard_questions:
        print(f"   • {q[:90]}")

    print("\n✅ Pipeline completo concluído.")


if __name__ == "__main__":
    asyncio.run(main())