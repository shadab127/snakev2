# Implementation Plan

Based on `roadmap.md` — detailed step-by-step instructions for each phase.

---

## Phase 1 — Modular Refactor

### Goal
Split monolithic `snakeV2.py` (~2440 lines) into focused modules.

### Module Map

| Module | Contents | Orig. lines | Depends on |
|--------|----------|-------------|------------|
| `config.py` | All ~60 constants (grid, colors, lighting, display) | 272–359 | `math` |
| `shaders.py` | 11 GLSL shader source strings | 22–270 | — |
| `game_state.py` | `GameState` enum (START/PLAYING/PAUSED/GAME_OVER/QUIT) | 703–708 | `enum` |
| `utils.py` | 17 module-level functions + global caches (`_PERM`, `_perlin_cache`, `_tile_noise_cache`) | 361–543 | `math`, `random`, `pygame`, `config` |
| `particle.py` | `Particle` + `ParticlePool` classes | 546–700 | `random`, `math`, `pygame`, `config`, `utils` |
| `resources.py` | `ResourceManager` class (fonts, sprites, atmospherics, caches) | 950–1243 | `pygame`, `config`, `utils` |
| `gl_renderer.py` | `GLRenderer` class (ModernGL pipeline, FBOs, shaders) | 711–947 | `struct`, `moderngl`, `shaders`, `config` |
| `ui.py` | Standalone UI functions: `draw_ui`, `draw_pause_overlay`, `draw_game_over`, `draw_start_screen` | 2247–2414 | `pygame`, `config`, `utils`, `game_state` |
| `main.py` | Remaining `SnakeGame` class (game loop, rendering, orchestration) | 1245–2442 | All above |

### Extraction Order

1. `config.py` — pure constants, no behavioral change
2. `shaders.py` — copy GLSL strings verbatim
3. `game_state.py` — copy enum
4. `utils.py` — copy 17 functions + global caches. Add `from config import *`
5. `particle.py` — copy Particle + ParticlePool classes
6. `resources.py` — copy ResourceManager class
7. `gl_renderer.py` — copy GLRenderer class
8. `ui.py` — extract UI functions. Convert `self.xxx` → `game.xxx` parameters
9. `main.py` — keep SnakeGame with imports from all above. Remove extracted code.
10. `README.md` — document each module

### Dependency Graph

```
config.py  ─┬─> utils.py  ─┬─> particle.py
            │              ├─> resources.py
            │              └─> ui.py
            │
shaders.py ─┴─> gl_renderer.py
game_state.py ─> ui.py

main.py imports: config, utils, particle, resources, gl_renderer, ui, game_state
```

### Key Decisions

- `__getattr__` delegation kept in SnakeGame → `self.resources` so `self._head_sprites`, `self.font_large`, etc. continue working in drawing methods.
- `draw_tile`, `draw_snake_segment`, `draw_apple`, `draw_shadow` stay on SnakeGame (too coupled to game state). They can be extracted in a future rendering refactor.
- `ui.py` functions take a `game` parameter instead of `self`.

---

## Phase 2 — Progressive Speed

### Changes

**`config.py`** — add:
```python
BASE_MOVE_INTERVAL = 0.07
MIN_MOVE_INTERVAL = 0.025
SPEED_DECAY_PER_POINT = 0.0005
```

**`main.py`** — in `update()`, replace:
```python
interval = 1.0 / FPS
```
with:
```python
interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - self.score * SPEED_DECAY_PER_POINT)
```

---

## Phase 3 — Mini-Map

### Changes

**`config.py`** — add:
```python
MINIMAP_SIZE = 140
MINIMAP_PADDING = 10
MINIMAP_ALPHA = 180
```

**`ui.py`** — new `draw_minimap(surf, snake, apple, game)` function:
- Create small `Surface` (140x140) with semi-transparent background
- Draw simplified top-down hex grid dots
- Green dots for snake segments
- Red dot for apple
- Blit to top-right corner

**`main.py`** — in `render()`, call `draw_minimap()` before vignette

---

## Phase 4 — Camera System + Toroidal World

### 4a — Toroidal World

**`config.py`** — add:
```python
GRID_COLS = GRID_RADIUS * 2 + 1  # 15
GRID_ROWS = GRID_RADIUS * 2 + 1  # 15
```

**`snake.py`** — new `wrap_coords(q, r)` function:
- Convert axial → offset coords
- Apply modulo
- Convert back to axial

**`main.py`** — in `move_snake()`:
- Replace `in_bounds()` death check with `wrap_coords()` wrapping

### 4b — 3D Follow Camera

**`camera.py`** — new module:
- `Matrix4` class with `identity()`, `perspective()`, `look_at()`, `multiply()`
- `Camera` class with `follow_snake()`, `project()`, `view_matrix`, `proj_matrix`

**`utils.py`** — replace old `project()` with wrapper around `Camera.project()`

**`main.py`** — all drawing methods: `project(x, y, z)` → `self.camera.project(x, y, z)`

### Migration Strategy

1. Add `camera.py` alongside existing code (don't remove `project()` yet)
2. Add `Camera.project()` mirroring old `project()` behavior
3. One call-site at a time: swap `project()` → `camera.project()`
4. Test after each swap
5. Remove old `project()` when all call-sites migrated

---

## Verification

| Phase | How to verify |
|-------|--------------|
| 1 | `python main.py` launches with identical visuals, no import errors |
| 2 | Snake starts slow, speeds up after eating |
| 3 | Top-right minimap shows grid/snake/apple |
| 4a | Snake wraps around edges instead of dying |
| 4b | Camera follows snake head smoothly, world stays upright |
