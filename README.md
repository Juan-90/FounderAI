# 🏛️ FounderAI (Fundador IA)

> **Conselho Consultivo Artificial para Validação de Missões e Ideias de Startups.**

O **FounderAI** é um sistema de suporte à decisão projetado para ajudar empreendedores, desenvolvedores e gerentes de produto a responder a uma pergunta fundamental antes de escrever uma única linha de código:  
👉 **"Esta missão/ideia realmente merece ser executada?"**

Através de uma deliberação sequencial entre **jurados especializados com personas distintas** (Arquiteto de Software, Especialista em Segurança e Generalista de Negócios), o sistema analisa a missão, pondera riscos, aplica direitos de veto e emite um veredito final fundamentado.

---

## 🎯 Principais Funcionalidades (Até a Sprint 2)

- 🧑‍⚖️ **Conselho Multi-Agente:** Avaliação sequencial com atribuição de notas (0-10), justificativas detalhadas e regras de veto por perfil.
- 🎨 **Interface CLI Rica (`rich`):** Terminal interativo com spinners em tempo real, tabelas formatadas e painéis de veredito amigáveis.
- 📁 **Injeção de Contexto Local (`-f` / `--file`):** Leitura segura de arquivos do repositório (ex: `README.md`, `docs/PRD.md`) para fundamentar as análises dos jurados.
- 🛡️ **Segurança e Resiliência:** Leitura de arquivos com proteção contra *Path Traversal*, truncamento inteligente de caracteres e tratamento gracioso de erros de conexão/timeout com o LLM.
- 💾 **Auditoria & Persistência Historica:** Registro automático de todas as deliberações e deliberações anteriores no arquivo `docs/DECISIONS.md`.

---

## 🛠️ Stack Tecnológica

- **Linguagem:** Python 3.12+
- **Provedor LLM:** Ollama (rodando localmente)
- **Interface / CLI:** `rich` + `argparse`
- **Validação de Dados:** Pydantic
- **Persistência:** Markdown (`docs/DECISIONS.md`)

---

## 📂 Estrutura do Projeto

```text
FounderAI/
├── backend/
│   ├── core/
│   │   ├── config.py          # Configurações globais (Timeouts, URLs do Ollama, etc.)
│   │   ├── council.py         # Lógica de orquestração do Conselho e jurados
│   │   ├── llm_client.py      # Client HTTP com tratamento de exceções e resiliência
│   │   └── storage.py         # Persistência de auditoria em Markdown
│   ├── schemas/               # Schemas Pydantic para estruturação das respostas
│   └── tools/
│       └── file_tools.py      # Leitura segura de arquivos locais e prevenção de Path Traversal
├── docs/
│   └── DECISIONS.md           # Histórico e log de decisões do Conselho
├── main.py                    # Ponto de entrada da CLI (Interativo e via linha de comando)
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

# 4. Garanta que o modelo no Ollama esteja pronto (ex: llama3 / qwen2.5 / deepseek-r1)
ollama run llama3

python main.py "Quero criar uma plataforma de gestão financeira voltada para MEIs no Brasil"
python main.py "Avaliar viabilidade de refatorar a CLI para suporte a mapas de memória" -f README.md
python main.py
