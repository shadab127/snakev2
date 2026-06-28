# Architecture Overview

## Game Loop

The game loop lives in `SnakeGame.run()` (line 1521). Execution flow:

1. **Start Screen** — `wait_for_key()` (line 1506) renders a static title/instructions screen and polls for any key or mouse press.
2. **Game Session Loop** — After key press, enters a nested loop:
   - Resets state via `reset()`.
   - Inner loop calls `handle_events()` → `update(dt)` → `render()` until `game_over` is true.
   - A second inner loop keeps rendering (with particles still updating) while `game_over` is true, waiting for R/ENTER/ESC.
3. **Timing** — `pygame.time.Clock().tick(60)` provides wall-clock delta-time. Game-logic ticks are decoupled: moves happen at a fixed 30 FPS interval (`1.0 / FPS = ~33 ms`). Accumulated `move_timer` drives discrete snake moves; `move_lerp` interpolates positions smoothly between moves.

## Rendering Pipeline

`render()` (line 1196) executes in order:

1. **Sky background** — pre-rendered vertical gradient (`_build_background`, line 606).
2. **Stars** — pre-rendered starfield alpha surface (`_build_stars`, line 621).
3. **Sun disc** — additive-blended radial gradient (`_build_sun_disc`, line 590), position oscillates with `SUN_ANGLE_SPEED`.
4. **Water** — dynamic polygon strips with multi-octave wave displacement, fresnel transparency, specular highlights, and sun reflection.
5. **Ground cache** — pre-rendered hex-bottoms (underside of tiles).
6. **Draw list construction + depth sort** — every hex tile, apple, and snake segment is assigned a `depth` value from `project()` and sorted back-to-front (painter's algorithm).
7. **Draw cache** — a cleared `SRCALPHA` surface onto which all geometry is composited in sorted order.
8. **Bloom** — downscale to 1/4 → smoothscale back up → additive blend at alpha 28.
9. **Apple glow** — radial gradient additive layer.
10. **God rays** — 12 animated sun-ray lines in additive mode.
11. **Fog** — pre-built vertical fog gradient strip.
12. **Particles** — sorted by Z, drawn with individual glow/spark/normal paths.
13. **UI** — score panel, pause overlay, or game-over overlay.
14. **Vignette** — pre-computed radial darkening.
15. **`pygame.display.flip()`** — full-screen buffer swap.

## Camera System

A fixed isometric/perspective hybrid:

- **Projection** — `project(x, y, z)` (line 211) applies a tilt rotation about X (`TILT = 52°`), then a perspective divide using `FOV / (z_cam)`. There is no camera movement, zoom, or rotation.
- **Parameters** — `CAM_DIST = 450`, `FOV = 420`, `Y_OFFSET = HEIGHT * 0.58`.
- **No view matrix** — everything is hard-coded in a single projection function.

## Snake Movement

- **Grid** — axial hex coordinates `(q, r)`. Six directions defined in `DIR_VECTORS` (line 26).
- **Control** — `turn_left()` / `turn_right()` rotate the desired direction; the actual direction updates only on the next tick in `move_snake()`.
- **Execution** — `move_snake()` (line 686) computes `new_head`, checks bounds and self-collision, inserts head, pops tail (unless apple eaten), returns success/failure.
- **Smoothing** — `prev_snake_positions` is snapshotted before each move; `move_lerp` (0→1) interpolates positions. Catmull-Rom splines (line 164) further smooth the body curve when length ≥ 4.

## Apple Spawning

`_find_empty()` (line 668) builds a list of all hexes not in the snake body and picks one uniformly at random. Returns `None` if the grid is full (terminal win state not handled — game would crash).

## Collision Detection

- **Wall collision** — `in_bounds()` (line 200) checks `max(abs(q), abs(r), abs(q+r)) <= GRID_RADIUS`.
- **Self collision** — `new_head in self.snake[1:]` after the head index.
- All collision logic is in `move_snake()`. Failure sets `game_over = True` and triggers screen shake + particle burst.

## UI Rendering

- **Score panel** — semi-transparent gradient rect at top-left with score text, glow, and a green dot.
- **Pause overlay** — semi-transparent dark fullscreen + centered panel with "PAUSED" and hint text.
- **Game-over overlay** — dark fullscreen + centered panel with score, "NEW BEST!" indicator, and restart hint.
- **Start screen** — fully drawn in `draw_start_screen()` (line 1456) with title, subtitle, controls table, and pulsing "Press any key".

## World Generation

- **Grid** — radius 7 (169 hexagonal tiles), generated once during `reset()`.
- **Terrain variation** — Perlin noise with 4 octaves produces `base`, `detail`, `moss`, `dirt`, `crack`, `grass`, `tex` values per tile (cached in `_tile_noise_cache`).
- **Tile structure** — each hex is drawn as 6 triangular fans for the top face + 6 quadrilateral side faces.
- **Lighting** — per-vertex normals (line 170–180) with directional light and ambient term. Distance-based fog and ambient occlusion modulate final color.
- **Decoration** — grass blades with wind sway, procedural cracks, moss/dirt color blending, rim highlights.
- **Water** — a strip of animated quads below the tiles with fresnel alpha and specular sun highlights.
- **Sky** — gradient background with stars, animated sun disc, god rays, and water reflection.

## Performance Bottlenecks

1. **`draw_tile()` called per hex per frame** — 169 tiles × ~12 polygon draw calls = ~2028 `pygame.draw.*` calls per frame.
2. **Perlin noise regeneration** — `tile_noise()` calls 7 noise lookups per tile; `perlin_noise()` itself runs 3 octaves with exponentiation.
3. **Bloom pass** — two full-screen `smoothscale` operations + additive blit each frame.
4. **Water surface** — per-frame polygon generation with sine-wave evaluation across many strips.
5. **Particle draws** — glow particles create a new `Surface` each frame; `BLEND_ADD` blits are expensive.
6. **Snake segment draws** — `smoothscale` per body segment per frame (not cached by size).
7. **Head glow surface** — created from scratch each frame.
8. **Full-screen clearing** — `self.draw_cache.fill((0, 0, 0, 0))` on a 1280×800 surface.
9. **Crack rendering** — calls `random.uniform` inside the draw loop.
10. **List modification during iteration** — `self.particles.remove(p)` while iterating the list.

# Current Problems

### Architectural Issues

1. **Monolithic class** — `SnakeGame` is ~950 lines, mixing game logic, rendering, particles, UI, asset generation, and input handling.
2. **No game state machine** — states (start, playing, paused, game over) are tracked via booleans (`paused`, `game_over`) and conditional branches throughout the code.
3. **Global caches** — `_perlin_cache`, `_tile_noise_cache`, `_noise_cache_frame` are module-level globals, creating implicit coupling and making testing impossible.
4. **Frame-dependent logic** — `time_float = self.frame_count / 60.0` is used for animation, but `frame_count` increments at render rate, not wall-clock time.
5. **No separation of concerns** — rendering, particle updates, and game logic all run in the same `update()` method.
6. **No resource management** — sprites are generated in `__init__` and stored as instance attributes ad-hoc; no loading/unloading life cycle.
7. **No delta-time decoupling** — the 30 FPS game-logic tick is fixed; screen refresh rate changes (e.g., 144 Hz) would not affect simulation speed, but the animation time `time_float` would diverge from real time.
8. **Game-over loop duplicates code** — the game-over render loop is a near-duplicate of the main loop.
9. **`_find_empty()` allocates a list every call** — on a large grid this creates garbage.

### Visual Artifacts

1. **Seam artifacts on hex tops** — per-vertex normals at the center of each triangular fan create a visible "star" pattern where adjacent triangles disagree on lighting at the shared edge.
2. **Z-fighting / draw order glitches** — painter's algorithm sorts by a single depth value per object; adjacent hexes with near-identical depth can flicker.
3. **No anti-aliasing** — all polygon edges are aliased.
4. **Bloom is low-quality** — single-pass smoothscale produces blocky artifacts.
5. **Screen-space eye/tongue rendering** — eyes and tongue are drawn in screen space without accounting for camera tilt, so they don't look correct from the isometric perspective.
6. **Grass blades have 1-pixel width** — flicker and alias badly, especially during wind sway.
7. **Particle glow creates visible per-frame surfaces** — especially for the head glow and apple glow.
8. **Apple leaf rotation uses `math.sin` in screen space** — the leaf does not properly track the isometric projection.
9. **No shadow on terrain** — the soft shadow sprite is a flat circle drawn on top of the ground but does not deform with terrain height or projection.

### Performance Issues

1. **2028+ draw calls per frame** — software rasterizer in pygame cannot sustain this at high resolutions.
2. **Sprite scaling every frame** — `pygame.transform.smoothscale` is called for each snake segment and apple instance (11+ times per frame).
3. **Particle glow surfaces created per frame** — the non-cached glow path (line 373) creates a new Surface every draw.
4. **Water polygon generation** — loops over 50 strips, creating 50 polygon draw calls per frame.
5. **Bloated draw list** — every tile, every snake segment, and apple are added to a Python list and sorted by depth every frame.
6. **No dirty rects** — entire 1280×800 surface is redrawn and flipped every frame.
7. **Hash-based pseudo-randomness** — `hash((q, r, bi))` in grass / crack drawing is called dozens of times per frame.
8. **Eat-flash and game-over color modulation in draw path** — color computation with `lerp_color`, `mul_color`, and the `if self.game_over` / `if self.eat_flash > 0` branches run inside the hot tile loop.
9. **`pygame.Surface` creation in hot paths** — head glow (line 1062), apple glow (line 1309), god rays cache (line 1316), leaf surface (line 1149) are allocated per frame.

# Prioritized Roadmap

## 1. State Machine Refactor

- **Objective:** Replace boolean flags (`paused`, `game_over`) with an explicit state machine (START, PLAYING, PAUSED, GAME_OVER, QUIT).
- **Reason:** Boolean flags scattered across 20+ methods make control flow unpredictable and hard to extend.
- **Dependencies:** None
- **Estimated difficulty:** Medium
- **Estimated functions changed:** 8–10 (`__init__`, `run`, `handle_events`, `update`, `render`, `reset`, `wait_for_key`, `quit`)

## 2. Separate Rendering from Game Logic (System Split)

- **Objective:** Extract Renderer, ParticleSystem, UIManager, and GameWorld classes from the monolithic `SnakeGame`.
- **Reason:** 950-line class is untestable; rendering and logic interleaved prevents profiling and independent optimization.
- **Dependencies:** #1 (state machine clarifies ownership)
- **Estimated difficulty:** Hard
- **Estimated functions changed:** 30+ (nearly every method moves or is split)

## 3. Cache Tile Static Layer

- **Objective:** Pre-render static hex tiles (those not under the snake or apple) into a persistent surface. Only redraw tiles that change (snake moves, apple spawns).
- **Reason:** ~169 tiles × 12 draw calls = 2028 calls per frame is the #1 bottleneck.
- **Dependencies:** None (can be done independently, but benefits from #2)
- **Estimated difficulty:** Medium
- **Estimated functions changed:** 4–6 (`render`, `draw_tile`, `move_snake`, `reset`, new methods for cache invalidation)

## 4. Per-Tile Sprite Cache with Size Variants

- **Objective:** Pre-scale all snake body sprites, head sprites, and apple sprite to all needed sizes at load time instead of calling `smoothscale` per frame.
- **Reason:** `smoothscale` is called 11 times per frame, each allocating a new surface.
- **Dependencies:** None
- **Estimated difficulty:** Easy
- **Estimated functions changed:** 3–4 (`__init__`, `draw_snake_segment`, `draw_apple`, new caching method)

## 5. Eliminate Per-Frame Surface Allocations in Hot Paths

- **Objective:** Pre-allocate or reuse surfaces for head glow, apple glow, leaf drawing, and god rays. Use pre-rendered glow sprites at multiple sizes.
- **Reason:** Creating `pygame.Surface` in a loop (head glow, apple glow, leaf, god rays cache) generates allocation pressure and GC churn.
- **Dependencies:** None
- **Estimated difficulty:** Easy
- **Estimated functions changed:** 5 (`draw_snake_segment`, `draw_apple`, `render`, `draw_start_screen`, `__init__`)

## 6. Optimize Perlin Noise

- **Objective:** Replace the current Perlin implementation with a faster algorithm (Simplex / OpenSimplex) or switch to pre-computed noise textures sampled with bilinear interpolation. Reduce octave count or use a single noise texture lookup.
- **Reason:** `tile_noise` calls `perlin_noise` 7 times per hex × 169 hexes = 1183 noise evaluations per frame, each with 2–3 octaves.
- **Dependencies:** None
- **Estimated difficulty:** Medium
- **Estimated functions changed:** 3–4 (`perlin_noise`, `tile_noise`, `__init__` for noise table generation, `draw_tile` usage)

## 7. Implement Dirty-Rect Rendering

- **Objective:** Track changed regions (snake moved, apple spawned, particles updated) and only blit those regions to the screen. Use `pygame.display.update(rects)` instead of `flip()`.
- **Reason:** Full 1280×800 redraw 60 times per second wastes GPU bandwidth when 95% of the scene is static.
- **Dependencies:** #3 (tile cache) makes dirty-rect trivial; #5 reduces per-frame allocations.
- **Estimated difficulty:** Hard
- **Estimated functions changed:** 6–8 (`render`, `update`, `move_snake`, `draw_snake_segment`, `draw_apple`, new dirty-rect tracker)

## 8. Fix Per-Vertex Normal Lighting on Hex Tops

- **Objective:** Use flat shading per triangle instead of per-vertex normals, or compute a single face normal for each hex top.
- **Reason:** The current `hex_corner_normal` creates a visible "star" lighting artifact along triangle edges.
- **Dependencies:** None
- **Estimated difficulty:** Easy
- **Estimated functions changed:** 2 (`draw_tile`, remove `hex_corner_normal`)

## 9. Switch to OpenGL / Hardware Acceleration

- **Objective:** Replace pygame software rendering with ModernGL or pyglet for GPU-accelerated rendering. Batch all hex geometry into a single VBO.
- **Reason:** Even with all optimizations, pygame software rendering cannot deliver 60 FPS with the visual complexity of this project.
- **Dependencies:** #2, #3 (clean separation makes the rendering backend swappable)
- **Estimated difficulty:** Very Hard
- **Estimated functions changed:** 20+ (entire render pipeline replaced)

## 10. Particle System Overhaul

- **Objective:** Object pool for particles, pre-multiplied alpha blending for glows, avoid `list.remove()` during iteration, pre-compute glow sprites at all needed sizes.
- **Reason:** Current system creates/destroys particles constantly, allocates per-frame glow surfaces, and modifies the list during iteration (which is O(n) per removal).
- **Dependencies:** #2, #5
- **Estimated difficulty:** Medium
- **Estimated functions changed:** 4–6 (`Particle.draw`, `update`, `update_ambient_particles`, `_spawn_eat_particles`, new `ParticlePool` class)

## 11. Depth-Sorting Optimization (Bucketed Sort)

- **Objective:** Replace per-frame Python sort of the draw list (~200 entries) with bucket sort by integer depth quantization.
- **Reason:** Python's Timsort on 200 items is fast, but avoiding the sort entirely by bucketing saves memory and time.
- **Dependencies:** #3 (static tiles already rendered to cache, only dynamic objects need sorting)
- **Estimated difficulty:** Easy
- **Estimated functions changed:** 2 (`render`, new depth-bucket generator)

## 12. Resource Management System

- **Objective:** Centralize sprite, font, surface, and noise-table creation into a `ResourceManager`. Support lazy loading, caching, and cleanup.
- **Reason:** Assets are currently generated in `__init__` with no explicit lifecycle.
- **Dependencies:** #2
- **Estimated difficulty:** Medium
- **Estimated functions changed:** 8–10 (`__init__`, all `generate_*_sprite`, `_build_*` methods, new `ResourceManager` class)

# Risks

### 1. State Machine Refactor
- **Regression:** Missed state transitions could lock the game in an unresponsive state.
- **Regression:** Breaking the escape-to-quit path could prevent clean shutdown.
- **Mitigation:** Keep the old boolean guards in parallel during refactor; remove them only after full test coverage.

### 2. Separate Rendering from Game Logic
- **Regression:** Incorrect ownership of shared state (e.g., `frame_count`, `particles`) causes crashes or visual desync.
- **Regression:** Particle rendering is tightly coupled to `SnakeGame` attributes (e.g., `game.particle_glows`); extracting it may break glow-drawing code paths.
- **Mitigation:** Pass dependencies explicitly via constructor injection; write regression tests comparing old vs. new frame output.

### 3. Cache Tile Static Layer
- **Regression:** Stale cache when snake/effects change a tile that was assumed static.
- **Regression:** Cache invalidation misses when the game-over overlay or eat-flash modifies all tiles.
- **Mitigation:** Always invalidate the entire cache on game-over, eat-flash, or any global effect change.

### 4. Per-Tile Sprite Cache with Size Variants
- **Regression:** Quality loss from pre-scaled sprites if the required size falls between cached variants.
- **Regression:** Increased memory usage (~10 variants × 11 segments × 48² = heavy).
- **Mitigation:** Use nearest-cached-size with bilinear interpolation; set a memory budget.

### 5. Eliminate Per-Frame Surface Allocations
- **Regression:** Reused surface not properly cleared between frames, leaving ghost artifacts.
- **Mitigation:** Always `.fill((0,0,0,0))` before reuse.

### 6. Optimize Perlin Noise
- **Regression:** Different noise output changes terrain appearance, moss placement, crack patterns — visually breaking the game's aesthetic.
- **Regression:** Seeded randomness changes; player expectations of grid layout shift.
- **Mitigation:** Use the exact same seed with the new algorithm; compare per-tile noise values for exact match or acceptably close approximation.

### 7. Implement Dirty-Rect Rendering
- **Regression:** Overlapping dirty rects cause partial updates visible as tearing.
- **Regression:** Particles or effects outside tracked dirty rects are invisible.
- **Mitigation:** Add a safety full-redraw every N frames; track all particle bounding boxes.

### 8. Fix Per-Vertex Normal Lighting on Hex Tops
- **Regression:** Changing from per-vertex to flat shading will change the look of every tile, potentially making it look worse.
- **Mitigation:** Side-by-side visual comparison before committing.

### 9. Switch to OpenGL
- **Regression:** Entire visual output changes; all `pygame.draw` calls must be replaced with GL calls.
- **Regression:** Font rendering, particle system, and UI overlays are non-trivial in GL.
- **Regression:** Compatibility breaks on systems without OpenGL 3.3+.
- **Mitigation:** Keep software renderer as a fallback via a `Renderer` interface.

### 10. Particle System Overhaul
- **Regression:** Pool exhaustion causes no particles to spawn (silent failure).
- **Regression:** Pre-computed glow sprites may not match the per-frame generated look.
- **Mitigation:** Set pool size generously; log warnings on exhaustion.

### 11. Depth-Sorting Optimization
- **Regression:** Quantization causes incorrect ordering for items at the same depth bucket.
- **Mitigation:** Use fine-enough quantization (256+ buckets).

### 12. Resource Management System
- **Regression:** Lazy loading adds latency on first frame.
- **Regression:** Memory leak if resources are not released.
- **Mitigation:** Preload on start screen; use weak references for cache entries.

# Recommendations

The following implementation order minimizes risk while delivering the highest performance gain earliest:

**Phase 1 (Low risk, high impact, no visual changes):**
1. #5 — Eliminate per-frame surface allocations
2. #4 — Per-tile sprite cache with size variants
3. #8 — Fix per-vertex normal lighting on hex tops

**Phase 2 (Structural):**
4. #1 — State machine refactor (enables clean separation)
5. #2 — Separate rendering from game logic (enables independent optimization)

**Phase 3 (Performance):**
6. #3 — Cache tile static layer (reduces draw calls by ~90%)
7. #6 — Optimize Perlin noise
8. #10 — Particle system overhaul
9. #11 — Depth-sorting optimization (bucket sort)

**Phase 4 (Advanced):**
10. #7 — Dirty-rect rendering
11. #12 — Resource management system

**Phase 5 (Hardware):**
12. #9 — Switch to OpenGL / hardware acceleration

Items #3, #4, #5, and #8 can be parallelized across developers since they touch independent code paths.
