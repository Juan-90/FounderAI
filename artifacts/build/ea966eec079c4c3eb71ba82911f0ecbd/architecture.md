# Arquitetura do Web‑App – MVP “Shop‑Car”

## # Stack  
- **FastAPI** – framework web assíncrono.  
- **SQLite** – banco de dados relacional leve (dev / MVP).  
- **Uvicorn** – servidor ASGI.  
- **Pydantic** – validação de dados e serialização.  
- **Pytest** – testes unitários e de integração.

---

## # Arquivos Necessários  
| Arquivo | Descrição |
|---------|-----------|
| **main.py** | Ponto de entrada da aplicação; cria o `FastAPI`, inclui routers e configura middlewares. |
| **models.py** | Definições de modelos SQLAlchemy (tabelas `users`, `cars`, `proposals`, `simulations`). |
| **schemas.py** | Schemas Pydantic para validação de entrada/saída (DTOs). |
| **database.py** | Configuração da sessão SQLite, criação de engine e migrações simples. |
| **test_main.py** | Testes de integração com Pytest usando `TestClient` do FastAPI. |

---

## # Responsabilidades por Arquivo  

| Arquivo | Responsabilidade |
|---------|------------------|
| **main.py** | • Instancia `FastAPI`. <br>• Registra routers (`/api/cars`, `/api/proposals`, `/api/simulations`). <br>• Configura CORS, JWT auth e middlewares de logging. <br>• Inicia o servidor Uvicorn quando executado como script. |
| **models.py** | • Define classes `User`, `Car`, `Proposal`, `Simulation` como subclasses de `Base` (SQLAlchemy). <br>• Estabelece relacionamentos (`user.cars`, `car.proposals`). <br>• Inclui campos de soft‑delete (`deleted_at`). |
| **schemas.py** | • Cria Pydantic `BaseModel` para cada entidade: `CarCreate`, `CarRead`, `ProposalCreate`, `ProposalRead`, `SimulationRequest`, `SimulationResponse`. <br>• Garante validação de tipos e limites (ex.: preço > 0). |
| **database.py** | • Cria `engine` apontando para `sqlite:///shopcar.db`. <br>• Configura `SessionLocal` e `Base.metadata.create_all()`. <br>• Exporta `get_db()` como dependency para routers. |
| **test_main.py** | • Usa `TestClient` para enviar requisições HTTP simuladas. <br>• Testa endpoints CRUD, filtros, soft‑delete e cálculo de simulação. <br>• Verifica códigos de status, payloads e regras de negócio (ex.: vendedor não pode excluir carro com proposta pendente). |

---

## # Fluxo de Dados  

```
Cliente (React/Next.js) ──► 1. Requisição HTTP (GET/POST/PUT/DELETE) ──►
FastAPI (main.py) ──► 2. Middleware de Auth (JWT) ──►
FastAPI Router ──► 3. Validação Pydantic (schemas.py) ──►
FastAPI Router ──► 4. Operação de Banco (models.py via SessionLocal) ──►
SQLite (database.py) ──► 5. Resultado (rows, status) ──►
FastAPI Router ──► 6. Serialização Pydantic (schemas.py) ──►
FastAPI (main.py) ──► 7. Resposta HTTP (JSON) ──►
Cliente
```

- **Autenticação**: JWT enviado no header `Authorization: Bearer <token>`.  
- **Validação**: Schemas Pydantic garantem que dados de entrada estejam corretos antes de chegar ao banco.  
- **Persistência**: SQLAlchemy mapeia objetos Python para tabelas SQLite; operações são atômicas dentro de uma sessão.  
- **Soft‑Delete**: `deleted_at` é preenchido em vez de remover registro; filtros de listagem ignoram registros marcados.  
- **Simulação**: Endpoint `/api/simulations` recebe parâmetros, calcula parcelas (ex.: amortização simples) e devolve JSON.  
- **Notificações**: (não implementado no MVP) – placeholder para futura integração com WebSocket/Email.

---

> **Observação**: Este documento descreve a estrutura mínima e o fluxo de dados para o MVP. A implementação real deve seguir boas práticas de testes, logging e tratamento de exceções.