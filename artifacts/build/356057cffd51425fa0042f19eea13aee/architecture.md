# Stack  
- **FastAPI** – framework de API REST.  
- **SQLite** – banco de dados relacional leve (prod: PostgreSQL).  
- **Uvicorn** – servidor ASGI para execução.  
- **Pydantic** – validação de dados e serialização.  
- **Pytest** – testes unitários e de integração.  

# Arquivos Necessários  
- `main.py` – ponto de entrada da aplicação.  
- `models.py` – definição de modelos ORM (SQLAlchemy).  
- `schemas.py` – esquemas Pydantic para requisição/resposta.  
- `database.py` – configuração de conexão e sessão de banco.  
- `test_main.py` – testes automatizados com Pytest.  

# Responsabilidades por Arquivo  

| Arquivo | Responsabilidade |
|---------|------------------|
| **main.py** | 1. Instancia `FastAPI`. <br>2. Configura rotas (`/games/start`, `/games/{gameId}/score`, `/highscores`, `/highscores/{id}`). <br>3. Implementa lógica de negócio (iniciar sessão, gravar pontuação, listar top‑10, deletar). <br>4. Gera `gameId` (UUID) e armazena temporariamente em memória (ou cache). |
| **models.py** | 1. Define classe `HighScore` (id, player_name, score, created_at). <br>2. Configura mapeamento SQLAlchemy para SQLite. |
| **schemas.py** | 1. Define `GameStartResponse` (gameId). <br>2. Define `ScoreSubmitRequest` (score, player_name). <br>3. Define `HighScoreOut` (id, player_name, score, created_at). |
| **database.py** | 1. Cria engine SQLite (`sqlite:///./highscores.db`). <br>2. Gera `SessionLocal` para acesso ao banco. <br>3. Função `get_db()` para injeção de dependência. |
| **test_main.py** | 1. Testa endpoints CRUD com `TestClient`. <br>2. Verifica validação de entrada, retorno JSON, status codes. <br>3. Usa fixture de banco em memória para isolamento. |

# Fluxo de Dados  

1. **Iniciar Jogo**  
   - Cliente faz `POST /games/start`.  
   - `main.py` gera `gameId` (UUID) e devolve `{ "gameId": "<uuid>" }`.  
   - `gameId` é usado apenas no cliente; não persiste no banco.  

2. **Enviar Pontuação**  
   - Cliente faz `POST /games/{gameId}/score` com corpo `{ "score": 1234, "player_name": "Alice" }`.  
   - `main.py` valida via `ScoreSubmitRequest`.  
   - Cria registro `HighScore` em SQLite (via `database.py`).  
   - Retorna `{ "id": 1, "player_name": "Alice", "score": 1234, "created_at": "2026‑10‑09T12:34:56Z" }`.  

3. **Listar Top 10**  
   - Cliente faz `GET /highscores`.  
   - `main.py` consulta `HighScore` ordenado por `score DESC`, limita 10.  
   - Retorna array de `HighScoreOut`.  

4. **Excluir Pontuação (Admin)**  
   - Cliente faz `DELETE /highscores/{id}` com header `X-API-Key: <key>`.  
   - `main.py` verifica chave (simples env var).  
   - Remove registro do banco.  
   - Retorna `204 No Content`.  

5. **Persistência**  
   - Todas as operações de gravação/leitura usam sessão gerada por `database.py`.  
   - Índice em `score` garante consulta rápida.  

6. **Testes**  
   - `test_main.py` usa `TestClient` de FastAPI para simular chamadas HTTP.  
   - Cada teste cria/limpa banco em memória, garantindo isolamento.  

---