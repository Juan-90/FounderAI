"""
Fundador IA — CLI Principal
Instancia o Conselho Consultivo, avalia uma missão e salva a decisão.

Uso:
    python main.py
    python main.py "Quero criar um app de delivery para farmácias no Brasil"
"""

import asyncio
import sys


async def main() -> None:
    from backend.agents.council import run_council
    from backend.storage.decisions import save_council_decision

    mission: str = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "Quero criar um app de finanças para MEIs no Brasil."
    )

    print("\n" + "═" * 60)
    print("🏛️  CONSELHO CONSULTIVO — Fundador IA")
    print("═" * 60)
    print(f"\n📋 Missão: {mission}\n")
    print("⏳ Iniciando deliberação sequencial...\n")

    decision = await run_council(mission)

    # ── Resultado ──
    print("\n" + "═" * 60)
    print("🎯 DECISÃO DO CONSELHO")
    print("═" * 60)

    verdict_emoji = "✅" if decision.final_verdict == "APPROVED" else "❌"
    print(f"\n{verdict_emoji} Veredicto Final: {decision.final_verdict}")
    print(f"📊 Score Médio:    {decision.average_score:.2f}/10.0\n")

    print("Avaliações individuais:")
    for r in decision.juror_responses:
        icon = "✅" if r.verdict.value == "APPROVE" else "🚫"
        print(f"  {icon} {r.juror_name}: {r.score:.1f}/10 — {r.verdict.value}")
        print(f"     {r.reasoning[:120]}")

    # ── Salva no DECISIONS.md ──
    print()
    save_council_decision(decision)
    print("\n✅ Concluído.")


if __name__ == "__main__":
    asyncio.run(main())