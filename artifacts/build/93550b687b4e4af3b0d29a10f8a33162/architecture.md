# Arquitetura do Jogo 2D – Nave vs. Asteroides

## # Stack  
- **Python 3.10+**  
- **pygame** – renderização, entrada e áudio.  
- **Pytest** – testes unitários da lógica (sem dependência de pygame).  

## # Arquivos Necessários  
| Arquivo | Responsabilidade |
|---------|------------------|
| **main.py** | Inicializa pygame, cria a janela, instancia `Game` e entra no loop principal. |
| **game.py** | Contém a classe `Game` que gerencia estado, entidades, lógica de atualização, colisões e pontuação. |
| **entities.py** | Define classes `Player`, `Asteroid`, `Projectile` com atributos de posição, velocidade, sprite e métodos de movimento. |

## # Separação Lógica vs Renderização  
- **Lógica** (testável)  
  - Todas as classes (`Player`, `Asteroid`, `Projectile`, `Game`) operam apenas com coordenadas, velocidades e estados.  
  - Métodos de atualização (`update(dt)`) e colisão (`collides_with(other)`) não importam pygame.  
  - Testes Pytest podem instanciar objetos e chamar `update`/`collides_with` sem chamar `pygame.init()`.  
- **Renderização** (isolada)  
  - `Game.render(screen)` recebe o objeto `pygame.Surface` e desenha sprites usando `blit`.  
  - Sprites são carregados em `Game.load_assets()` (executado apenas em `main.py`).  
  - Nenhum código de lógica chama pygame diretamente; apenas `Game.render` faz isso.

## # Game Loop  
```text
while running:
    dt = clock.tick(60) / 1000.0          # delta time em segundos
    handle_input()                        # pygame.event.get()
    game.update(dt)                       # lógica determinística
    game.render(screen)                   # desenho
    pygame.display.flip()
```
- **handle_input**: atualiza `Player`’s direction e dispara projéteis.  
- **game.update(dt)**:  
  - Move todas as entidades.  
  - Remove projéteis fora da tela.  
  - Reaparece asteroides na borda oposta.  
  - Detecta colisões e atualiza pontuação.  
  - Verifica tempo restante → `game_over`.  
- **game.render(screen)**: desenha fundo, entidades e HUD (tempo, pontuação).  

## # Colisões e Pontuação  
- **Detecção**: `pygame.Rect.colliderect` ou bounding‑box manual (retângulos 32×32 ou 8×16).  
- **Colisão Nave‑Asteroide** → `game_over = True`.  
- **Colisão Projectile‑Asteroide** →  
  - Remove ambos.  
  - `score += 10`.  
  - Cria novo asteroide na borda oposta.  
- **Pontuação**: exibida no HUD; persistida apenas na memória.  
- **Tempo**: `time_left = max_duration - elapsed_time`.  
- **Vitoria**: se `time_left <= 0` e `not game_over` → vitória.  

---  
Este documento descreve a estrutura mínima e testável do MVP, permitindo que a lógica seja validada com Pytest sem dependência de pygame, enquanto a renderização permanece isolada em `main.py`.