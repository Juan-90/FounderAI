# 🏛 FounderAI — AI Project Operating System

**FounderAI** é um *Sistema Operacional de Projetos* movido a IA: ele **descobre**
oportunidades, **valida** ideias, **constrói** MVPs executáveis, **corrobora com
evidências externas**, **expõe tudo por API reativa** e **audita a si próprio** —
transformando a intenção de um fundador em software testado, com trilha de
auditoria completa e decisão humana no comando.

> **v5.2.1** — Evidence Hardening (Real Providers, Caching, Dedup & Observability)
> · Núcleo GA selado em v5.0.0 · Interaction Layer em v5.1.0 · Evidence Graph em v5.2.0.

---

## 🧠 O Ciclo Cognitivo & Arquitetura

```
   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐
   │ DISCOVER │──▶│ VALIDATE │──▶│  BUILD   │──▶│ SELF-AUDIT │──┐
   │ (mapear) │   │ (merece?)│   │(construir)│   │ (auditar)  │  │
   └──────────   └──────────┘   └──────────┘   └────────────┘  │
        ▲                                                       │
        └────────────────────  feedback  ───────────────────────┘
                            │
        ┌───────────────────────────────────────────┐
        │ Interaction Layer (v5.1)                  │
        │ FastAPI REST + WebSockets + Streamlit     │
        ├───────────────────────────────────────────┤
        │ Evidence Layer (v5.2)                     │
        │ Tavily/Serper + Cache + Dedup + Métricas  │
        └───────────────────────────────────────────┘
```

- **🧭 DISCOVER** — mapeia oportunidades a partir de um tema (ranking por pesos
  explícitos + filtro anti-clichê) e entrega as melhores ao VALIDATE.
- **🔍 VALIDATE** — analisa dor/mercado/concorrência/viabilidade e emite veredito
  `INVESTIGATE / BUILD / PIVOT / DISCARD` com confiança e seção "Evidence vs Opinion".
- **🏗 BUILD** — gera requisitos → arquitetura → código → testes e os executa em
  sandbox Docker hardenizada (Web/FastAPI ou Game/Pygame headless).
- **🩺 SELF-AUDIT** — roda missões canônicas, aplica objective checks e um auditor
  adversarial (Creator ≠ Auditor); scorecard `HEALTHY / DEGRADED / CRITICAL`.
- **🧩 VALIDATE_AND_BUILD** — ponte direta: valida e, se o gate autorizar (com
  confirmação humana quando exigida), constrói na mesma missão.
- **⚡ INTERACTION LAYER (v5.1)** — `MissionEngine` expõe o núcleo via REST + WebSocket.
- **🔍 EVIDENCE LAYER (v5.2)** — busca externa (Tavily/Serper), cache 24h, dedup e
  métricas; cada claim rastreável até uma fonte real.

---

## ⚡ Instalação Rápida

```bash
git clone <repo> && cd FounderAI
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .[dev]                                # ou pip install -r requirements.txt

# Sandbox (necessária p/ BUILD/SELF-AUDIT):
docker build -t founderai-sandbox-python:v1 \
  -f backend/sandbox/dockerfile/Dockerfile backend/sandbox/dockerfile

# Configuração:
cp .env.example .env     # edite chaves de API e provedores
```

---

## 🌐 Servidor de API (v5.1+) & Frontend

```bash
# API backend
uvicorn backend.api.app:app --reload --port 8000
#   REST:      http://localhost:8000/api/v1/interact
#   Docs:      http://localhost:8000/docs
#   WebSocket: ws://localhost:8000/ws/v1/missions/{mission_id}/stream

# Frontend Streamlit harmonizado
streamlit run frontend/app.py
```

---

## 🖥 Uso via CLI

```bash
# DISCOVER
python main.py discover "Oportunidades de software para barbearias no Brasil" --max 6

# VALIDATE
python main.py validate "Quero validar o EcoTrack-IA..." -f research.md

# BUILD
python main.py build "Quero um sistema de agendamento para minha barbearia"
python main.py build "Jogo 2D de nave vs asteroides" --type GAME

# VALIDATE_AND_BUILD
python main.py validate-and-build "Validar EcoTrack-IA e construir MVP" --auto-build

# SELF-AUDIT & Golden Missions
python main.py self-audit --max-per-mode 2
python main.py golden-missions

# Evidências (v5.2)
python main.py validate "Sua ideia" --evidence-provider tavily
python main.py discover "Tema" --no-evidence        # só opinião do modelo
```

---

## 🔍 Evidências Externas (v5.2)

### Provedores reais

```bash
# .env
TAVILY_API_KEY="tvly-..."      # https://tavily.com
SERPER_API_KEY="..."           # https://serper.dev
EVIDENCE_PROVIDER=tavily       # mock | http | tavily | serper
```

Sem key configurada, o sistema **cai graciosamente para o MockSearchProvider**
(com aviso) — nunca quebra a missão.

### Cache & Dedup

- Cache de 24h em `artifacts/.evidence_cache/` (`EVIDENCE_CACHE_TTL_SECONDS`);
  `EVIDENCE_CACHE_BYPASS=true` força busca fresca.
- Dedup de fontes por URL canônica, de evidências por hash e de claims por texto.

### Observabilidade

Cada missão com evidência grava `evidence_graph.json` com métricas:
`provider_used`, `cache_hits`, `cache_misses`, `deduped_sources_count`,
`deduped_evidence_count`, `deduped_claims_count` — expostas em
`GET /api/v1/missions/{id}` no campo `evidence_summary`.

---

## 🗂 Artefatos & Governança

- **Artefatos:** `artifacts/<modo>/<mission_id>/` (+ subpasta `evidence/` quando aplicável).
- **Governança (ADRs):** arquivo único **`docs/DECISIONS`** (v1.0 → v5.2.1, ADR-004…ADR-020).
- **Log de deliberações (verbatim):** `docs/decisions_history.json`.
- **Release notes:** `docs/RELEASE_NOTES_v5.0.md`.

---

## 🧪 Testes

```bash
pytest -q                     # suíte completa (400+ testes, sem LLM/Docker no CI)
pytest -q --run-real-llm      # inclui testes com LLM real
pytest -q --run-golden        # inclui a bateria Golden Missions real
```

---

## ⚠️ Limitações Honestas (v5.2.1)

- **Relevância lexical:** `score_relevance` usa Jaccard (proxy); embeddings/RAG
  ficam para a v5.3.
- **Cache 24h:** pode servir evidência levemente desatualizada (aceitável; bypass disponível).
- **Render de jogos:** validação headless (camada de lógica); render real é local.
- **Persistência:** artefatos em disco + SQLite local; sem dashboard web de evidências ainda.

---

## 🗺 Roadmap

- **v5.2.1 (atual)** — Evidence Hardening: Tavily/Serper, cache, dedup, métricas, ADR-020.
- **v5.3.0** — UI de evidências (visualização do grafo) + auto-refinamento + embeddings/RAG.
- **v6.0.0+** — Continuous Project Memory & orquestração multi-agente (Colibri).

---

*FounderAI · AI Project Operating System · v5.2.1*