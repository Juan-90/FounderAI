# Stack  
- **Python 3.11+**  
- **Pygame** – 2D rendering, input, and timing.  
- **Pytest** – unit‑testing the deterministic game logic (no Pygame init).  

# Arquivos Necessários  
| Arquivo | Responsabilidade |
|---------|------------------|
| **main.py** | Inicializa Pygame, cria a janela, instancia `Game`, e entra no loop principal. |
| **game.py** | Contém a classe `Game` que gerencia o estado global, o loop de jogo, timers, e delega atualizações/renderização para os módulos de lógica e renderização. |
| **entities.py** | Define as classes `Player`, `Asteroid`, `Projectile` e os métodos de atualização, colisão e desenho. |

# Separação Lógica vs Renderização  
- **Lógica** (`entities.py` + `game.py`):  
  - Operações matemáticas, física, colisões e timers são puras funções/objetos Python.  
  - Não importam `pygame` nem chamam `pygame.init()`.  
  - Testáveis com **Pytest**: instanciar objetos, chamar `update(dt)` e verificar estados.  

- **Renderização** (`game.py` + `main.py`):  
  - Importa `pygame` apenas aqui.  
  - Converte estados lógicos em chamadas de desenho (`blit`, `draw.circle`, etc.).  
  - Mantém a lógica livre de dependências de Pygame, permitindo execução em ambientes sem display (CI).  

# Game Loop  
```text
while not game_over:
    dt = clock.tick(60) / 1000.0          # 60 fps → ~16.67 ms/frame
    # 1. Input
    events = pygame.event.get()
    for e in events:
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.KEYDOWN:
            player.handle_key(e.key, True)
        elif e.type == pygame.KEYUP:
            player.handle_key(e.key, False)

    # 2. Update
    game.update(dt)                       # move entities, handle collisions

    # 3. Render
    screen.fill((0, 0, 0))
    game.render(screen)                   # draw all sprites
    draw_timer(screen, elapsed_time)

    # 4. Check End
    if elapsed_time >= match_duration:
        game_over = True
```
- `game.update(dt)` chama `update(dt)` de cada entidade, aplica colisões e remove objetos expirados.  
- `game.render(screen)` delega a cada entidade seu próprio método `draw(surface)`.  

# Colisões e Pontuação  
- **Detecção**:  
  - **Player–Asteroid**: `pygame.sprite.collide_circle` (radius based).  
  - **Projectile–Asteroid**: same circle collision.  
  - Colisões são resolvidas na fase de atualização; colisão entre player e asteroide termina o jogo.  
- **Pontuação**:  
  - Não há pontuação, mas a lógica pode contar “asteroids_destroyed” para métricas de teste.  
  - Cada `Projectile` tem `lifespan = 2.0 s`; é removido se `age > lifespan`.  
- **Estado de vitória/derrota**:  
  - `Game` mantém `self.won` e `self.lost`.  
  - `self.lost` é definido quando `player.health <= 0`.  
  - `self.won` é definido quando `elapsed_time >= match_duration`.  

---