Markdown
# 🤖 FounderAI — Conselho Consultivo AI (v2.0-MVP)

[![Status](https://img.shields.io/badge/Status-APROVADO%20%26%20CONGELADO-brightgreen)](#)
[![Release](https://img.shields.io/badge/Release-v2.0--MVP-blue)](#)
[![Python](https://img.shields.io/badge/Python-3.10%2B-informational)](#)
[![Architecture](https://img.shields.io/badge/Architecture-CLI%20%7C%20Local%20LLM-orange)](#)

O **FounderAI** é uma ferramenta CLI (Command Line Interface) interativa, resiliente e automatizada criada para auxiliar fundadores, arquitetos de software e gerentes de produto na validação rigorosa de missões, ideias de produto e decisões estratégicas.

A validação é conduzida por um **Conselho Consultivo de IA** autônomo e multi-agente, rodando sobre infraestrutura local privativa via Ollama.

---

## 🏛️ O Conselho Consultivo

O sistema submete cada missão a um fluxo sequencial de avaliação por três jurados especializados com diretrizes estritas:

* **🏗️ Architect:** Analisa a viabilidade técnica, complexidade de implementação, arquitetura de software e escalabilidade da proposta.
* **🛡️ SecurityCoder:** Avalia a postura de segurança, privacidade de dados, conformidade regulatória (LGPD, PCI-DSS) e riscos operacionais graves. Possui **poder de VETO absoluto** no conselho.
* **💼 Generalist:** Examina o potencial comercial, adequação ao mercado brasileiro, viabilidade financeira e pragmatismo do modelo de negócios.

---

## 🏗️ Arquitetura & Fluxo do Sistema

                    [ Entrada da Missão ]
                    ( + Arquivo Opção -f )
                              │
                              ▼
               ┌──────────────────────────────┐
               │   Análise de Riscos & Input  │
               │ (Truncamento & Path Traversal)│
               └──────────────┬───────────────┘
                              │
                              ▼
            ┌──────────────────────────────────┐
            │     Conselho Consultivo AI       │
            │ ──────────────────────────────── │
            │  1. Architect (Score / Nota)     │
            │  2. SecurityCoder (Score / VETO) │
            │  3. Generalist (Score / Nota)    │
            └─────────────────┬────────────────┘
                              │
                              ▼
                ┌───────────────────────────┐
                │  Cálculo do Veredito      │
                │  & Persistência Dupla     │
                └─────────────┬─────────────┘
                              │
          ┌───────────────────┴───────────────────┐
          ▼                                       ▼
 [ docs/DECISIONS.md ]              [ docs/decisions_history.json ]
(Relatório Markdown Humano)             (Estrutura JSON / Reexecução)


---

## 🚀 Como Executar

### 1. Pré-requisitos
* **Python 3.10+**
* **Ollama** instalado e configurado

---

### 2. Inicializando o Provedor Local (Ollama)

Você pode executar o Ollama de duas formas equivalentes:

**Via Docker Compose (Recomendado para ambientes containerizados):**
```bash
docker compose -f docker/docker-compose.yml up -d ollama
Via Ollama Nativo (Instalado diretamente no Sistema Operacional):

Bash
ollama run gemma2:2b
3. Instalação de Dependências
Certifique-se de ativar seu ambiente virtual (.venv) no terminal do projeto e instale os pacotes necessários:

Bash
pip install -r requirements.txt
💻 Interface de Linha de Comando (CLI)
O FounderAI conta com uma interface rica e amigável desenvolvida em rich, garantindo respostas visuais claras, tabelas formatadas e spinners de progresso.

🔹 Submeter uma nova missão
Bash
python main.py "Validar viabilidade de um super app de produtividade urbana"
🔹 Submeter uma missão anexando um arquivo de contexto
Bash
python main.py "Validar arquitetura e segurança do projeto" -f README.md
🔹 Consultar o histórico de deliberações
Bash
python main.py --history -n 5
🔹 Reexecutar a última missão submetida
Bash
python main.py --last
🔹 Reexecutar uma missão específica por ID
Bash
python main.py --rerun 37daafd5-e464-4c4a-aaf1-f2121dcec850
🛡️ Auditoria e Persistência Dupla
Todas as deliberações geradas pelo Conselho possuem rastreabilidade total e geram registros imutáveis gravados simultaneamente em dois formatos:

docs/DECISIONS.md — Histórico humano contendo ADRs (Architecture Decision Records) e relatórios detalhados em Markdown.

docs/decisions_history.json — Base estruturada legível por máquina, garantindo reexecuções exatas (--rerun) e consultas via CLI (--history).

📌 Histórico de Decisões de Arquitetura (ADRs)
[ADR-001] Escolha de Execução Local Sequencial com Ollama e gemma2:2b.

[ADR-002] Congelamento Oficial do MVP v2.0 e Definição de Escopo de Manutenção (Agosto/2026).

📋 Status da Release
Versão: v2.0-MVP

Status: APROVADO & CONGELADO

Data de Encerramento: 27 de Agosto de 2026
