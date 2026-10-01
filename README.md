Markdown
# 🏛 FounderAI — AI Project Operating System

**FounderAI** é um *Sistema Operacional de Projetos* movido a IA: ele **descobre**
oportunidades, **valida** ideias, **construções** MVPs executáveis, **expe por API reativa** e **audita a si próprio** — transformando uma intenção de fundador em software testado, com trilha de auditoria completa e decisão humana no comando.

> **v5.1.0** — Interaction Layer & Reactive API (REST + WebSocket) | Núcleo GA Selado em v5.0.0.

---

## 🧠 O Ciclo Cognitivo & Arquitetura

┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐
│ DISCOVER │──▶│ VALIDATE │──▶│  BUILD   │──▶│ SELF-AUDIT │──┐
│ (mapear) │   │ (merece?)│   │(construir)│   │ (auditar)  │  │
└──────────┘   └──────────┘   └──────────┘   └────────────┘  │
▲                                                       │
└──────────────────── feedback ─────────────────────────┘
│
┌───────────────────────────┐
│ Interaction Layer (v5.1)  │
│ FastAPI REST + WebSockets │
└───────────────────────────┘


- **🧭 DISCOVER** — mapeia oportunidades a partir de um tema (ranking por pesos explícitos + filtro anti-clichê) e entrega as melhores ao VALIDATE.
- **🔍 VALIDATE** — analisa dor/mercado/concorrência/viabilidade e emite veredito `INVESTIGATE / BUILD / PIVOT / DISCARD` com confiança.
- **🏗 BUILD** — gera requisitos → arquitetura → código → testes e os executa em sandbox Docker hardenizada (Web/FastAPI ou Game/Pygame headless).
- **🩺 SELF-AUDIT** — roda missões canônicas nos 3 modos, aplica objective checks e um auditor adversarial (Creator ≠ Auditor), consolidando um scorecard `HEALTHY / DEGRADED / CRITICAL`.
- **🧩 VALIDATE_AND_BUILD** — ponte direta: valida e, se o gate autorizar (com confirmação humana quando exigida), constrói na mesma missão.
- **⚡ INTERACTION LAYER (v5.1)** — `MissionEngine` orquestrador que expõe todas as capacidades do núcleo via API REST e streaming WebSocket em tempo real.

---

## ⚡ Instalação Rápida

```bash
git clone <repo> && cd FounderAI
python -m venv .venv && source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .[dev]                                   # ou pip install -r requirements.txt

# Sandbox (necessária p/ BUILD/SELF-AUDIT):
docker build -t founderai-sandbox-python:v1 \
  -f backend/sandbox/dockerfile/Dockerfile backend/sandbox/dockerfile

# Configuração:
cp .env.example .env     # edite chaves de API e provedores
🌐 Servidor de API (v5.1.0) & Frontend
A partir da v5.1.0, o FounderAI roda como um serviço reativo desacoplado:

Subir a API Backend:

Bash
uvicorn backend.api.app:app --reload --port 8000
REST: http://localhost:8000/api/v1/interact

Docs Swagger: http://localhost:8000/docs

WebSocket: ws://localhost:8000/ws/v1/missions/{mission_id}/stream

Subir o Frontend Harmonizado:

Bash
streamlit run frontend/app.py
🖥 Uso via CLI
Também é possível invocar o motor diretamente via linha de comando:

Bash
# DISCOVER
python main.py discover "Oportunidades de software para barbearias no Brasil" --max 6

# VALIDATE
python main.py validate "Quero validar o EcoTrack-IA..." -f research.md

# BUILD
python main.py build "Quero um sistema de agendamento para minha barbearia"

# SELF-AUDIT & Golden Missions
python main.py self-audit --max-per-mode 2
python main.py golden-missions
🗂 Artefatos & Histórico de Decisões
Artefatos Gerados: Persistidos por missão em artifacts/<modo>/<mission_id>/.

Histórico Arquitetural (ADRs): Todas as decisões de arquitetura e design da v1.0 à v5.1.0 (incluindo a ADR-018) estão centralizadas e versionadas no arquivo único docs/DECISIONS.md.

🧪 Testes
Bash
pytest -q                     # suíte completa (327+ testes cobrindo rotas, WS, motor e pipelines)
pytest -q --run-real-llm      # inclui testes com LLM real
pytest -q --run-golden        # inclui a bateria Golden Missions real
⚠️ Limitações Honestas (v5.1.0)
Sem Pesquisa Web em Tempo Real: O DISCOVER e o VALIDATE utilizam dados internos/heurística de LLM (a busca web com Grafo de Evidências é o foco da v5.2.0).

Renderização de Jogos: A validação de jogos 2D é executada headless (camada de lógica e testes); render real de tela permanece no ambiente local.

Persistência de Artefatos: Artefatos e logs são gravados em disco e SQLite local (artifacts/).

🗺 Roadmap Atualizado
v5.1.0 (Atual) — Interaction Layer (MissionEngine, REST API FastAPI, WebSockets & Streamlit harmonizado).

v5.2.0 (Próxima) — External Evidence & Evidence Graph (Busca web real, citação de fontes e confiança de dados).

v5.3.0 — Continuous Project Memory & Versioning Loop (RAG e histórico contínuo do projeto).

v6.0.0 / v7.0.0 — Integração com o ecossistema e orquestração do Colibri.

FounderAI · AI Project Operating System · v5.1.0
