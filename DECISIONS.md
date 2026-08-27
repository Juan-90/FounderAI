# DECISIONS.md

> Registro de decisões arquiteturais e estratégicas do projeto.

---

## 2026-06

### Arquitetura local-first
**Decisão:** Rodar modelos localmente via Ollama.
**Motivo:** Redução de custos operacionais e privacidade dos dados do usuário.
**Status:** ✅ Confirmada

---

### Gemma 2 2B como modelo principal
**Decisão:** Usar gemma2:2b para todos os agentes.
**Motivo:** Eficiência — boa qualidade com baixo consumo de recursos em CPU.
**Status:** ✅ Confirmada

---

### Sprint 2 — Resiliência e CLI (Junho 2026)
**Decisões:**
- `LLMProviderError` unificado com `LLMErrorKind` enum. Aliases de retrocompatibilidade mantidos.
- Retry automático (1 tentativa) em falhas transitórias de conexão/timeout.
- CLI refatorada com `rich` (Console, Panel, Table, Status/spinner).
- Suporte a arquivos de contexto via `-f` / `--file`.
- `backend/tools/file_tools.py` criado com validação de Path Traversal.
- Histórico persistido em `docs/decisions_history.json` + `docs/DECISIONS.md`.
**Status:** ✅ Concluída

---

### Sprint 3 — Confiabilidade, Observabilidade e UX (Agosto 2026)
**Decisões:**
- `backend/core/history.py` centraliza persistência (MD + JSON).
- `prepare_context_payload()` com limites configuráveis: MAX_FILE_CHARS=10k, MAX_TOTAL_CONTEXT_CHARS=30k.
- `ContextPayload` dataclass com included/truncated/omitted/warnings.
- CLI: menu interativo, `--last`, `--rerun [ID]`, resumo de contexto com tamanho em KB.
- `get_last_decision()` e `get_decision_by_id()` adicionados ao history.py.
**Status:** ✅ Concluída

---

## ADR-002 — Congelamento Oficial do MVP v2.0 (Agosto/2026)

- **Data:** 27 de Agosto de 2026
- **Status:** APROVADO & CONGELADO
- **Participantes:** Juan, Grok (Guardião do Tempo), Gemini (Arquiteto)

### Contexto

Encerramento oficial do ciclo inicial de desenvolvimento do FounderAI v2.0. O sistema atingiu estabilidade funcional como CLI interativa e automatizada para validação de missões de produto via Conselho Consultivo AI.

### Escopo Incluído no MVP v2.0

- Conselho Consultivo Sequencial com 3 papéis fixos (Architect, SecurityCoder, Generalist).
- Interface CLI moderna (`rich`) com menu interativo, tabelas formatadas, spinners e painéis de erro graciosos.
- Gerenciamento seguro de contexto (`-f` / `--file`) com mitigação de Path Traversal e limite de payload (`prepare_context_payload`).
- Persistência dupla auditável: Markdown (`docs/DECISIONS.md`) e JSON estruturado (`docs/decisions_history.json`).
- Modos de navegação e reexecução: `--history` (`-n`), `--last` e `--rerun <ID>`.
- Tratamento defensivo de erros de conexão HTTP/Timeout com Ollama local.

### Escopo Explicitamente Fora do MVP (Congelado para v3.0+)

- Execução de código / Sandbox.
- Provedores Cloud (Groq, OpenRouter, OpenAI).
- Múltiplas rodadas de debate ou troca de papéis dinâmicos.
- Interface Web / Frontend gráfico.
- Banco de dados vetorial / RAG avançado.

---
<!-- ANCHOR_DELIBERATIONS -->



## 2026-06

### Arquitetura local-first
**Decisão:** Rodar modelos localmente via Ollama.
**Motivo:** Redução de custos operacionais e privacidade dos dados do usuário.
**Status:** ✅ Confirmada

---

### Gemma 2 2B como modelo principal
**Decisão:** Usar gemma2:2b para todos os agentes.
**Motivo:** Eficiência — boa qualidade com baixo consumo de recursos em CPU.
**Status:** ✅ Confirmada

---

