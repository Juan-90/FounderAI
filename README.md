# FounderAI 🚀

O **FounderAI** é uma ferramenta de apoio à validação de ideias de startups e software. Ele utiliza um conselho de agentes LLM especializados (*Architect*, *SecurityCoder* e *Generalist*) para analisar propostas, identificar riscos técnicos/negócios e emitir um parecer deliberativo transparente.

## 🛡️ O que a v4.0 adiciona

| Capacidade | Descrição |
|---|---|
| **Sandbox Isolada (Fase A)** | Containers Docker efêmeros e hardenizados (`--rm --network=none --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=64 --memory=512m --cpus=1.0`) para executar código sem risco ao host. |
| **Loop TDD Autônomo (Fase B)** | `QAAgent` + `TDDLoop` (Self-Healing): baseline → análise de falha → geração de patch → re-execução, com teto estrito de **3 tentativas** e escalação explícita (`escalated=True`). |
| **Schemas estritos de execução** | `SandboxInput`/`SandboxOutput` (comando sempre como `list[str]`, nunca shell) e `TDDRequest`/`TDDAttempt`/`TDDResult`. |
| **Gate de testes controlado** | Marker `@pytest.mark.real_llm` + flag `--run-real-llm` para testes que exigem LLM real em CI/CD. |

## 🚀 Configuração Rápida

