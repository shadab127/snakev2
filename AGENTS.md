# SnakeV2 — Agent Guide

## Entrypoint
- `main.py` — `SnakeGame` class
- `__version__.py` — single-source version (`VERSION = (0,1,0)`, `__version__ = '0.1.0'`)
- `snakev2/__main__.py` — allows `python -m snakev2`
- Console entry: `snakev2` (via pyproject.toml `[project.scripts]`)

## Module layout
| File | Responsibility |
|---|---|
| `config.py` | All constants (`WIDTH`, `HEIGHT`, colors, physics). Imported via `from config import *` everywhere. |
| `main.py` | Game loop, rendering, tile/snake/apple drawing, event handling, state machine, CLI arg parsing |
| `utils.py` | Perlin noise, hex math (`hex_to_pixel`, `hex_corners`, `all_hexes`), color helpers, `wrap_coords` |
| `camera.py` | `Camera` class with `project(x, y, z=0)` (isometric projection) and `follow_snake()`. |
| `particle.py` | `Particle` + `ParticlePool` (object pool pattern). |
| `shaders.py` | GLSL shader source strings (vertex, fragment, bloom, god rays, water) |
| `gl_renderer.py` | Optional ModernGL renderer. Falls back to software rendering if `moderngl` unavailable or init fails. |
| `resources.py` | `ResourceManager` — fonts, sprites, sky/star/cloud surfaces, caches, `generate_app_icon()`. Attached to `SnakeGame` via `__getattr__` delegation. |
| `ui.py` | Draw helpers for score panel, pause overlay, game-over screen, start screen, minimap |
| `audio.py` | `AudioManager` — procedurally generated music, SFX, ambience with day/night crossfade |
| `persistence.py` | `PersistenceManager` — save/load high scores, settings, lifetime stats |
| `game_state.py` | `GameState` enum (START, PLAYING, PAUSED, GAME_OVER, QUIT, SETTINGS) |
| `__version__.py` | Single source of truth for version number |
| `__main__.py` | Root-level entry for `python __main__.py` |
| `snakev2/__init__.py` | Package marker |
| `snakev2/__main__.py` | Entry for `python -m snakev2` |
| `build.py` | PyInstaller build script |
| `pyproject.toml` | Python packaging config |

## Architecture notes
- `SnakeGame` delegates attribute lookups to `ResourceManager` via `__getattr__`
- Rendering uses dirty-rect tracking; full redraw forced on game state changes and every 60 frames
- Snake movement uses Catmull-Rom spline interpolation between hex positions for smooth animation
- Depth sorting: items (snake, apple) are bucketed by projected depth for correct draw order
- Grid is hexagonal axial coordinates `(q, r)`, radius 7, wrapped at edges via `wrap_coords()`
- Game loop: fixed-timestep accumulator (simulation at 180 Hz), render capped at 60 FPS

## Running
```sh
# From source
python main.py

# With optional GL acceleration
pip install moderngl && python main.py

# Installed via pip
pip install .
snakev2

# Via module
python -m snakev2
```

## CLI flags
| Flag | Effect |
|---|---|
| `--windowed` | Launch in window (default) |
| `--fullscreen` | Launch in fullscreen |
| `--no-gl` | Disable GPU acceleration |
| `--version` | Print version and exit |

## Known quirks
- `snakeV2.py` has been deleted — monolith was broken into the modules above
- Tile cache is rebuilt every frame (~4.4ms for 212 visible tiles); no offset caching
- Perlin noise uses a per-run random seed (`NOISE_SEED`), cached permanently in `_perlin_cache` and `_tile_noise_cache` (module-level dicts in utils.py)
- Game loop uses fixed-timestep accumulator: simulation at 180 Hz (`FIXED_DT = 1/180`), render capped at `RENDER_FPS` (60). Movement interval decays with score (`BASE_MOVE_INTERVAL = 0.15s`, decays by `SPEED_DECAY_PER_POINT`)
- Startup hardening: pygame init/display errors show friendly messages, no traceback

## Tests

```sh
# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_utils.py -v

# Run a specific test class or function
python -m pytest tests/test_headless.py::TestHeadlessSimulation::test_1000_step_soak -v

# Headless soak test (longer run)
python -m pytest tests/test_headless.py -v --timeout=60
```

### Test layout

| File | What it tests |
|---|---|
| `tests/test_utils.py` | Hex math, Catmull-Rom spline, color helpers, lighting |
| `tests/test_camera.py` | Camera projection, follow snake, shake, events, matrix math |
| `tests/test_particle.py` | Particle physics, lifetime, pool emit/clean/recycle, burst helpers |
| `tests/test_persistence.py` | Save/load round-trip, corruption handling, schema version |
| `tests/test_headless.py` | Full game simulation with `SDL_VIDEODRIVER=dummy` — 1000+ step soak |

### Running tests without pytest

```sh
python -m unittest discover tests/ -v
```

### Notes
- Tests use `SDL_VIDEODRIVER=dummy` (set in `conftest.py`) for headless operation.

## Guardrails
1. NEVER delete or rewrite `tests/`, `dev/`, `AGENTS.md`, or `implementation_plan/`. No "cleanup" or "simplification" commits. If a file seems dead, note it in the changelog — do not delete it.
