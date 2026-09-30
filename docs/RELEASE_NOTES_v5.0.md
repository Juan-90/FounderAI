# 🎉 Release Notes — FounderAI v5.0.0 GA

**Data:** 27/09/2026 · **Status:** General Availability (congelada — ver ADR-017)

A v5.0 marca a transição do FounderAI de "conjunto de agentes" para um
**Sistema Operacional de Projetos** completo, com regressão canônica (Golden
Missions), CLI polida e auto-auditoria.

---

## 🧬 Evolução v1.0 → v5.0

| Versão | Marco | Destaques |
|---|---|---|
| **v1.0** | Council inicial | Jurados de IA, veredito APPROVE/VETO, score |
| **v2.0** | Council + histórico | Persistência de deliberações, reexecução (`--last/--rerun`) |
| **v3.0** | Multi-turno + contexto | Turno 0/1 com esclarecimentos; anexos `-f` com limites seguros |
| **v4.0** | LLM agnóstico + Sandbox | `LLMClient` multi-provedor c/ fallback; sandbox Docker hardenizada; `TDDLoop` self-healing |
| **v4.1** | Guardrails + telemetria | `StaticAnalysisGate` (ruff/mypy); telemetria RAM/CPU; Escalation Webhook |
| **v4.2** | BUILD Web | `BuildPipeline` 6 estágios; `ArtifactManager`; caso Barbearia |
| **v4.3** | BUILD Game | `GameProfile` (pygame headless); CLI `--type GAME`; caso Asteroids |
| **v4.4** | VALIDATE | 7 agentes analíticos; `DecisionGate`; vereditos INVESTIGATE/BUILD/PIVOT/DISCARD |
| **v4.5** | VALIDATE_AND_BUILD | Ponte direta; `BuildSeed`; confirmação humana (`WAITING_HUMAN`) |
| **v4.6** | SELF-AUDIT | `AuditRunner` + objective checks; `AdversarialAuditor` (Creator≠Auditor); scorecard |
| **v4.7** | DISCOVER | Ranking por pesos explícitos; `OpportunityCritic`; handoff → VALIDATE |
| **v5.0** | **GA** | Golden Missions (G1–G7); polimento CLI; checagem de ambiente; congelamento |

---

## ✨ Novidades da v5.0

- **🏅 Golden Missions (G1–G7):** regressão canônica cobrindo todos os modos,
  incluindo casos negativos (ideia fraca bloqueada no gate) e os dois paths de
  BUILD. `python main.py golden-missions` · `pytest --run-golden`.
- **🖥 Polimento CLI:** erros acionáveis sem stack trace (`friendly_error`),
  resumos Rich consistentes, exit codes 0/1 previsíveis em todos os modos.
- **⚙ Checagem de ambiente:** avisos claros no startup (chave ausente, ambos
  locais sem Ollama); `.env.example` revisado de ponta a ponta.
- **🗂 Padrão de artefatos:** `artifacts/{discover,validate,build,
  validate_and_build,self_audit,golden}/<mission_id>/`.

## 🐞 Correções relevantes no caminho p/ GA

- Retry/backoff em HTTP 429/5xx + resposta vazia triggera fallback (v4.3 hotfix).
- Repair do gate estático gracioso (não derruba a build).
- Parsing robusto de JSON do LLM (fences, truncamento, campos omitidos).
- Duplicatas semânticas por contenção; clichês rejeitados com motivo.
- Tipagem estática limpa (Pylance) em todos os módulos.

## 📈 Métricas de qualidade (GA)

- **~320 testes** passando (unit + integração), sem LLM/Docker no CI padrão.
- **Golden Missions:** 7/7 no dispatcher fake; bateria real sob `--run-golden`.
- **SELF-AUDIT:** veredito garantido `HEALTHY/DEGRADED` (nunca `CRITICAL`) com
  ecossistema saudável.

## ⬆️ Upgrade

Sem migrações de dados. Basta atualizar o `.env` a partir do novo
`.env.example` (variáveis novas têm defaults seguros).

**Obrigatório ler:** `ADR-017-GA-Release-Freeze` (regras do congelamento).