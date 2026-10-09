# Arquitetura do MVP – Web App (FastAPI + SQLite)

## Stack
- **FastAPI** – framework web assíncrono, alto desempenho e suporte nativo a OpenAPI.  
- **SQLite** – banco de dados embutido, ideal para MVP com baixo custo e fácil deploy.  
- **Uvicorn** – servidor ASGI que roda a aplicação FastAPI.  
- **Pydantic** – validação de dados e serialização de modelos.  
- **Pytest** – framework de testes unitários e de integração.

---

## Arquivos Necessários
| Arquivo | Descrição |
|---------|-----------|
| `main.py` | Ponto de entrada da aplicação, definição de rotas e inicialização do servidor. |
| `models.py` | Modelos ORM (SQLAlchemy) que mapeiam as tabelas `users`, `medicamentos`, `alarme`, `panico`. |
| `schemas.py` | Schemas Pydantic para validação de entrada/saída (DTOs). |
| `database.py` | Configuração da conexão SQLite, criação do `SessionLocal` e `Base`. |
| `test_main.py` | Testes de integração das rotas principais usando `TestClient`. |

---

## Responsabilidades por Arquivo

| Arquivo | Responsabilidade Principal |
|---------|---------------------------|
| **main.py** | • Configura o `FastAPI` app.<br>• Define endpoints CRUD para cada entidade.<br>• Integra middlewares (CORS, autenticação JWT).<br>• Inicia o Uvicorn quando executado como script. |
| **models.py** | • Declara classes SQLAlchemy (`User`, `Medicamento`, `Alarme`, `Panico`).<br>• Define relacionamentos, índices e campos de soft‑delete (`deleted_at`). |
| **schemas.py** | • Cria modelos Pydantic (`UserCreate`, `UserRead`, `MedicamentoCreate`, etc.).<br>• Garante validação de tipos, formatos de data/hora e regras de negócio simples. |
| **database.py** | • Cria engine SQLite (`sqlite:///./app.db`).<br>• Gera `SessionLocal` para injeção de dependência.<br>• Executa `Base.metadata.create_all()` na inicialização. |
| **test_main.py** | • Usa `TestClient` para simular requisições HTTP.<br>• Testa criação, leitura, atualização e exclusão (soft delete).<br>• Verifica respostas HTTP, status codes e payloads. |

---

## Fluxo de Dados

1. **Requisição HTTP**  
   - O cliente (React ou outro front‑end) envia uma requisição para `POST /api/users` (exemplo).  
   - O Uvicorn recebe a requisição e encaminha para o FastAPI.

2. **Validação Pydantic**  
   - FastAPI converte o corpo JSON em `UserCreate` (schema).  
   - Se houver erro de validação, retorna 422.

3. **Persistência**  
   - `main.py` chama `get_db()` (dependência) para obter `SessionLocal`.  
   - `models.User` é instanciado e adicionado ao `session`.  
   - `session.commit()` grava no SQLite.

4. **Resposta**  
   - FastAPI converte o objeto `User` em `UserRead` (schema) e devolve 201 Created.

5. **Soft Delete**  
   - Ao chamar `DELETE /api/users/{id}`, o endpoint atualiza `deleted_at` em vez de remover a linha.  
   - Consultas subsequentes filtram por `deleted_at IS NULL`.

6. **Alarme & Pânico**  
   - `POST /api/alarme` cria registro com `next_trigger` calculado.  
   - Um job background (FastAPI `BackgroundTasks`) pode ser adicionado para disparar notificações.  
   - `POST /api/panico` grava evento; cuidadores recebem webhook/notification.

7. **Auditoria**  
   - Cada operação crítica (create, update, delete) dispara inserção em `audit_log` (não detalhado aqui, mas pode ser adicionado em `models.py`).

8. **Testes**  
   - `test_main.py` executa as mesmas rotas via `TestClient`, garantindo que a lógica de negócio e a camada de persistência funcionem corretamente.

---

### Observações de Implementação

- **Segurança**: JWT implementado em `main.py` com dependência `get_current_user`.  
- **Acessibilidade**: Front‑end (React) deve usar fontes ≥18 px e contraste ≥4.5:1; rotas de API não afetam diretamente.  
- **Escalabilidade**: SQLite é suficiente para MVP; migração para PostgreSQL pode ser feita alterando `engine` em `database.py`.  
- **Infraestrutura**: Dockerfile simples com `uvicorn main:app --host 0.0.0.0 --port 8000`.  
- **Testes**: Pytest + `pytest-asyncio` para rotas assíncronas; cobertura mínima 80 %.  

---