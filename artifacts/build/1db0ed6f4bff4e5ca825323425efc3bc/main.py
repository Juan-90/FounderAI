# main.py
import pygame
from game import Game


def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Asteroid Shooter")
    clock = pygame.time.Clock()
    game = Game(screen)

    while not game.is_over:
        dt = clock.tick(60) / 1000.0  # 60 FPS
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
