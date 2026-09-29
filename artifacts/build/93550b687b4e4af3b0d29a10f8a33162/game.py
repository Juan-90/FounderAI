# game.py
import random
from entities import Player, Asteroid, Projectile

# Constants for the game
DEFAULT_MAX_DURATION = 60.0  # seconds
ASTEROID_SPAWN_INTERVAL = 2.0  # seconds

class Game:
    def __init__(self, screen_width, screen_height, max_duration=DEFAULT_MAX_DURATION):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.max_duration = max_duration
        self.elapsed_time = 0.0
        self.time_left = max_duration
        self.game_over = False
        self.score = 0

        # Entities
        self.player = Player(screen_width / 2, screen_height - 50)
        self.asteroids = []
        self.projectiles = []

        # Asset placeholders (set in load_assets)
        self.player_sprite = None
        self.asteroid_sprite = None
        self.projectile_sprite = None
        self.font = None

        # Timing for asteroid spawn
        self.time_since_last_spawn = 0.0

    # ---------------------------------------------------------------------
    # Asset loading (only called from main.py)
    # ---------------------------------------------------------------------
    def load_assets(self):
        import pygame
        # Simple colored surfaces