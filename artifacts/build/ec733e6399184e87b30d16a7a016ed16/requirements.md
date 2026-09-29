# Requisitos do Jogo 2D – Nave vs. Asteroides

## Game Loop  
- **Duração da partida**: 30 – 60 segundos.  
- **Sequência**:  
  1. Inicialização (tela de título, instruções).  
  2. Loop principal:  
     - Processar entrada.  
     - Atualizar posições de todas as entidades.  
     - Detectar colisões.  
     - Renderizar frame.  
  3. Finalização: exibir pontuação e opção de reiniciar.  

## Entidades  
| Entidade | Descrição | Comportamento |
|----------|-----------|---------------|
| **Player (Nave)** | Sprite 2D com tamanho 32×32 px. | Movimenta-se horizontalmente na base da tela; dispara projéteis. |
| **Asteroid (Asteroide)** | Sprite 32×32 px, variação de tamanho (16, 32, 48 px). | Desce verticalmente a partir de posições aleatórias na parte superior; velocidade aumenta gradualmente. |
| **Projectile (Projétil)** | Sprite 8×16 px. | Voa verticalmente para cima a partir da posição atual da nave; desaparece ao sair da tela ou colidir com asteroide. |

## Controles  
- **Movimento**:  
  - `←` / `→` (ou `A` / `D`) – mover nave horizontalmente.  
- **Disparo**:  
  - `Space` – disparar projétil.  
- **Menu**:  
  - `Esc` – sair para tela de título.  

## Win/Lose Condition  
- **Vitoria**:  
  - Jogador atira e destrói **10 asteroides** antes do tempo acabar.  
- **Derrota**:  
  - Tempo esgotado **ou** nave colide com um asteroide.  

## Restrições  
- **Plataforma**: Web (HTML5 Canvas) ou Desktop (SDL2).  
- **Linguagem**: JavaScript/TypeScript ou C++ (SDL2).  
- **Assets**: Gráficos 8‑bit simples; áudio opcional.  
- **Performance**: 60 fps mínimo.  
- **Tamanho**: Código‑base ≤ 5 000 linhas.  

## Não‑objetivos  
- Não incluir níveis múltiplos ou progressão de dificuldade.  
- Não implementar power‑ups, upgrades ou inimigos adicionais.  
- Não usar física avançada (colisões apenas por bounding box).  
- Não adicionar interface de usuário complexa (menus, configurações).  

---  

**Obs.**: Este documento define apenas o MVP mínimo para que o jogo seja jogável e demonstrável. Qualquer extensão futura deve ser avaliada separadamente.