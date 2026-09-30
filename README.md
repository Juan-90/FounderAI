# 🏛 FounderAI — AI Project Operating System

**FounderAI** é um *Sistema Operacional de Projetos* movido a IA: ele **descobre**
oportunidades, **valida** ideias, **constrói** MVPs executáveis e **audita a si
próprio** — transformando uma intenção de fundador em software testado, com trilha
de auditoria completa e decisão humana no comando.

> v5.0.0 GA — estável, testado e congelado (ver `ADR-017-GA-Release-Freeze`).

---

## 🧠 O Ciclo Cognitivo

```
   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐
   │ DISCOVER │──▶│ VALIDATE │──▶│  BUILD   │──▶│ SELF-AUDIT │──┐
   │ (mapear) │   │ (merece?)│   │(construir)│   │ (auditar)  │  │
   └──────────   └──────────┘   └──────────┘   └────────────┘  │
        ▲                                                       │
        └────────────────────  feedback  ───────────────────────┘
```

- **🧭 DISCOVER** — mapeia oportunidades a partir de um tema (ranking por pesos
  explícitos + filtro anti-clichê) e entrega as melhores ao VALIDATE.
- **🔍 VALIDATE** — analisa dor/mercado/concorrência/viabilidade e emite veredito
  `INVESTIGATE / BUILD / PIVOT / DISCARD` com confiança.
- **🏗 BUILD** — gera requisitos → arquitetura → código → testes e os executa em
  sandbox Docker hardenizada (Web/FastAPI ou Game/Pygame headless).
- **🩺 SELF-AUDIT** — roda missões canônicas nos 3 modos, aplica objective checks
  e um auditor adversarial (Creator ≠ Auditor), consolidando um scorecard
  `HEALTHY / DEGRADED / CRITICAL`.
- **🧩 VALIDATE_AND_BUILD** — ponte direta: valida e, se o gate autorizar
  (com confirmação humana quando exigida), constrói na mesma missão.
- **🏛 Council** *(origem)* — deliberação multi-turno de jurados de IA para
  avaliar missões de produto (APPROVED/REJECTED + esclarecimentos).

---

## ⚡ Instalação rápida

```bash
git clone <repo> && cd FounderAI
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .[dev]                                   # ou pip install -r requirements.txt

# Sandbox (necessária p/ BUILD/SELF-AUDIT):
docker build -t founderai-sandbox-python:v1 \
  -f backend/sandbox/dockerfile/Dockerfile backend/sandbox/dockerfile

# Configuração:
cp .env.example .env     # edite chaves de API e provedores
```

**Provedores:** `PRIMARY_PROVIDER` (`groq|openrouter|openai|local`) com fallback
automático para `local` (Ollama). Sem chave Cloud? Use `PRIMARY_PROVIDER=local`
com `ollama serve`. O startup avisa (sem stack traces) se faltar algo essencial.

---

## 🖥 Uso via CLI

```bash
# Council (deliberação)
python main.py "Criar app de finanças para MEIs" -f README.md

# DISCOVER
python main.py discover "Oportunidades de software para barbearias no Brasil" --max 6
python main.py discover "Tema" --handoff <opp_id>          # envia ao VALIDATE

# VALIDATE
python main.py validate "Quero validar o EcoTrack-IA..." -f research.md

# BUILD
python main.py build "Quero um sistema de agendamento para minha barbearia"
python main.py build "Jogo 2D de nave vs asteroides" --type GAME

# VALIDATE_AND_BUILD
python main.py validate-and-build "Validar EcoTrack-IA e construir MVP" --auto-build

# SELF-AUDIT
python main.py self-audit --max-per-mode 2

# Golden Missions (regressão GA)
python main.py golden-missions

# Histórico / reexecução
python main.py --history -n 10
python main.py --last
```

**Exit codes previsíveis:** `0` sucesso · `1` falha (todos os modos).

---

## 🗂 Artefatos

Cada modo persiste tudo sob `artifacts/<modo>/<mission_id>/`:

```
artifacts/
├── discover/            scope.json, opportunities.json, rejected.json, discover_report.md
├── validate/            idea_profile.json, validation_report.md, ...
├── build/               requirements.md, architecture.md, código, report.md
├── validate_and_build/  gate_decision.json, composite_report.md, ...
├── self_audit/          scorecard.json, adversarial_review.json, self_audit_report.md
└── golden/              golden_report.md, golden_state.json, mission_state.json (por missão)
```

---

## 🧪 Testes

```bash
pytest -q                     # suíte padrão (sem LLM/Docker)
pytest -q --run-real-llm      # inclui testes com LLM real
pytest -q --run-golden        # inclui a bateria Golden Missions real
```

---

## ⚠️ Limitações Honestas (v5.0)

- **Qualidade atrelada ao LLM:** prompts/heurísticas mitigam, mas não eliminam,
  variabilidade de modelos (especialmente locais/pequenos).
- **Sandbox sem pygame/display:** jogos são validados pela camada de lógica
  (testes headless); render/áudio reais ficam para a v5.1+.
- **Sem evidências externas:** `evidence_level` do DISCOVER é proxy heurístico
  (não faz web scraping).
- **Self-audit real custa LLM/Docker:** por padrão roda sob demanda (`--run-golden`
  / `self-audit`), não em todo commit.
- **Persistência local:** artefatos em disco; banco/Qdrant permanecem legados
  (histórico do Council), sem dashboard web.

## 🗺 Roadmap (v5.1+)

- **v5.1** — Sandbox com pygame/display virtual; re-ranking automático pós-VALIDATE.
- **v5.2** — Busca de evidências externas (web) para o DISCOVER/VALIDATE.
- **v5.3** — Dashboard web do scorecard GA + memória de longo prazo (RAG).
- **v6.0** — Auto-correção a partir do SELF-AUDIT (loop fechado de melhoria).

---

*Fundador IA · do Conselho ao GA · v5.0.0*