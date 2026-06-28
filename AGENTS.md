# SnakeV2 — Agent Guide

## Entrypoint
- `main.py` — `SnakeGame` class, `if __name__ == '__main__': SnakeGame().run()`

## Module layout
| File | Responsibility |
|---|---|
| `config.py` | All constants (`WIDTH`, `HEIGHT`, colors, physics). Imported via `from config import *` everywhere. |
| `main.py` | Game loop, rendering, tile/snake/apple drawing, event handling, state machine |
| `utils.py` | Perlin noise, hex math (`hex_to_pixel`, `hex_corners`, `all_hexes`), color helpers, `wrap_coords` |
| `camera.py` | `Camera` class with `project(x, y, z=0)` (isometric projection) and `follow_snake()`. Replaces standalone `project()` from utils. |
| `particle.py` | `Particle` + `ParticlePool` (object pool pattern). |
| `shaders.py` | GLSL shader source strings (vertex, fragment, bloom, god rays, water) |
| `gl_renderer.py` | Optional ModernGL renderer. Accesses `game.camera` directly. Falls back to software rendering if `moderngl` is unavailable or init fails. |
| `resources.py` | `ResourceManager` — fonts, sprites, sky/star/cloud surfaces, caches. Attached to `SnakeGame` via `__getattr__` delegation. |
| `ui.py` | Draw helpers for score panel, pause overlay, game-over screen, start screen, minimap |

## Architecture notes
- `SnakeGame` delegates attribute lookups to `ResourceManager` via `__getattr__` (line 64-68 of main.py)
- Rendering uses dirty-rect tracking; full redraw forced on game state changes and every 60 frames
- Snake movement uses lerp between prev/current positions for smooth animation
- Depth sorting: items (snake, apple) are bucketed by projected depth for correct draw order
- Grid is hexagonal axial coordinates `(q, r)`, radius 7, wrapped at edges via `wrap_coords()`

## Running
```sh
python main.py
```
No dependencies beyond `pygame`. Optional: `pip install moderngl` for GPU-accelerated rendering with bloom/god rays.

## Known quirks
- `snakeV2.py` has been deleted — monolith was broken into the modules above
- Tile cache is rebuilt every frame (~4.4ms for 212 visible tiles); no offset caching
- Perlin noise uses a per-run random seed (`NOISE_SEED`), cached permanently in `_perlin_cache` and `_tile_noise_cache` (module-level dicts in utils.py)
- Game loop runs at 60 FPS (`clock.tick(60)`), movement interval decays with score (`BASE_MOVE_INTERVAL = 0.07s`, decays by `SPEED_DECAY_PER_POINT`)
- No test infrastructure exists
