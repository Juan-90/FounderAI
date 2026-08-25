"""
Fundador IA — Interface Chainlit
Pipeline completo: Mission Intelligence → Reality Engine → Contrarian Engine → Scorecard → Memory
"""

import os
import chainlit as cl

from backend.agents.contrarian_engine import run_contrarian_engine
from backend.agents.mission_intelligence import run_mission_intelligence
from backend.agents.mission_memory import save_mission
from backend.agents.mission_scorecard import run_mission_scorecard
from backend.agents.reality_engine import run_reality_engine
from backend.core.schemas import MissionInput, MissionState

WELCOME_MESSAGE = """# 🚀 Fundador IA
### Co-Fundador Digital para Validação de Missões

> *"Reduzir o risco de construir a coisa errada."*

---

Descreva sua ideia ou missão em linguagem natural. O sistema irá:

1. **Mission Intelligence** — Descobrir o problema real
2. **Reality Engine** — Analisar o mercado com honestidade
3. **Contrarian Engine** — Encontrar o que pode dar errado
4. **Mission Scorecard** — Gerar um score 0-100
5. **Mission Memory** — Registrar os aprendizados

**Qual é a sua missão?**
"""


@cl.on_chat_start
async def on_start():
    await cl.Message(content=WELCOME_MESSAGE).send()


@cl.on_message
async def on_message(message: cl.Message):
    raw_idea = message.content.strip()
    if not raw_idea:
        await cl.Message(content="Por favor, descreva sua ideia.").send()
        return

    state = MissionState(input=MissionInput(raw_idea=raw_idea))

    # ── Agente 1: Mission Intelligence ──
    step1 = cl.Message(content="🔍 **[1/5] Mission Intelligence** — Analisando o problema real...")
    await step1.send()

    state.mission_brief = await run_mission_intelligence(state.input)
    brief = state.mission_brief

    step1.content = f"""✅ **Mission Brief**

**Missão Declarada:** {brief.declared_mission}

**Problema Raiz:** {brief.root_problem}

**Público-Alvo:** {brief.target_audience}

**Hipóteses Críticas:**
{chr(10).join(f"- {h}" for h in brief.critical_hypotheses)}

**Nível de Clareza:** {brief.clarity_level.value}
"""
    await step1.update()

    # ── Agente 2: Reality Engine ──
    step2 = cl.Message(content="📊 **[2/5] Reality Engine** — Analisando mercado e viabilidade...")
    await step2.send()

    state.reality_report = await run_reality_engine(state.mission_brief)
    report = state.reality_report

    rec_emoji = {"GO": "🟢", "PIVOT": "🟡", "KILL": "🔴"}.get(report.recommendation.value, "⚪")

    step2.content = f"""✅ **Reality Report**

**Resumo:** {report.executive_summary}

**Riscos Principais:**
{chr(10).join(f"- {r}" for r in report.risks[:4])}

**Investimento MVP:** {report.estimated_investment}

{rec_emoji} **Recomendação: {report.recommendation.value}**
_{report.justification[:300]}..._
"""
    await step2.update()

    # ── Agente 3: Contrarian Engine ──
    step3 = cl.Message(content="😈 **[3/5] Contrarian Engine** — Procurando o que pode dar errado...")
    await step3.send()

    state.risk_report = await run_contrarian_engine(state.reality_report)
    risk = state.risk_report

    step3.content = f"""✅ **Risk Report**

**Premissas Frágeis:**
{chr(10).join(f"- {a}" for a in risk.fragile_assumptions[:3])}

**Perguntas Difíceis:**
{chr(10).join(f"- {q}" for q in risk.hard_questions[:3])}

⚠️ **Probabilidade de Falha: {risk.failure_probability.value}**
"""
    await step3.update()

    # ── Agente 4: Mission Scorecard ──
    step4 = cl.Message(content="📈 **[4/5] Mission Scorecard** — Calculando score...")
    await step4.send()

    state.mission_score = await run_mission_scorecard(
        state.mission_brief,
        state.reality_report,
        state.risk_report,
    )
    score = state.mission_score

    interp_emoji = {
        "Excelente": "🏆",
        "Promissora": "✨",
        "Incerta": "🤔",
        "Arriscada": "⚠️",
        "Não recomendada": "🛑",
    }.get(score.interpretation.value, "📊")

    step4.content = f"""✅ **Mission Scorecard**

| Critério | Nota |
|---|---|
| Mercado | {score.market}/10 |
| Concorrência | {score.competition}/10 |
| Diferenciação | {score.differentiation}/10 |
| Facilidade de MVP | {score.mvp_ease}/10 |
| Viabilidade Técnica | {score.technical_viability}/10 |
| Potencial de Receita | {score.revenue_potential}/10 |
| Velocidade de Validação | {score.validation_speed}/10 |
| Risco Geral | {score.overall_risk}/10 |

{interp_emoji} **Score Final: {score.final_score}/100 — {score.interpretation.value}**
"""
    await step4.update()

    # ── Agente 5: Mission Memory ──
    step5 = cl.Message(content="💾 **[5/5] Mission Memory** — Salvando aprendizados...")
    await step5.send()

    try:
        mission_id = await save_mission(state)
        step5.content = f"✅ **Missão salva!** ID: `{mission_id}`"
    except Exception as e:
        step5.content = f"⚠️ **Mission Memory indisponível:** {str(e)[:80]}"
    await step5.update()

    # ── Resumo Final ──
    rec_emoji = {"GO": "🟢", "PIVOT": "🟡", "KILL": "🔴"}.get(report.recommendation.value, "⚪")

    await cl.Message(content=f"""---
## 🎯 Resultado Final

| | |
|---|---|
| **Recomendação** | {rec_emoji} {report.recommendation.value} |
| **Score** | {score.final_score}/100 — {score.interpretation.value} |
| **Probabilidade de Falha** | {risk.failure_probability.value} |
| **Confiança da Análise** | {report.confidence_level.value} |

> Quer explorar uma reformulação da missão? Descreva uma nova ideia ou peça para aprofundar algum ponto.
""").send()