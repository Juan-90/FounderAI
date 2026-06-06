"""
Teste manual do Mission Intelligence.
Roda direto no terminal sem precisar do Chainlit.

Uso:
    python -m scripts.test_mission_intelligence

    # Ou com ideia customizada:
    python -m scripts.test_mission_intelligence "Quero criar um app de finanças para MEIs"
"""

import asyncio
import sys

sys.path.insert(0, ".")  # Garante que o projeto está no path


async def main():
    from backend.agents.mission_intelligence import run_mission_intelligence
    from backend.core.ollama_client import ollama
    from backend.core.schemas import MissionInput

    # ── 1. Verifica se o Ollama está rodando ──
    print("🔌 Verificando conexão com Ollama...")
    if not await ollama.health_check():
        print("❌ Ollama não está acessível em http://localhost:11434")
        print("   Inicie com: docker compose -f docker/docker-compose.yml up -d ollama")
        sys.exit(1)
    print("✅ Ollama conectado.\n")

    # ── 2. Define a ideia a ser testada ──
    if len(sys.argv) > 1:
        raw_idea = " ".join(sys.argv[1:])
    else:
        raw_idea = "Quero criar um Uber para supermercados no Brasil."

    print(f"💡 Ideia: {raw_idea}")
    print("─" * 60)
    print("⏳ Executando Mission Intelligence...\n")

    # ── 3. Executa o agente ──
    input_data = MissionInput(raw_idea=raw_idea)
    brief = await run_mission_intelligence(input_data)

    # ── 4. Exibe o resultado raw (output direto do modelo) ──
    print("═" * 60)
    print("📋 OUTPUT DO MODELO")
    print("═" * 60)
    print(brief.raw_output)

    # ── 5. Exibe o schema parseado ──
    print("\n" + "═" * 60)
    print("🔍 SCHEMA PARSEADO")
    print("═" * 60)
    print(f"Missão Declarada:      {brief.declared_mission}")
    print(f"Problema Identificado: {brief.identified_problem[:80]}...")
    print(f"Público-Alvo:          {brief.target_audience[:80]}...")
    print(f"Nível de Confiança:    {brief.clarity_level.value}")
    print(f"Hipóteses ({len(brief.critical_hypotheses)}):")
    for h in brief.critical_hypotheses:
        print(f"  • {h[:80]}")
    print(f"Reformulações ({len(brief.recommended_reformulations)}):")
    for r in brief.recommended_reformulations:
        print(f"  • {r[:80]}")
    print(f"Perguntas ({len(brief.pending_questions)}):")
    for q in brief.pending_questions:
        print(f"  • {q[:80]}")

    print("\n✅ Teste concluído.")


if __name__ == "__main__":
    asyncio.run(main())