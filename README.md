# 🏛️ FounderAI (Fundador IA)

> **Conselho Consultivo Artificial para Validação de Missões e Ideias de Startups.**

O **FounderAI** é um sistema de suporte à decisão projetado para ajudar empreendedores, desenvolvedores e gerentes de produto a responder a uma pergunta fundamental antes de escrever uma única linha de código:  
👉 **"Esta missão/ideia realmente merece ser executada?"**

Através de uma deliberação sequencial entre **jurados especializados com personas distintas** (Arquiteto de Software, Especialista em Segurança e Generalista de Negócios), o sistema analisa a missão, pondera riscos, aplica direitos de veto e emite um veredito final fundamentado.

---

## 🎯 Principais Funcionalidades (Até a Sprint 3)

- 🧑‍⚖️ **Conselho Multi-Agente:** Avaliação sequencial com atribuição de notas (0-10), justificativas detalhadas e regras de veto por perfil.
- 🎨 **Interface CLI Rica (`rich`):** Terminal interativo com spinners em tempo real, tabelas formatadas, menus de navegação e painéis de veredito amigáveis.
- 📁 **Gerenciamento Inteligente de Contexto (`-f` / `--file`):** Leitura segura de arquivos do repositório com limites configuráveis de caracteres (`prepare_context_payload`) para evitar estouro da janela do LLM.
- 📊 **Histórico e Persistência Dupla:** Registro automático e auditável em formato humano (`docs/DECISIONS.md`) e em formato estruturado (`docs/decisions_history.json`).
- 📜 **Visualização de Histórico (`--history` / `-h`):** Comando para listar as últimas deliberações em tabela estilizada no terminal.
- 🔄 **Reexecução de Deliberações (`--last` e `--rerun`):** Capacidade de reexecutar a última missão enviada ao Conselho ou resgatar uma deliberação antiga por ID para reavaliação.
- 🛡️ **Segurança e Resiliência:** Prevenção contra *Path Traversal*, captura defensiva de IDs inexistentes e tratamento gracioso de falhas/timeouts de conexão com o Ollama.

---

## 🛠️ Stack Tecnológica

- **Linguagem:** Python 3.12+
- **Provedor LLM:** Ollama (rodando localmente)
- **Interface / CLI:** `rich` + `argparse`
- **Validação de Dados:** Pydantic
- **Persistência:** JSON (`docs/decisions_history.json`) + Markdown (`docs/DECISIONS.md`)

---

## 📂 Estrutura do Projeto

```text
FounderAI/
├── backend/
│   ├── core/
│   │   ├── config.py          # Configurações globais (Timeouts, URLs do Ollama, etc.)
│   │   ├── council.py         # Orquestração do Conselho e regras de deliberação
│   │   ├── history.py         # Gerenciador de persistência em JSON e consulta de histórico
│   │   ├── llm_client.py      # Client HTTP resiliente com tratamento de exceções
│   │   └── storage.py         # Formatação e persistência de auditoria em Markdown
│   ├── schemas/               # Schemas Pydantic para estruturação das respostas
│   └── tools/
│       └── file_tools.py      # Leitura segura de arquivos, prevenção de Path Traversal e gestão de payload
├── docs/
│   ├── DECISIONS.md           # Histórico legível de decisões do Conselho
│   └── decisions_history.json # Histórico estruturado para auditoria e re-runs
├── main.py                    # Ponto de entrada da CLI (Interativo, Rerun, History e Argumentos)
├── requirements.txt           # Dependências do projeto
└── README.md                  # Documentação do projeto

# 1. Clone o repositório
git clone [https://github.com/seu-usuario/FounderAI.git](https://github.com/seu-usuario/FounderAI.git)
cd FounderAI

# 2. Crie e ative um ambiente virtual
python -m venv .venv
# No Windows (PowerShell):
.venv\Scripts\Activate.ps1
# No Linux/Mac:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Garanta que o modelo no Ollama esteja pronto
ollama run llama3

python main.py "Quero criar uma plataforma de gestão financeira voltada para MEIs no Brasil"
python main.py "Avaliar viabilidade de refatorar a CLI" -f README.md
python main.py --history
python main.py --last
python main.py --rerun "ID_DA_DELIBERACAO"
python main.py

📌 Status do Projeto
[x] Sprint 1: Estrutura base do Conselho Consultivo, integração com Ollama local e persistência em Markdown.

[x] Sprint 2: Interface CLI avançada com rich, tratamento de resiliência/timeout e injeção de contexto via arquivos locais.

[x] Sprint 3: Persistência estruturada em JSON, histórico de decisões (--history), limites inteligentes de contexto e reexecução de deliberações (--last / --rerun).

[ ] Sprint 4 (Em andamento): Polimento final do MVP, estabilização de UX/DX, documentação e congelamento da versão 2.0-MVP.
