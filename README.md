# 🏛 FounderAI v3.5 — Conselho Consultivo Artificial

Sistema de consultoria interativa **multi-agente e multi-turno** para fundadores de
startups. Um conselho de jurados de IA (Architect, SecurityCoder, Generalist) avalia
sua missão, faz perguntas de esclarecimento quando necessário e emite um veredito
final com score e justificativa.

## ✨ O que a v3.5 entrega

| Capacidade | Descrição |
|---|---|
| **Diálogo Multi-turno** | Turno 0 (análise inicial) e Turno 1 (após esclarecimentos), com controle estrito de estado: `PENDING_CLARIFICATION`, `FINAL`, `CANCELLED`. |
| **Cliente Híbrido (Cloud + Local)** | Contrato único `OpenAI-compatible` para Groq, OpenRouter, OpenAI e Ollama/vLLM local, com **fallback automático** Cloud → Local em falhas, timeout ou ausência de chave. |
| **Contexto Expandido** | Múltiplos arquivos via `-f`, com limites previsíveis por arquivo (`MAX_FILE_CHARS`) e acumulados (`MAX_TOTAL_CONTEXT_CHARS`), relatados como incluídos/truncados/omitidos. |
| **Observabilidade** | Provedor/modelo efetivos e indicador de fallback por jurado, exibidos na CLI e persistidos no histórico (JSON + Markdown). |
| **Override por Papel** | Provedor específico por jurado (`ARCHITECT_PROVIDER`, `SECURITYCODER_PROVIDER`, `PRODUCTSTRATEGIST_PROVIDER`). |
| **Suíte de Testes** | 140+ testes unitários, de integração e E2E, 100% verdes, sem I/O real (MockTransport). |

## 🚀 Configuração Rápida

### Pré-requisitos
- Python 3.11+
- (Opcional, modo local) [Ollama](https://ollama.com) instalado

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # e edite conforme abaixo