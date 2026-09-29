# game.py
import random
from entities import Player, Asteroid, Projectile


class Game:
    def __init__(self, width=640, height=480, spawn_interval=2.0, max_time=30.0):
        self.width = width
        self.height = height
        self.spawn_interval = spawn_interval
        self.max_time = max_time

        self.player = Player(x=width // 2, y=height - 50)
        self.projectiles = []
        self.asteroids = []

        self.score = 0
        self.time_remaining = max_time
        self.state = "running"  # "running", "won", "lost"

        self.spawn_timer = 0.0

    # ------------------------------------------------------------------
    # Event handling (pygame only)
    # ------------------------------------------------------------------
    def handle_event(self, event):
        import pygame  # local import to keep logic headless
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.player.vx = -self.player.speed
            elif event.key == pygame.K_RIGHT:
                self.player.vx = self.player.speed
            elif event.key == pygame.K_UP:
                self.player.vy = -self.player.speed
            elif event.key == pygame.K_DOWN:
                self.player.vy = self.player.speed
            elif event.key == pygame.K_SPACE:
                self.projectiles.append(self.player.shoot())
        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.player.vx = 0
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                self.player.vy = 0

    # ------------------------------------------------------------------
    # Core game logic (no pygame imports)
    # ------------------------------------------------------------------
    def update(self, dt):
        if self.state != "running":
            return

        # Time management
        self.time_remaining -= dt
        if self.time_remaining <= 0:
            self.time_remaining = 0
            self.state = "lost"
            return

        # Spawn asteroids
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_asteroid()
            self.spawn_timer = self.spawn_interval

        # Update entities
        self.player.update(dt, self.width, self.height)
        for p in list(self.projectiles):
            p.update(dt)
            if p.y < 0:
                self.projectiles.remove(p)

        for a in list(self.asteroids):
            a.update(dt)
            if a.y > self.height:
                self.asteroids.remove(a)

        # Collision detection
        self.handle_collisions()

    # ------------------------------------------------------------------
    # Rendering (pygame only)
    # ------------------------------------------------------------------
    def render(self, screen):
        import pygame
        # Draw player
        pygame.draw.rect(screen, (0, 255, 0), self.player.rect)
        # Draw projectiles
        for p in self.projectiles:
            pygame.draw.rect(screen, (255, 255, 0), p.rect)
        # Draw asteroids
        for a in self.asteroids:
            pygame.draw.rect(screen, (255, 0, 0), a.rect)
        # Draw score and timer
        font = pygame.font.SysFont(None, 24)
        score_surf = font.render(f"Score: {self.score}", True, (255, 255, 255))
        timer_surf = font.render(f"Time: {int(self.time_remaining)}", True, (255, 255, 255))
        screen.blit(score_surf, (10, 10))
        screen.blit(timer_surf, (10, 30))

        # End‑game overlay
        if self.state in ("won", "lost"):
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            msg = "You Win!" if self.state == "won" else