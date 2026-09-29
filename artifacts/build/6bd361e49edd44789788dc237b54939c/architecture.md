# Stack  
- **pygame** – renderização 2D, entrada e áudio.  
- **Pytest** – testes unitários para lógica de movimento e colisões.

# Arquivos Necessários  
- `main.py` – ponto de entrada, inicializa pygame, cria instância de `Game` e entra no loop.  
- `game.py` – contém a classe `Game` que gerencia entidades, tempo, lógica de jogo e renderização.  
- `entities.py` – define classes `Player`, `Asteroid`, `Projectile` e utilitários de colisão.

# Separação Lógica vs Renderização  
- **Lógica** (sem `pygame.init`)  
  - Todas as classes (`Player`, `Asteroid`, `Projectile`) operam apenas com coordenadas, velocidades e estados.  
  - Métodos `update(dt)` e `collides_with(other)` são puros, não dependem de pygame.  
  - Testes unitários podem instanciar objetos e chamar esses métodos sem inicializar o módulo pygame.  
- **Renderização**  
  - Responsável apenas por desenhar sprites no `pygame.Surface`.  
  - Funções de renderização recebem objetos de lógica e acessam atributos como `pos` e `sprite`.  
  - Mantém a camada de apresentação isolada, permitindo que a lógica seja testada em qualquer ambiente.

# Game Loop  
```python
# main.py
import pygame
from game import Game

def main():
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    clock = pygame.time.Clock()
    game = Game(screen)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0  # segundos
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game.handle_input(event)

        game.update(dt)
        game.render()
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
```

- **Entrada** – `Game.handle_input(event)` atualiza estado do jogador.  
- **Atualização** – `Game.update(dt)` chama `update(dt)` de todas as entidades, gera asteroides, remove projeções fora da tela e verifica colisões.  
- **Renderização** – `Game.render()` desenha todas as entidades e HUD (tempo restante, vida).  
- **Loop** – repete até 30–60 s ou colisão fatal.

# Colisões e Pontuação  
- **Detecção** – método `collides_with(other)` usa retângulos (`pygame.Rect`) calculados a partir das posições e tamanhos dos sprites.  
- **Reação**  
  - *Player ↔ Asteroid* → vida do jogador decrementa; se vida == 0, fim de jogo.  
  - *Projectile ↔ Asteroid* → ambos são removidos; pontuação +1.  
- **Pontuação** – mantida em `Game.score`. Exibida no HUD.  
- **Testes** – com Pytest, verificam que:  
  - colisão entre dois objetos retorna `True`.  
  - colisão entre objetos não sobrepostos retorna `False`.  
  - disparar projétil reduz a lista de asteroides e aumenta a pontuação.  

---