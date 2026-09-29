# Stack  
- **Python 3.10+**  
- **pygame** – rendering, input, timing  
- **pytest** – unit‑testing deterministic logic  

# Arquivos Necessários  
| Arquivo | Responsabilidade |
|---------|------------------|
| `main.py` | Inicializa pygame, cria a janela, instancia `Game`, entra no loop principal. |
| `game.py` | Contém a classe `Game` que gerencia estado global, loop de jogo, timers, pontuação e win/lose. |
| `entities.py` | Define classes `Player`, `Asteroid`, `Projectile` com lógica de movimento, colisão e renderização. |

# Separação Lógica vs Renderização  
- **Lógica Determinística**  
  - Todas as atualizações de estado (posição, colisões, spawn) são feitas em métodos que **não** importam `pygame`.  
  - `entities.py` expõe métodos `update(dt)` e `collides_with(other)` que operam apenas sobre atributos numéricos.  
  - Testes unitários (`tests/test_logic.py`) instanciam objetos sem chamar `pygame.init()` e verificam resultados de `update` e `collides_with`.  

- **Renderização Isolada**  
  - Métodos `draw(surface)` em cada entidade dependem apenas de `pygame.Surface`.  
  - `Game.render(surface)` chama `draw` de todas as entidades.  
  - Assim, a lógica pode ser testada sem qualquer dependência de `pygame`.  

# Game Loop  
```python
# main.py
import pygame
from game import Game

def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    clock = pygame.time.Clock()
    game = Game(screen)

    while not game.is_over:
        dt = clock.tick(60) / 1000.0          # Fixed 60 fps
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.is_over = True
            else:
                game.handle_input(event)

        game.update(dt)
        game.render()
        pygame.display.flip()

    pygame.quit()
    print(f"Score: {game.score}")

if __name__ == "__main__":
    main()
```

- **Process Input** – `Game.handle_input(event)` updates player velocity or fires projectile.  
- **Update** – `Game.update(dt)` calls `update(dt)` on player, all asteroids, and projectiles; spawns new asteroids; checks collisions; updates timer and score.  
- **Render** – `Game.render()` clears screen, draws all entities, draws HUD (time left, score).  
- **Win/Lose** – `Game.is_over` becomes `True` when time expires or player collides with an asteroid.  

# Colisões e Pontuação  
- **Colisão**  
  - `Entity.collides_with(other)` usa bounding‑box (rect) ou circunferência para detecção simples.  
  - Quando `Player` colide com `Asteroid` → `Game.is_over = True`.  
  - Quando `Projectile` colide com `Asteroid` → ambos são removidos, `Game.score += 10`.  

- **Pontuação**  
  - `Game.score` inicia em 0.  
  - Cada destruição de asteroide adiciona 10 pontos.  
  - Pontuação exibida no HUD e impressa no console ao fim do jogo.  

---  

**Observação**: O código acima é apenas a estrutura; a implementação detalhada de cada classe e método segue a mesma separação lógica/visual, garantindo que a lógica seja totalmente testável com `pytest` sem dependência de `pygame`.