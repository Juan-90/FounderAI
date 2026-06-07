"""
Teste do Reality Engine (Sprint 2).
Roda o pipeline completo: Mission Intelligence → Reality Engine.

Uso:
    python -m scripts.test_reality_engine
    python -m scripts.test_reality_engine "Quero criar um app de finanças para MEIs"
"""

import asyncio
import sys

sys.path.insert(0, ".")


async def main() -> None:
    from backend.agents.mission_intelligence import run_mission_intelligence
    from backend.agents.reality_engine import run_reality_engine
    from backend.core.ollama_client import ollama
    from backend.core.schemas import MissionInput

    # ── 1. Verifica Ollama ──
    print("🔌 Verificando conexão com Ollama...")
    if not await ollama.health_check():
        print("❌ Ollama não está acessível em http://localhost:11434")
        sys.exit(1)
    print("✅ Ollama conectado.\n")

    raw_idea: str = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "Quero criar um app de finanças para MEIs no Brasil."
    )

    print(f"💡 Ideia: {raw_idea}")
    print("─" * 60)

    # ── 2. Mission Intelligence ──
    print("⏳ [1/2] Executando Mission Intelligence...")
    brief = await run_mission_intelligence(MissionInput(raw_idea=raw_idea))
    print(f"✅ Mission Brief gerado. Clareza: {brief.clarity_level.value}\n")

    # ── 3. Reality Engine ──
    print("⏳ [2/2] Executando Reality Engine (Qwen3 14B — pode demorar)...")
    report = await run_reality_engine(brief)

    # ── 4. Output completo ──
    print("\n" + "═" * 60)
    print("📋 REALITY REPORT")
    print("═" * 60)
    print(report.raw_output)

    # ── 5. Schema parseado ──
    print("\n" + "═" * 60)
    print("🔍 SCHEMA PARSEADO")
    print("═" * 60)
    print(f"Resumo:          {report.executive_summary[:100]}...")
    print(f"Recomendação:    {report.recommendation.value}")
    print(f"Confiança:       {report.confidence_level.value}")
    print(f"Investimento:    {report.estimated_investment}")
    print(f"Tempo validação: {report.validation_time}")
    print(f"Riscos ({len(report.risks)}):")
    for r in report.risks:
        print(f"  • {r[:90]}")

    print("\n✅ Teste concluído.")


if __name__ == "__main__":
    asyncio.run(main())