### Sprint 2 — Resiliência e CLI (Junho 2026)
**Decisões:**
- `LLMProviderError` unificado com `LLMErrorKind` enum. Aliases de retrocompatibilidade mantidos.
- Retry automático (1 tentativa) em falhas transitórias de conexão/timeout.
- CLI refatorada com `rich` (Console, Panel, Table, Status/spinner).
- Suporte a arquivos de contexto via `-f` / `--file`.
- `backend/tools/file_tools.py` criado com validação de Path Traversal.
- Histórico persistido em `docs/decisions_history.json` + `docs/DECISIONS.md`.
**Status:** ✅ Concluída

---

### Sprint 3 — Confiabilidade, Observabilidade e UX (Agosto 2026)
**Decisões:**
- `backend/core/history.py` centraliza persistência (MD + JSON).
- `prepare_context_payload()` com limites configuráveis: MAX_FILE_CHARS=10k, MAX_TOTAL_CONTEXT_CHARS=30k.
- `ContextPayload` dataclass com included/truncated/omitted/warnings.
- CLI: menu interativo, `--last`, `--rerun [ID]`, resumo de contexto com tamanho em KB.
- `get_last_decision()` e `get_decision_by_id()` adicionados ao history.py.
**Status:** ✅ Concluída

---

# DECISION LOG - FounderAI 2.0

## 📐 ADR-001: Runtime de Agentes Heterogêneos & Escopo do MVP
- **Data:** 25/08/2026
- **Status:** Aprovado

### Contexto
O FounderAI foi idealizado como um sistema operacional/runtime configurável para agentes de IA heterogêneos (`Model` ≠ `Agent` ≠ `Role` ≠ `Team`). No entanto, dado o prazo (24/12/2026), a limitação de dedicação (~10h/semana) e execução local em CPU/Ollama (Vaio FE15), a implementação precisa de foco estrito.

### Decisão
1. A arquitetura de código manterá abstrações extensíveis para suportar múltiplos modelos e papéis dinâmicos no futuro.
2. O MVP (Sprint 1) é implementado com **3 papéis fixos** (`Architect`, `SecurityCoder`, `Generalist`) em execução sequencial local via Ollama (`gemma2:2b`).
3. O parâmetro de limitação de 3 modelos reflete uma restrição de ambiente/hardware do usuário, não uma limitação da arquitetura do software.
4. A validação das missões requer aprovação por score médio >= 8.0 e ausência de veto de segurança/regulatório.

---


## 2026-06

### Arquitetura local-first
**Decisão:** Rodar modelos localmente via Ollama.
**Motivo:** Redução de custos operacionais e privacidade dos dados do usuário.
**Status:** ✅ Confirmada

---

### Gemma 4 E4B como modelo principal
**Decisão:** Usar Gemma 4 E4B para agentes de menor complexidade.
**Motivo:** Eficiência — boa qualidade com baixo consumo de recursos.
**Status:** ✅ Confirmada

---

### Qwen3 14B como modelo de reasoning/coding
**Decisão:** Usar Qwen3 14B para agentes que exigem raciocínio mais profundo.
**Motivo:** Qualidade superior em análise e programação.
**Status:** ✅ Confirmada

---

### Mission Intelligence como primeiro componente
**Decisão:** Desenvolver o Mission Intelligence no Sprint 1.
**Motivo:** É o primeiro neurônio do sistema — sem ele, nenhum outro agente funciona.
**Status:** ✅ Confirmada

---

### LangGraph para orquestração
**Decisão:** Usar LangGraph para orquestrar o pipeline de agentes.
**Motivo:** Controle explícito do fluxo, suporte a estado persistente e grafos cíclicos para futuras iterações.
**Status:** ✅ Confirmada

---

### PostgreSQL + Qdrant para memória
**Decisão:** Dados estruturados em PostgreSQL, busca semântica em Qdrant.
**Motivo:** Separação clara entre persistência relacional e recuperação por similaridade.
**Status:** ✅ Confirmada

---

### Gemma 4 E4B como modelo único durante desenvolvimento local
**Decisão:** Usar Gemma 4 E4B para todos os agentes durante o desenvolvimento.
**Motivo:** Ambiente de desenvolvimento usa CPU (GPU integrada AMD 5700U sem suporte ROCm via Docker no Windows). O Qwen3 14B requer GPU dedicada para ser viável. Gemma 4 E4B demonstrou qualidade suficiente no Sprint 1.
**Impacto:** Nenhum na arquitetura — a troca é feita via variável MODEL_REASONING no .env. Quando houver acesso a hardware adequado, basta alterar a configuração.
**Status:** Confirmada para desenvolvimento local