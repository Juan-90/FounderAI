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
        dt = clock.tick(60) / 1000.0  # seconds
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
