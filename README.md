# Fundador IA

> Sistema Operacional para Validação de Missões e Criação de Organizações Digitais Evolutivas.

## Missão

**Reduzir o risco de construir a coisa errada.**

## O Problema

Empreendedores gastam meses ou anos desenvolvendo produtos sem validar adequadamente se existe mercado, demanda ou viabilidade.

## A Solução

Fundador IA atua como um Co-Fundador Digital que responde duas perguntas críticas:

1. **"Essa missão merece ser executada?"**
2. **"Qual é o problema real por trás da ideia declarada?"**

## Agentes do Sistema

| Agente | Entrada | Saída |
|---|---|---|
| Mission Intelligence | Ideia do usuário | Mission Brief |
| Reality Engine | Mission Brief | Reality Report |
| Contrarian Engine | Reality Report | Risk Report |
| Mission Scorecard | Todos os relatórios | Score Visual |
| Mission Memory | Todos os relatórios | Base histórica |

## Stack

- **Orquestração:** LangGraph
- **Modelos:** Gemma 4 E4B + Qwen3 14B (via Ollama)
- **Memória:** Mem0 + Qdrant + PostgreSQL
- **Interface:** Chainlit
- **Deploy:** Docker Compose

## Início Rápido

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/fundador-ia.git
cd fundador-ia

# 2. Suba os serviços
docker compose up -d

# 3. Instale dependências Python
pip install -r backend/requirements.txt

# 4. Rode a interface
chainlit run frontend/app.py
```

## Estrutura do Projeto

```
FundadorIA/
├── docs/           # Documentação e constituição do projeto
├── backend/        # Agentes, core e API
├── frontend/       # Interface Chainlit
├── database/       # Schemas e migrations
├── memory/         # Configuração da camada de memória
├── missions/       # Missões salvas (output)
├── tests/          # Testes unitários e de integração
├── docker/         # Dockerfiles e configurações
└── scripts/        # Scripts utilitários
```

## Status

🚧 Em desenvolvimento — Sprint 1: Mission Intelligence
