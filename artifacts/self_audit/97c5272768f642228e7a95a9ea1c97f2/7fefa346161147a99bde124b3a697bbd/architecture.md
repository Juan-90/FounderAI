# Arquitetura do Web App – Barbearia Online

## Stack
- **FastAPI** – framework web assíncrono  
- **SQLite** – banco de dados relacional leve (para MVP)  
- **Uvicorn** – servidor ASGI  
- **Pydantic** – validação de dados e serialização  
- **Pytest** – testes automatizados

## Arquivos Necessários
| Arquivo | Descrição |
|---------|-----------|
| `main.py` | Ponto de entrada da aplicação, definição de rotas e inicialização do servidor. |
| `models.py` | Definição das tabelas ORM (SQLAlchemy) – `Cliente`, `Barbeiro`, `Servico`, `Agendamento`. |
| `schemas.py` | Schemas Pydantic para entrada/saída das APIs. |
| `database.py` | Configuração da conexão SQLite, criação do `SessionLocal` e `Base`. |
| `test_main.py` | Testes de integração das rotas CRUD usando `TestClient` do FastAPI. |

## Responsabilidades por Arquivo

| Arquivo | Responsabilidades |
|---------|-------------------|
| **main.py** | • Importa `FastAPI`, `Depends`, `HTTPException`. <br>• Cria instância `app = FastAPI()`. <br>• Define rotas CRUD (`/agendamentos`). <br>• Usa `Depends(get_db)` para injeção de sessão. <br>• Configura middleware de CORS (opcional). <br>• Executa `uvicorn.run(app, host="0.0.0.0", port=8000)` quando chamado diretamente. |
| **models.py** | • Importa `Base`, `Column`, `Integer`, `String`, `DateTime`, `ForeignKey`. <br>• Define classes `Cliente`, `Barbeiro`, `Servico`, `Agendamento` com relacionamentos. <br>• Inclui campo `cancelado_em` em `Agendamento` para soft‑delete. |
| **schemas.py** | • Importa `BaseModel`, `Field`, `datetime`. <br>• Cria `ClienteCreate`, `BarbeiroCreate`, `ServicoCreate`, `AgendamentoCreate`. <br>• Cria `AgendamentoRead`, `AgendamentoUpdate`. <br>• Define enum `StatusAgendamento` (agendado, cancelado, concluído). |
| **database.py** | • Configura `engine = create_engine("sqlite:///./barbearia.db", connect_args={"check_same_thread": False})`. <br>• Cria `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`. <br>• Função `get_db()` que gera e fecha sessão. <br>• Função `init_db()` que chama `Base.metadata.create_all(bind=engine)`. |
| **test_main.py** | • Usa `TestClient` do FastAPI. <br>• Testa criação, leitura, atualização e exclusão de agendamentos. <br>• Verifica status HTTP e payloads. <br>• Configura fixture `client` que roda `init_db()` antes dos testes. |

## Fluxo de Dados

1. **Cliente** envia `POST /agendamentos` com JSON contendo `cliente_id`, `barbeiro_id`, `servico_id`, `data_hora`.  
2. `main.py` recebe a requisição, valida com `AgendamentoCreate` (Pydantic).  
3. `database.py` fornece sessão `db`.  
4. `models.py` cria instância `Agendamento` e persiste no SQLite.  
5. Resposta `AgendamentoRead` é retornada (Pydantic serializa).  

6. **Listagem**: `GET /agendamentos` → `main.py` consulta `Agendamento` filtrando por `cliente_id` ou `barbeiro_id`, aplica paginação (10 por página) e retorna lista de `AgendamentoRead`.  

7. **Atualização**: `PUT /agendamentos/{id}` → valida com `AgendamentoUpdate`, atualiza campos `data_hora` ou `servico_id`.  

8. **Exclusão/Cancelamento**: `DELETE /agendamentos/{id}` → seta `cancelado_em = datetime.utcnow()` (soft delete).  

9. **Notificação** (opcional): após cancelamento, `main.py` pode disparar função de envio de e‑mail (não implementado no MVP).  

10. **Testes**: `test_main.py` executa chamadas simuladas via `TestClient`, assegurando que cada endpoint responde corretamente e que a lógica de soft delete funciona.  

---

> **Observação**: Este documento descreve apenas a estrutura mínima para um MVP funcional. Para produção, recomenda‑se migração para PostgreSQL, autenticação JWT, e deploy em Docker/Heroku.