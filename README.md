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

## 🧠 Memória de Projeto (v5.3.0)

Cada projeto acumula **eventos, decisões, aprendizados e versões de artefatos**
entre missões. Um BUILD posterior herda automaticamente as decisões e os riscos
descobertos num VALIDATE anterior (injetados no contexto dos agentes).

### Vincular missões a um projeto

```bash
python main.py validate "Validar EcoTrack-IA" --project <project_id>
python main.py build "Construir MVP EcoTrack" --project <project_id>
python main.py validate-and-build "Ideia" --project <project_id>

python main.py project list                 # todos os projetos
python main.py project show <id>            # goal + decisões + aprendizados
python main.py project timeline <id>        # linha do tempo de eventos
python main.py project artifacts <id>       # versões de artefatos arquivadas

python main.py project list                 # todos os projetos
python main.py project show <id>            # goal + decisões + aprendizados
python main.py project timeline <id>        # linha do tempo de eventos
python main.py project artifacts <id>       # versões de artefatos arquivadas

GET /api/v1/projects                      # lista
GET /api/v1/projects/{id}                 # resumo completo
GET /api/v1/projects/{id}/timeline        # eventos
GET /api/v1/projects/{id}/artifacts       # versões

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

## 🔧 Modo IMPROVE (v5.4.0)

Fecha o loop de refinamento: **diagnostica** a memória do projeto, **planeja**
melhorias, **aplica patches** com limite estrito de arquivos e **re-valida** em
sandbox (static gate + TDD). Falhas passadas viram correções; correções viram
aprendizados.



Saída: tabela Rich com diagnóstico, plano de ações e status
(`WAITING_HUMAN` / `SUCCESS` / `ESCALATED`); em `WAITING_HUMAN` pede `[y/N]`.

Via API: `POST /api/v1/interact` com `mode:"improve"` (+`project_id`) ou atalho
`POST /api/v1/projects/{id}/improve`.

Variáveis: `IMPROVE_MODE_ENABLED`, `IMPROVE_MAX_FILES_TOUCHED` (limite estrito
de arquivos por melhoria), `IMPROVE_MAX_RETRIES` (retries do TDD antes de
escalar). Ver **ADR-022**.

## ⚠️ Limitações Honestas (v5.2.1)

## ⚠️ Estado da Baseline v5.5.0 & Limitações Reais

**Baseline consolidada (selada em v5.5.0):** v5.0 GA (núcleo + Golden Missions)
· v5.1 Interaction Layer (REST+WS) · v5.2 Evidence Graph + providers reais +
cache/dedup · v5.3 Project Memory · v5.4 IMPROVE Mode · v5.5 OBSERVE mínimo +
smoke de release. **478 testes** passando; smoke 6/6.

**Limitações reais (transparência):**
- **Generator LLM de patches não plugado:** o `ImprovePatcher` opera via
  generators injetáveis (Protocol); sem generator, o patch é no-op. Patches
  reais por provider LLM chegam na v5.6.
- **OBSERVE mínimo:** só feedback humano explícito (CLI/REST); sem telemetria
  automática de uso.
- **Memória apenas em disco:** `artifacts/projects/<id>/memory.json` (atômico);
  backends sqlite/redis adiados.
- **Sem UI web** de timeline/melhorias (Streamlit cobre missões, não memória).
- **Smoke in-process:** não sobe servidor/Docker reais (propósito: checagem
  rápida de release).
- **Relevância lexical:** Jaccard em evidence; embeddings/RAG adiados.


---

## 👁 Feedback Humano — OBSERVE (v5.5.0)

Registre a observação do fundador diretamente na memória do projeto; ela vira
aprendizado (`human_feedback`) + evento `OBSERVED` e **alimenta o IMPROVE**
(diagnoser a cita primeiro; planner gera item de correção).

```bash
python main.py project feedback <project_id> --rating 4 --note "UX ótima, mas lenta" --tags ux,perf
python main.py project timeline <project_id>     # evento OBSERVED formatado

## 🗺 Roadmap

- **v5.5.0 (atual — GA)** — OBSERVE mínimo + smoke de release + baseline v5.x selada.
- **v5.6.0** — Generator LLM de patches plugável + auto-refinamento agendado +
  UI web de timeline/melhorias + backend de memória plugável.
- **v7.0.0+** — Continuous Project Memory & orquestração multi-agente (Colibri).

---

*FounderAI · AI Project Operating System · v5.2.1*