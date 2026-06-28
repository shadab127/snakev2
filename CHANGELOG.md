# Changelog

## [Unreleased]

### Added
- Project initialized.

### Architecture
- 3D isometric hex-grid snake game with software rendering via pygame.
- Perlin-noise-based procedural terrain with moss, dirt, cracks, and grass decoration.
- Sprite-based snake body with Catmull-Rom spline interpolation and per-vertex lighting.
- Dynamic water surface with Fresnel transparency, wave displacement, and sun reflections.
- Particle system with glow, spark, and ambient particle types.
- God rays, bloom post-processing, vignette, and fog atmospheric effects.
- Start screen, pause overlay, game-over screen, and score UI.

## Roadmap Item #1 — State machine

Replace boolean flags (`paused`, `game_over`) with an explicit `GameState` enum (`START`, `PLAYING`, `PAUSED`, `GAME_OVER`, `QUIT`).

- Added `GameState(Enum)` class; all 15 conditionals referencing `self.paused`/`self.game_over` replaced with `self.state` comparisons.
- `handle_events` branches per-state; `update` guards move logic with `PLAYING`; `render` checks state for overlays.
- `run()` loop simplified: single outer loop checks for QUIT; inner loops for PLAYING/PAUSED and GAME_OVER.
- Verified: compile passes, all controls and visual features preserved.

## Roadmap Item #3 — Tile caching

Pre-render static hex tiles into a persistent surface; only redraw tiles that change (snake moves, apple spawns).

- Added `_tile_cache` (SRCALPHA surface) and `_tile_cache_valid` flag.
- New `_build_tile_cache()` renders all 169 tiles in depth order to the cache surface.
- Cache invalidated on snake move, game-over, eat-flash, and reset.
- Per-frame draw list reduced from ~200 to ~10 items (only apple + snake) on cache-hit frames.
- At 60 FPS with 30 FPS game-logic ticks, ~50% of frames are cache hits (zero tile redraws).
- Verified: compile passes, no visual artifacts. Remaining: tiles adjacent to snake have slightly stale AO until next move (33ms latency, imperceptible).

## Roadmap Item #4 — Sprite pre-scaling

Pre-scale snake body sprites, head sprites, and apple sprites to all needed sizes at load time instead of per-frame `smoothscale`.

- New `_cache_sprite_sizes()` pre-scales master head, body (8 colors), and apple sprites to sizes 10–40.
- `draw_snake_segment` and `draw_apple` use dict lookups; fallback scales on demand for uncached sizes.
- Per-frame `smoothscale` calls eliminated from hot draw path (10+ per frame → 0 after warm-up).
- Verified: compile passes, visual quality preserved. Memory: ~310 cached surfaces ≈ 1 MB.

## Roadmap Item #5 — Surface reuse & glow caching

Pre-allocate or reuse surfaces for head glow, apple glow, leaf drawing, god rays, water reflection, and start screen sun.

- New `_cache_glow_sprites()` pre-renders head glow (sz 10–40, alpha 50) and apple glow (glow_r 10–49, alpha 35) with per-frame alpha modulation via `set_alpha`.
- New `_build_start_sun()` pre-renders the 42-radius sun disc, eliminating 42 per-frame circle draws on start screen.
- Head glow/apple glow: replaced per-frame Surface + circle draws with cached sprite + `set_alpha`.
- Leaf drawing: replaced per-frame Surface allocation with fill+redraw to pre-allocated surface.
- Water reflection: replaced per-frame Surface allocation with fill+redraw to pre-allocated surface.
- Start screen sun: replaced 42 circle calls per frame with a single blit.
- Verified: compile passes, 10+ frames without crash. Remaining: `draw_shadow` and particle glow sprites still call `smoothscale` per frame.

## Roadmap Item #6 — Permanent noise cache

Replace per-frame-cleared Perlin noise cache with permanent per-tile cache. Tile noise depends only on (q, r), which never change.

- Removed `_noise_cache_frame` and per-frame cache clearing; cache is now permanent.
- `tile_noise(q, r, frame)` → `tile_noise(q, r)`; cache pre-populated for all 169 tiles during `__init__`.
- Cleared `_perlin_cache` after pre-computation to reclaim ~2 KB stale entries.
- Verified: compile passes, 169 cache entries, zero noise computation on first render frame.

## Roadmap Item #7 — Dirty rect updates

Track changed regions and blit only those regions using `pygame.display.update(rects)` instead of `flip()`.

