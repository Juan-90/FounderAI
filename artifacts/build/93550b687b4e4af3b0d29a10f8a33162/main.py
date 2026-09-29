# main.py
import pygame
import sys
from game import Game

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Frames per second
FPS = 60


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Nave vs. Asteroides")
    clock = pygame.time.Clock()

    # Create game instance and load assets
    game = Game(screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
    game.load_assets()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0  # delta time in seconds

        # --- Input handling -------------------------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    game.player.set_velocity(-game.player.speed, 0)
                elif event.key == pygame.K_RIGHT:
                    game.player.set_velocity(game.player.speed, 0)
                elif event.key == pygame.K_UP:
                    game.player.set_velocity(0, -game.player.speed)
                elif event.key == pygame.K_DOWN:
                    game.player.set_velocity(0, game.player.speed)
                elif event.key == pygame.K_SPACE:
                    game.fire_projectile()
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                    # Stop movement when any arrow key is released
                    game.player.set_velocity(0, 0)

        # --- Game logic -----------------------------------------------------
        game.update(dt)

        # --- Rendering ------------------------------------------------------
        game.render(screen)
        pygame.display.flip()

        # Check for game over or victory
        if game.game_over or game.victory:
            running = False

    # Show final screen for a moment
    pygame.time.wait(2000)
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
