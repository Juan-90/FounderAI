# DECISIONS.md

> Registro de decisões arquiteturais e estratégicas do projeto.

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