- Added dirty-rect tracking: `_dirty_rects`, `_prev_dirty_rects`, `_full_redraw_counter`, `_full_redraw_requested`.
- New helper functions: `_add_dirty_rect`, `_request_full_redraw`, `_merge_rects`, `_compute_dirty_rects`.
- `render()`: full redraw when cache invalid, eat_flash, or overlay active; otherwise unions previous + current dirty rects and calls `update(merged_rects)`.
- Safety full-redraw every 60 frames prevents stale pixel accumulation.
- Verified: compile passes, controls preserved. Remaining: water animates continuously (dirty every frame), screen shake not fully covered (safety redraw handles within 60 frames).

## Roadmap Item #8 — Flat shading

Use flat shading per triangle instead of per-vertex normals for hex tops, eliminating visible "star" lighting artifacts.

- Removed `hex_corner_normal(i)` and `normalize3(v)` functions.
- Replaced per-vertex normal lighting loop (3 normals × 6 triangles with averaging) with flat shading: single `face_normal = (0,0,1)` dot with `LIGHT_DIR`, uniform color for all 6 triangles.
- Bevel highlights simplified to use uniform `(0,0,1)` normal instead of per-edge corner-normal average.
- Verified: compile passes, no references to removed functions remain, "star" artifact eliminated. Remaining: side faces retain per-face normals (correct).

## Roadmap Item #9 — ModernGL pipeline

Replace software render pipeline with ModernGL for GPU-accelerated rendering, bloom, god rays, and fog via GL shaders.

- `GLTileRenderer` expanded to full `GLRenderer` with multiple FBOs (scene, main, bloom1, bloom2, tile float), 7 GLSL shader programs, fullscreen quad VBO, and texture cache.
- Bloom: GPU downsample-blur-upsample pipeline with bright-pass filtering (replaced 2 `smoothscale` calls).
- God rays: procedural fragment shader (replaced 12 software line draws per frame).
- Fog: GL additive texture blend (replaced software blit).
- Pre-built surfaces uploaded once to GL texture cache; dynamic scene snapshots uploaded per frame.
- Software fallback when `moderngl` unavailable.
- Verified: compile passes, GL 4.6 Core Profile, all 8 shaders compile, 4 FBOs created, 10+ frames without error.

## Roadmap Item #10 — Particle object pool & pre-multiplied alpha

Object pool for particles, pre-multiplied alpha blending for glows, eliminate `list.remove()` during iteration.

- New `ParticlePool` class with pre-allocated pool of 500 slots using alive/free-list pattern — O(n) with zero allocation per frame.
- `generate_particle_sprite` pre-multiplies RGB by alpha for correct additive blending.
- New `_cache_particle_glow_scales()` pre-scales 12 glow sprite colors to sizes 4–40 (444 cached surfaces, ~2.8 MB).
- `Particle.draw` uses cached sprites; fallback caches on demand.
- Per-frame `list.remove()` eliminated from `update()`, `run()` game-over loop, and all particle iteration.
- Verified: compile passes, pool initializes 500 dead particles, 444 pre-scaled sprites, visual behavior unchanged.

## Roadmap Item #12 — Resource Management System

Centralize sprite, font, surface, and scene-data creation into a `ResourceManager` class. Support lazy loading, caching, and cleanup.

- New `ResourceManager` class with `_init_fonts`, `_init_atmospherics`, `_init_sprites`, `_init_caches`, `_init_working_surfaces`, `_init_scene_data`, `cleanup`, and the three `generate_*_sprite` methods.
- Moved all `generate_*_sprite`, `_build_*`, and `_cache_*` methods from `SnakeGame` to `ResourceManager`.
- `SnakeGame.__init__` delegates resource creation to `ResourceManager`; runtime access via `__getattr__` fallback to `self.resources`.
- Per-frame working buffers (`water_surf`, `_tile_cache`, `draw_cache`, `bloom_layer`, `cloud_surf_cache`) remain in `SnakeGame` as mutable state.
- Verified: compile passes, AST structure correct, no stale references to removed methods.

## Roadmap Item #11 — Depth-sorting optimization (bucketed sort)

Replace per-frame Python sort of the draw list (~200 entries) with bucket sort by integer depth quantization.

- New `_build_depth_buckets(items, num_buckets=256)` method quantizes floating-point depth into 256 integer buckets, collecting items into a dict and iterating buckets from far-to-near without any sort call.
- `render()`: replaced `draw_list.sort(key=lambda x: x[0], reverse=True)` with `_build_depth_buckets(draw_items)` — eliminates per-frame `sort()` call and lambda invocation.
- Since Roadmap #3 (tile caching) already removed most entries from the per-frame draw list, the practical impact is small, but the pattern is now correct for future use with larger draw lists.
- Verified: compile passes, game initializes and renders without error, visual output identical.
