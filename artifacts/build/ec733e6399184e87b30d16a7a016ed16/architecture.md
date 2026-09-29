# Stack
- **pygame** – framework para renderização 2D e captura de entrada.  
- **Pytest** – framework de testes unitários para a lógica do jogo.

# Arquivos Necessários
- `main.py` – ponto de entrada, inicializa pygame, cria instância de `Game` e entra no loop principal.  
- `game.py` – contém a classe `Game` que gerencia estado, loop, timers, pontuação e transições de tela.  
- `entities.py` – define classes `Player`, `Asteroid`, `Projectile` e utilitários de colisão.

# Separação Lógica vs Renderização
- **Lógica**:  
  - Todas as atualizações de posição, colisões e pontuação são feitas em métodos que não importam `pygame`.  
  - `Game.update(dt)` recebe delta‑time e manipula objetos de `entities.py`.  
  - Testes unitários com **Pytest** chamam `Game.update` e verificam estados (posição, vida, pontuação) sem inicializar pygame.  
- **Renderização**:  
  - `Game.render(screen)` importa `pygame` apenas dentro deste método.  
  - Recebe o objeto `screen` criado em `main.py` e desenha sprites usando coordenadas já calculadas pela lógica.  
  - Assim, lógica e renderização são totalmente isoladas.

# Game Loop
```python
# main.py
import pygame
from game import Game

def main():
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    clock = pygame.time.Clock()
    game = Game()

    running = True
    while running:
        dt = clock.tick(60) / 1000.0  # segundos
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game.handle_event(event)

        game.update(dt)
        screen.fill((0, 0, 0))
        game.render(screen)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
```
- **handle_event**: traduz eventos de teclado em ações do `Player`.  
- **update**: atualiza todas as entidades, verifica colisões, controla spawn de asteroides e tempo restante.  
- **render**: delega desenho a cada entidade.

# Colisões e Pontuação
- **Detecção**: bounding‑box (rectângulo) simples usando `pygame.Rect` (apenas na camada de renderização).  
- **Colisão Nave‑Asteroide**: termina jogo (derrota).  
- **Colisão Projectile‑Asteroide**:  
  - Asteroide é removido.  
  - Se tamanho > 16 px, gera dois asteroides menores (tamanho/2).  
  - Pontuação +1.  
  - Quando pontuação ≥ 10 → vitória.  
- **Tempo**: contador de 30–60 s; quando zero, verifica vitória/derrota.  
- **Pontuação**: mantida em `Game.score`; exibida na tela de fim de jogo.