# 🤖 FounderAI — Conselho Consultivo AI (v2.0-MVP)

O **FounderAI** é uma CLI interativa e automatizada projetada para validar missões, ideias de produto e decisões estratégicas por meio de um Conselho Consultivo de IA local.

---

## 🏛️ O Conselho Consultivo

O sistema executa uma avaliação sequencial composta por 3 papéis especializados:

- **Architect:** Avalia a viabilidade técnica, arquitetura, escalabilidade e complexidade de execução.
- **SecurityCoder:** Avalia riscos de segurança, privacidade de dados, compliance (LGPD/PCI-DSS) e possui **poder de VETO absoluto**.
- **Generalist:** Avalia a viabilidade comercial, modelo de negócios e pragmatismo no contexto do mercado brasileiro.

---

## 🚀 Como Usar

### 1. Requisitos Prévios
- Python 3.10+
- Docker & Docker Compose (para executar o Ollama localmente)

### 2. Inicializando o Modelo Local (Ollama)
```bash
docker compose -f docker/docker-compose.yml up -d ollama


python main.py "Validar viabilidade de um super app de produtividade urbana"
python main.py "Validar arquitetura do projeto" -f README.md
python main.py --history -n 5
python main.py --last
python main.py --rerun <ID-DA-MISSAO>
