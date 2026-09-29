# Jogo 2D MVP – Nave vs. Asteroides

## Game Loop  
- **Duração**: Cada partida dura **30–60 segundos**.  
- **Loop**:  
  1. Processar entrada do jogador.  
  2. Atualizar posições de todas as entidades (player, asteroides, projéteis).  
  3. Detectar colisões e aplicar efeitos (dano, destruição).  
  4. Renderizar frame.  
  5. Repetir até o tempo expirar ou condição de fim de jogo.

## Entidades  
| Entidade | Descrição | Atributos Principais |
|----------|-----------|----------------------|
| **Player** | Nave do jogador | posição (x, y), velocidade, vida (1 vida = 1 hit), sprite |
| **Asteroid** | Obstáculo em movimento | posição (x, y), velocidade (direção aleatória), tamanho (pequeno/médio/grande), sprite |
| **Projectile** | Tiro disparado pelo player | posição (x, y), velocidade (para cima), sprite |

## Controles  
- **Movimento**:  
  - `←` / `→` (ou `A` / `D`) – mover nave horizontalmente.  
- **Atirar**:  
  - `Space` – dispara um projétil.  
- **Pause** (opcional):  
  - `Esc` – pausa/reinicia o jogo.

## Win/Lose Condition  
- **Win**: Jogador sobrevive até o fim do tempo (30–60 s).  
- **Lose**: Nave colide com um asteroide (vida = 0).  
- **Score**: (opcional) +1 ponto por cada asteroide destruído.

## Restrições  
- **Plataforma**: Web (HTML5 Canvas) ou desktop (SDL/Unity 2D).  
- **Performance**: ≤ 60 fps em hardware padrão.  
- **Assets**: Gráficos simples (sprites 32×32 ou 64×64), sons minimalistas.  
- **Código**: Modular, com classes/objetos para cada entidade.  
- **Testes**: Unitários mínimos para colisões e lógica de movimento.

## Não‑objetivos  
- Não incluir níveis, pontuação avançada ou power‑ups.  
- Não implementar IA complexa ou física avançada (gravidade, drag).  
- Não adicionar interface de usuário extensa (menus, configurações).  
- Não usar recursos de rede ou multiplayer.  

---  

**Resumo**: Um jogo de 30–60 s onde o jogador controla uma nave que dispara projéteis para destruir asteroides que se movem aleatoriamente. O objetivo é sobreviver até o fim do tempo. O MVP deve ser jogável, simples e focado apenas nas mecânicas básicas descritas acima.