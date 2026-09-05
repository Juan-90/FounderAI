# FounderAI 🚀

O **FounderAI** é uma ferramenta de apoio à validação de ideias de startups e software. Ele utiliza um conselho de agentes LLM especializados (*Architect*, *SecurityCoder* e *Generalist*) para analisar propostas, identificar riscos técnicos/negócios e emitir um parecer deliberativo transparente.

---

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
