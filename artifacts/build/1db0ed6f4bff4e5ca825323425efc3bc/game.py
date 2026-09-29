# game.py
import random
from entities import Player, Asteroid, Projectile


class Game:
    def __init__(self, screen, duration=60.0, spawn_interval=2.0):
        self.screen = screen
        self.duration = duration
        self.time_left = duration
        self.spawn_interval = spawn_interval
        self.spawn_timer = 0.0
        self.is_over = False
        self.score = 0

        # Initialize player at bottom center
        self.player = Player(400, 550, 0, 0)
        self.asteroids = []
        self.projectiles = []

    # ---------- Input ----------
    def handle_input(self, event):
        import pygame  # local import to keep logic pygame‑free
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.player.vx = -200
            elif event.key == pygame.K_RIGHT:
                self.player.vx = 200
            elif event.key == pygame.K_UP:
                self.player.vy = -200
            elif event.key == pygame.K_DOWN:
                self.player.vy = 200
            elif event.key == pygame.K_SPACE:
                # Fire a projectile upwards
                proj = Projectile(self.player.x, self.player.y, 0, -400)
                self.projectiles.append(proj)
        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.player.vx = 0
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                self.player.vy = 0

    # ---------- Game Logic ----------
    def update(self, dt):
        if self.is_over:
            return

        # Update timers
        self.time_left -= dt
        if self.time_left <= 0:
            self.is_over = True
            return

        # Spawn asteroids
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer -= self.spawn_interval
            self.asteroids.append(self.spawn_asteroid())

        # Update entities
        self.player.update(dt)
        for a in list(self.asteroids):
            a.update(dt)
        for p in list(self.projectiles):
            p.update(dt)

        # Collision detection
        # Projectile vs Asteroid
        for p in list(self.projectiles):
            for a in list(self.asteroids):
                if p.collides_with(a):
                    self.projectiles.remove(p)
                    self.asteroids.remove(a)
                    self.score += 10
                    break

        # Player vs Asteroid
        for a in self.asteroids:
            if self.player.collides_with(a):
                self.is_over = True
                break

    def spawn_asteroid(self):
        # Random position within screen bounds
        x = random.uniform(0, self.screen.get_width())
        y = random.uniform(0, self.screen.get_height() / 2)
        # Random velocity towards bottom
        vx = random.uniform(-50, 50)
        vy = random.uniform(50, 150)
        return Asteroid(x, y, vx, vy)

    # ---------- Rendering ----------
    def render(self):
        self.screen.fill((0, 0, 0))
        self.player.draw(self.screen)
        for a in self.asteroids:
            a.draw(self.screen)
        for p in self.projectiles:
            p.draw(self.screen)
        self.draw_hud()

    def draw_hud(self):
        import pygame
        font = pygame.font.SysFont(None, 24)
        score_surf = font.render(f"Score: {self.score}", True, (255, 255, 255))
        time_surf = font.render(f"Time: {int(self.time_left)}", True, (255, 255, 255))
        self.screen.blit(score_surf, (10, 10))
        self.screen.blit(time_surf, (10, 30))
