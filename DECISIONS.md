# DECISIONS.md

> Registro de decisões arquiteturais e estratégicas do projeto.

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