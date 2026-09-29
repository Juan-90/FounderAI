# Game Loop  
- **Duration**: Each match lasts **30–60 seconds**.  
- **Timing**: Fixed‑time step of **60 fps** (≈16.67 ms per frame).  
- **Sequence**:  
  1. **Input** – read player controls.  
  2. **Update** – move player, asteroids, and projectiles; handle collisions.  
  3. **Render** – draw all entities to the screen.  
  4. **Check End** – if time elapsed → end match.  

# Entidades  
- **Player**  
  - Sprite: 2‑D ship.  
  - Properties: position, velocity, rotation, health (1 hit = death).  
  - Capable of firing projectiles.  
- **Asteroid**  
  - Sprite: circular/irregular shape.  
  - Properties: position, velocity, size (small/medium/large).  
  - Spawns at random edges, moves across screen.  
- **Projectile**  
  - Sprite: small bullet.  
  - Properties: position, velocity, lifespan (auto‑destroy after 2 s or on collision).  

# Controles  
- **Keyboard**  
  - `← / →` – rotate left/right.  
  - `↑` – thrust forward (accelerate).  
  - `Space` – fire projectile.  
- **Optional**: mouse click to fire in mouse direction (not required for MVP).  

# Win/Lose Condition  
- **Win**: Survive the full 30–60 seconds.  
- **Lose**: Player’s ship collides with any asteroid (health reaches 0).  

# Restrições  
- **Platform**: Web browser (HTML5 Canvas) or desktop (SDL/MonoGame).  
- **Assets**: Use royalty‑free or procedurally generated graphics; no external art packs.  
- **Performance**: Target 60 fps on mid‑range hardware.  
- **Code**: Single‑file or minimal module structure; no external game engines beyond the chosen framework.  

# Não‑objetivos  
- No power‑ups, upgrades, or score tracking.  
- No split‑screen or multiplayer.  
- No complex physics (no gravity, no inertia beyond simple velocity).  
- No sound effects or music.  
- No UI beyond a simple timer display.