# O que foi construído  
- Um arquivo `main.py` contendo a estrutura inicial de um jogo 2D em Python, usando a biblioteca **Pygame**.  
- O código define a janela do jogo, carrega uma sprite de nave e um sprite de asteroide, e implementa a lógica básica de movimentação da nave com as teclas de seta.  
- O loop principal do jogo atualiza a posição da nave, desenha os sprites na tela e mantém a taxa de frames em 60 FPS.  

# Resultado das Análises e Testes  
| Ferramenta | Status | Observações |
|------------|--------|-------------|
| **ruff** | ❌ Falha | Erros de linting (ex.: variáveis não utilizadas, importações desnecessárias). |
| **mypy** | ✅ OK | Tipagem estática não apresentou problemas. |
| **Testes** | ❌ Nenhum | Não há arquivos de teste; o jogo não foi executado em ambiente de CI. |

# Limitações  
- **Sem lógica de colisão**: a nave não interage com os asteroides.  
- **Sem pontuação ou vidas**: o jogo não possui mecânicas de pontuação ou controle de vidas.  
- **Ausência de recursos visuais**: apenas sprites simples; não há animações ou efeitos de fogo.  
- **Código não modularizado**: tudo está em um único arquivo, dificultando a manutenção e expansão.  
- **Falha de linting**: `ruff` indica problemas de estilo que precisam ser corrigidos antes de prosseguir.  

# Próximos passos  
1. **Refatorar** `main.py` em módulos separados (`game.py`, `player.py`, `asteroid.py`, `utils.py`).  
2. **Adicionar lógica de colisão** entre nave e asteroides, com remoção de asteroides e decremento de vidas.  
3. **Implementar pontuação** e exibição na tela.  
4. **Corrigir erros de linting** (`ruff`) e garantir que o código siga as convenções PEP8.  
5. **Criar testes unitários** (ex.: `test_player.py`, `test_collision.py`) usando `pytest`.  
6. **Adicionar recursos visuais** (sprites animados, efeitos de explosão).  
7. **Configurar CI** para rodar `ruff`, `mypy` e os testes automaticamente.