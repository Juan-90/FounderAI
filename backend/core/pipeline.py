"""
Pipeline principal do Fundador IA.
Orquestra todos os agentes via LangGraph.
"""

from langgraph.graph import END, START, StateGraph

from backend.agents.contrarian_engine import run_contrarian_engine
from backend.agents.mission_intelligence import run_mission_intelligence
from backend.agents.mission_memory import save_mission
from backend.agents.mission_scorecard import run_mission_scorecard
from backend.agents.reality_engine import run_reality_engine
from backend.core.schemas import MissionState


# ─────────────────────────────────────────
# Nós do grafo
# ─────────────────────────────────────────

async def node_mission_intelligence(state: MissionState) -> MissionState:
    brief = await run_mission_intelligence(state.input)
    return MissionState(**state.model_dump(), mission_brief=brief)


async def node_reality_engine(state: MissionState) -> MissionState:
    report = await run_reality_engine(state.mission_brief)
    return MissionState(**state.model_dump(), reality_report=report)


async def node_contrarian_engine(state: MissionState) -> MissionState:
    risk = await run_contrarian_engine(state.reality_report)
    return MissionState(**state.model_dump(), risk_report=risk)


async def node_mission_scorecard(state: MissionState) -> MissionState:
    score = await run_mission_scorecard(
        state.mission_brief,
        state.reality_report,
        state.risk_report,
    )
    return MissionState(**state.model_dump(), mission_score=score)


async def node_mission_memory(state: MissionState) -> MissionState:
    await save_mission(state)
    return state


# ─────────────────────────────────────────
# Construção do grafo
# ─────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(MissionState)

    graph.add_node("mission_intelligence", node_mission_intelligence)
    graph.add_node("reality_engine", node_reality_engine)
    graph.add_node("contrarian_engine", node_contrarian_engine)
    graph.add_node("mission_scorecard", node_mission_scorecard)
    graph.add_node("mission_memory", node_mission_memory)

    graph.add_edge(START, "mission_intelligence")
    graph.add_edge("mission_intelligence", "reality_engine")
    graph.add_edge("reality_engine", "contrarian_engine")
    graph.add_edge("contrarian_engine", "mission_scorecard")
    graph.add_edge("mission_scorecard", "mission_memory")
    graph.add_edge("mission_memory", END)

    return graph.compile()


# Instância compilada para uso pela aplicação
pipeline = build_graph()