### Pré-requisitos
- Python 3.11+
- Docker (para Sandbox/TDD)
- (Opcional, modo local) [Ollama](https://ollama.com) instalado

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # e edite conforme abaixo
```

### Modo 100% Local (Ollama)
```bash
ollama pull gemma2:2b
```
```env
PRIMARY_PROVIDER="local"
FALLBACK_PROVIDER="local"
ollama_base_url="http://localhost:11434/v1"
council_model="gemma2:2b"
```
Nenhuma chave de API é necessária. Ideal para hardware modesto (dev rápido, sem GPU).

### Modo Cloud (Groq / OpenRouter / OpenAI)
```env
PRIMARY_PROVIDER="groq"          # "groq" | "openrouter" | "openai" | "local"
FALLBACK_PROVIDER="local"        # rede de segurança automática
GROQ_API_KEY="gsk_..."
```
> ⚠️ Se o provedor primário Cloud estiver sem chave, o FounderAI avisa na
> inicialização e usa o fallback local automaticamente (`validate_provider_config`).

### Provedor/Modelo por Papel
```env
ARCHITECT_PROVIDER="openrouter"      # Architect usa OpenRouter
SECURITYCODER_PROVIDER="local"       # SecurityCoder sempre local
PRODUCTSTRATEGIST_PROVIDER=""        # vazio = usa PRIMARY_PROVIDER
```

##  Como Rodar a Sandbox (Fase A)

**Build da imagem local (uma vez por host):**
```bash
docker build -t founderai-sandbox-python:v1 -f backend/sandbox/dockerfile/Dockerfile backend/sandbox/dockerfile
```

**Uso programático:**
```python
from backend.sandbox import DockerSandboxRunner, SandboxInput

runner = DockerSandboxRunner()
out = runner.run(SandboxInput(
    files={"calc.py": "print(6 * 7)\n"},
    command=["python", "calc.py"],
    timeout_seconds=30,
))
print(out.exit_code, out.stdout)   # 0 42
```

## 🔄 Loop TDD Autônomo / Self-Healing (Fase B)

Ciclo: baseline (tentativa 0) → `analyze_failure` → `generate_fix` → re-execução na
sandbox, com teto de **3 retries**. Sem sucesso no limite → `escalated=True` com
diagnóstico completo para revisão humana.

```python
import asyncio
from backend.qa import TDDLoop, TDDRequest

loop = TDDLoop()
request = TDDRequest(
    source_files={"main.py": "def soma(a, b): return a - b\n"},
    test_files={"test_main.py": "from main import soma\n\ndef test_soma():\n    assert soma(2, 3) == 5\n"},
    goal="soma deve retornar a adição de a e b",
    max_retries=3,
)
result = asyncio.run(loop.run(request))
print(result.success, result.summary)
```

## 💻 Guia de Uso da CLI

```bash
python main.py                                    # Menu interativo
python main.py "Criar um app de finanças para MEIs"
python main.py "Missão" -f README.md              # 1 arquivo de contexto
python main.py "Missão" -f README.md -f docs/PRD.md   # múltiplos arquivos
python main.py --last                             # reexecuta a última deliberação
python main.py --rerun ID_COMPLETO                # reexecuta por ID
python main.py --history -n 10                    # últimas 10 deliberações
```

### Durante o pedido de esclarecimento (Turno 0)
Se o conselho detectar ambiguidade, um painel amarelo exibe as perguntas numeradas.
Digite sua resposta e pressione Enter para avançar ao Turno 1.

### Cancelamento gracioso
No prompt de esclarecimento: digite `cancel`, `abort` ou `/cancel`, **ou** pressione
`Ctrl+C`. A deliberação transita para `CANCELLED` e encerra sem stack trace.

### Contexto de arquivos
Resumo exibido antes da deliberação, ex.:
`📁 Contexto: 3 arquivo(s) incluído(s), 1 truncado(s), 0 omitido(s)`.

## 🏗️ Modo BUILD (v4.2 Web / v4.3 Game)

Transforma uma intenção de produto em um MVP executável e validado, em 6 estágios
(Requirements → Architecture → Implementation → Quality Gate → Sandbox/TDD → Report).
O tipo de projeto seleciona o **Profile** (stack, arquivos, prompts e env):

**Web/SaaS (default):**
```bash
python main.py build "Quero um sistema de agendamento para minha barbearia"


## 🔍 Modo VALIDATE (v4.4.0)

Valida se uma ideia **merece ser construída** antes de gastar ciclos de código, em
7 estágios analíticos (intake → problema/mercado → concorrentes → viabilidade
técnica → risco contrarian → experimentos → síntese).

**Executar:**
```bash
python main.py validate "Quero validar o EcoTrack-IA: um sistema de rastreamento ambiental..."
python main.py validate "Sua ideia aqui" -f research.md -f dados.csv


## 🧩 Modo VALIDATE_AND_BUILD (v4.5.0 — Ponte Direta)

Valida a ideia e, se o **DecisionGate** autorizar, constrói o MVP na mesma missão.

**Executar:**
```bash
python main.py validate-and-build "Validar EcoTrack-IA e construir MVP"
python main.py validate-and-build "Sua ideia" -f research.md   # com contexto
python main.py validate-and-build "Ideia" --no-build           # só valida
python main.py validate-and-build "Ideia" --auto-build         # sem confirmação humana
python main.py validate-and-build "Ideia" --no-confirm         # não pergunta; aguarda se exigir


## 🩺 Modo SELF-AUDIT (v4.6.0 — Auditoria Interna)

Executa um pack de missões canônicas nos 3 modos, aplica objective checks
determinísticos, passa por um **auditor adversarial** (Creator ≠ Auditor) e
consolida um Scorecard `HEALTHY / DEGRADED / CRITICAL`.

**Executar:**
```bash
python main.py self-audit
python main.py self-audit --no-vab --max-per-mode 2   # reduz escopo
python main.py self-audit --no-build --no-validate    # só VAB


## 🧪 Como Executar a Suíte Total de Testes

**Execução padrão (162 testes; testes de LLM real skipam graciosamente):**
```bash
pytest -q
```

**Execução completa incluindo testes que exigem LLM real (Groq/Ollama funcional):**
```bash
pytest -q --run-real-llm
```

**Apenas a suíte da Sandbox/TDD:**
```bash
pytest -q tests/unit/test_sandbox.py tests/unit/test_tdd_loop.py
```

> Sem Docker ou sem a imagem buildada, os testes de execução real **skipam**
> graciosamente (não falham) — a mecânica do loop permanece 100% coberta por fakes.

## 🗂 Arquitetura (visão geral)

```
main.py                     CLI Rich + orquestração multi-turno
backend/
  core/
    config.py               Settings Pydantic V2 (provedores, limites, sandbox, validação)
    llm_client.py           LLMClient híbrido + LLMCallResult (observabilidade)
    council.py              Máquina de estados (process_turn0 / process_founder_reply / cancel)
    verdict.py              Regra pura de veredito (limiares v3.0)
    context.py              Contexto expandido (ContextPayload)
    history.py              Persistência Markdown + JSON
    schemas.py              Schemas de domínio + ContextPayload + DeliberationState
  agents/council.py         Avaliação de jurados (retry C1 + observabilidade)
  schemas/council.py        JurorResponse / CouncilDecision (validação C1)
  sandbox/                  v4.0 Fase A — Docker efêmero hardenizado
    models.py               SandboxInput / SandboxOutput
    exceptions.py           SandboxError, DockerUnavailableError, SandboxTimeoutError, ImageNotFoundError
    runner.py               Abstração SandboxRunner
    docker_runner.py        DockerSandboxRunner (subprocess, flags estritas)
    dockerfile/Dockerfile   Imagem founderai-sandbox-python:v1
  qa/                       v4.0 Fase B — QA & Loop TDD
    schemas.py              TDDRequest / TDDAttempt / TDDResult
    agent.py                QAAgent (generate_tests / analyze_failure / generate_fix)
    orchestrator.py         TDDLoop / SelfHealingRunner
docs/DECISIONS.md           ADRs (001–007) + histórico de deliberações
tests/conftest.py           Marker real_llm + flag --run-real-llm
```

## 📜 Decisões Arquiteturais
- **ADR-004** — Padronização do protocolo OpenAI-Compatible e client híbrido.
- **ADR-005** — Congelamento e fechamento da v3.5.
- **ADR-007** — Congelamento oficial da v4.0 (Execução Segura & Loop TDD).

## 🔭 Roadmap (fora de escopo da v4.0)
- RAG / Memória vetorial (v4.5/v5.0)
- Persistência automática de patches no Git / abertura de PRs
- Execução de código com acesso à rede
- Autonomia sem limites de retries
## 📌 Novidades da Versão 3.0 (Sprint 4)

A versão 3.0 recalibrou os critérios do conselho para eliminar falsos-positivos de veto identificados em modelos menores (`2b`), promovendo deliberações mais equilibradas sem perder o rigor técnico:

* **Módulo C1 — Isolamento de System Prompts:** Prompts de cada jurado agora vivem em arquivos externos versionados com mecanismo de *fallback* resiliente a erros de I/O e encoding.
* **Módulo C2 — Parsing & Auto-Correção:** Validação estrita entre nota (*score*) e veredito (*verdict*), com disparos automáticos de *retry* técnico antes de acionar respostas *fallback*.
* **Módulo C3 — Matriz de Decisão Centralizada:** Lógica de deliberação unificada com limiares ajustados:
  * **Aprovado:** Média geral $\ge 7.5$, sem vetos e nota do *SecurityCoder* $\ge 6.0$.
  * **Rejeitado:** Presença de VETO, nota do *SecurityCoder* $< 6.0$ ou média $< 7.5$.
* **Observabilidade Clara:** Motivos detalhados da recusa/aprovação expostos diretamente no resultado da deliberação.
* **Alta Cobertura de Testes:** Bateria de testes de regressão executada em $<0.5s$ para garantir consistência operacional.

---

## 🛠️ Arquitetura do Conselho

| Agente | Foco Principal | LimiarCrítico |
| :--- | :--- | :--- |
| **Architect** | Escalabilidade, acoplamento e viabilidade técnica | Avalia arquitetura e padrão de projeto |
| **SecurityCoder** | Vulnerabilidades, exposição de dados e boas práticas | Reprovado se nota $< 6.0$ ou VETO |
| **Generalist** | Modelo de negócios, produto e aderência ao mercado | Avalia viabilidade geral da proposta |

---

## 🚀 Como Rodar o Projeto

### Pré-requisitos
* Python 3.12+
* Ambiente virtual (`.venv`) ativado

### Instalação
```bash
# Clone o repositório
git clone [https://github.com/seu-usuario/FounderAI.git](https://github.com/seu-usuario/FounderAI.git)
cd FounderAI

# Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instale as dependências
pip install -r requirements.txt


# Executando os Testes
Para rodar a suíte completa de testes unitários e de regressão (v3.0):

Bash
pytest tests/unit/ -v --asyncio-mode=auto
📝 Documentação
Para entender as motivações técnicas por trás dos limiares da v3.0 e a evolução dos prompts, consulte docs/DECISIONS.md
