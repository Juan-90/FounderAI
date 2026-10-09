# Objetivo  
Desenvolver um **jogo retro arcade space shooter 2D/3D** executado em **WebGL/Canvas (HTML5/JS)**, com um backend mínimo que permita **registrar e listar pontuações altas**. O produto será disponibilizado como **Web App / SaaS** para que usuários joguem no navegador e vejam suas pontuações em um ranking público.

---

# Usuários  
- **Jogadores casuais** que desejam jogar rapidamente no navegador.  
- **Desenvolvedores de jogos** que querem testar a API de pontuação em seus próprios projetos.  
- **Administradores** que precisam gerenciar a lista de pontuações (exclusão de entradas inválidas).

---

# MVP  

## Recursos CRUD / APIs  
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| **POST** | `/games/start` | Inicia uma nova sessão de jogo (retorna `gameId`). |
| **POST** | `/games/:gameId/score` | Envia a pontuação final de uma sessão (`score`, `playerName`). |
| **GET** | `/highscores` | Lista as 10 pontuações mais altas (ordenadas decrescente). |
| **DELETE** | `/highscores/:id` | Remove uma pontuação específica (admin). |

> **Observação**: Todos os endpoints retornam JSON.  

## Persistência  
- Banco de dados **relacional** (PostgreSQL ou SQLite em produção).  
- Tabela `highscores` com campos: `id (PK)`, `player_name`, `score`, `created_at`.  
- Índice em `score` para consulta rápida.  

## Listagem  
- A rota `/highscores` devolve um array JSON contendo objetos `{ id, player_name, score, created_at }`.  
- Apenas os **top 10** são retornados; paginação não é necessária no MVP.  

## Exclusão/Cancelamento  
- Endpoint `DELETE /highscores/:id` permite remover pontuações inválidas ou abusivas.  
- Não há cancelamento de sessões de jogo em andamento (o jogo roda apenas no cliente).  

---

# Restrições  

1. **Compatibilidade**: deve funcionar em navegadores modernos (Chrome, Firefox, Edge, Safari) sem plugins.  
2. **Performance**: o loop de jogo deve manter **≥ 60 FPS** em dispositivos de média performance.  
3. **Segurança**:  
   - Autenticação mínima (API key opcional) apenas para exclusão de pontuações.  
   - Validação de entrada para evitar injeção SQL.  
4. **Escalabilidade**: o backend deve suportar até **10 000 requisições por minuto** (pico de jogadores).  
5. **Licença**: todo o código deve ser **MIT** ou equivalente.  

---

# Não-objetivos  

- Multiplayer online ou matchmaking.  
- Física avançada (ragdoll, colisão 3D complexa).  
- Gráficos 3D avançados (shaders complexos, iluminação global).  
- Integração com redes sociais ou leaderboard externo.  
- Persistência de estado de jogo (save/load).  
- Suporte a dispositivos móveis nativos (iOS/Android apps).  
- Análise de dados em tempo real (dashboards).  

---