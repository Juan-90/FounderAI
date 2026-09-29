# Requisitos do Jogo 2D – Nave vs. Asteroides

## Game Loop  
- **Duração da partida**: 30 – 60 segundos.  
- **Sequência**:  
  1. **Inicialização**: tela de título → menu de “Iniciar”.  
  2. **Loop principal**:  
     - Processar entrada do jogador.  
     - Atualizar posições de todas as entidades (nave, asteroides, projéteis).  
     - Detectar colisões.  
     - Renderizar frame.  
  3. **Fim de jogo**: exibir “Game Over” + pontuação → opção de reiniciar.  

## Entidades  
| Entidade | Descrição | Comportamento |
|----------|-----------|---------------|
| **Player (Nave)** | Sprite 32×32 px, pode mover em 4 direções (↑ ↓ ← →). | Velocidade fixa (ex.: 200 px/s). Pode disparar projéteis. |
| **Asteroid (Asteroide)** | Sprite 32×32 px, tamanho variável (pequeno, médio, grande). | Movimento aleatório em linha reta, velocidade crescente com a pontuação. Reaparece na borda oposta ao sair da tela. |
| **Projectile (Projétil)** | Sprite 8×16 px. | Veloz (ex.: 400 px/s), desaparece ao sair da tela ou colidir com asteroide. |

## Controles  
| Ação | Tecla / Botão |
|------|---------------|
| Mover para cima | ↑ ou W |
| Mover para baixo | ↓ ou S |
| Mover para esquerda | ← ou A |
| Mover para direita | → ou D |
| Disparar | Espaço ou botão esquerdo do mouse |

## Win/Lose Condition  
- **Perder**: Nave colide com qualquer asteroide.  
- **Vencer**: Jogador sobrevive até o fim do tempo (30‑60 s).  
- **Pontuação**: +10 pontos por asteroide destruído.  

## Restrições  
- **Plataforma**: Web (HTML5 Canvas) ou Desktop (SDL/pygame).  
- **Linguagem**: JavaScript/TypeScript ou Python (padrão).  
- **Assets**: Gráficos 2D simples (sprites PNG) e som minimalista (efeitos de tiro e colisão).  
- **Performance**: 60 fps, uso mínimo de memória.  
- **Compatibilidade**: Navegadores modernos ou sistemas operacionais suportados.  

## Não‑objetivos  
- Não incluir níveis, power‑ups ou upgrades.  
- Não implementar IA complexa ou física avançada (ex.: gravidade).  
- Não adicionar interface de usuário além da tela de título, Game Over e pontuação.  
- Não integrar backend ou persistência de dados.  

---  
**Obs.:** Este documento define apenas o escopo mínimo para um MVP jogável. Qualquer extensão futura deve ser documentada separadamente.