# Game Loop  
- **Duration**: Each match lasts **30–60 seconds**.  
- **Timing**: Fixed‑time step (e.g., 60 fps).  
- **Sequence**:  
  1. Process input.  
  2. Update entities (movement, collision, spawning).  
  3. Render frame.  
  4. Check win/lose condition.  
  5. Repeat until time expires or player loses.

# Entidades  
- **Player**  
  - Sprite: 2‑D ship.  
  - Position: bottom‑center of screen.  
  - Movement: left/right (or up/down if desired).  
  - Lives: 1 (game over on hit).  
- **Asteroid**  
  - Sprite: circular/irregular shape.  
  - Spawn: random X at top, falling down at constant speed.  
  - Size: single size (no scaling).  
  - Collision: destroys player on overlap.  
- **Projectile**  
  - Sprite: small bullet.  
  - Fired: from player’s current position.  
  - Direction: straight up.  
  - Lifetime: until off‑screen or hits asteroid.  
  - Effect: destroys asteroid on hit, awards points.

# Controles  
- **Keyboard**  
  - Left/Right arrows (or A/D): move horizontally.  
  - Spacebar: fire projectile.  
- **Optional**: Mouse click to fire (if desired).

# Win/Lose Condition  
- **Win**: Survive the full 30–60 seconds.  
- **Lose**: Player collides with an asteroid (or projectile count reaches zero if you add ammo).  
- **Score**: (Optional) Points per asteroid destroyed; displayed at end.

# Restrições  
- **Platform**: Web browser (HTML5 Canvas) or desktop (SDL/pygame).  
- **Assets**: Use simple shapes or free sprites; no external art packs.  
- **Performance**: ≤ 60 fps on typical mid‑range hardware.  
- **Code**: Single file per language (e.g., `main.py`, `index.html`).  
- **Dependencies**: Only standard libraries or widely available open‑source libs.

# Não‑objetivos  
- No power‑ups, upgrades, or multiple levels.  
- No sound effects or music.  
- No complex physics or particle effects.  
- No high‑score leaderboard or persistence.  
- No network/multiplayer support.