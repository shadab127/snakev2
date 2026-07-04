# Changelog

## v0.1.0 — 2026-07-04

### Recovery Track Complete

Phase 21 (Playability Sign-Off) closes the 11-phase recovery track that began with Phase 01.

**Headless verification results:**
- 129/129 tests pass (fixed one flaky soak test — periodic force-feeding)
- Entry points: `python main.py --version`, `python -m snakev2 --version`, `from __version__ import __version__` all produce `0.1.0`
- Harness captured start_screen, gameplay, and game_over screenshots
- FPS: 38.4 post-on / 84.5 post-off (software render, 1280×800)
- Per-stage: tiles ~0.5ms, snake ~0.8ms, particles ~0.06ms, post 1.3–5.8ms, UI ~2.4ms
- No inverted projection (probe points confirmed correct)
- All game state transitions verified programmatically

**Phase 19 follow-up fixes:**
- Removed per-pixel Python loop fallback in bloom/tone map (non-numpy path now skips with warning)
- Updated `frame_budget.md` with real Phase 19 measured numbers
- Added paused state screenshot capture to verification harness

**Phase 20 follow-up fixes:**
- GL god rays shader: 12→6 rays, softened (pow 8→4), day-cycle gated (`u_day_cycle < 0.2` skips)
- GL renderer: passes `u_day_cycle` uniform; gates god rays render on `day_cycle > 0.2`
- Vignette moved before UI rendering (no longer draws over HUD/menus)
- Removed redundant full-screen fog_surf additive blit from SW path (per-tile depth fog already handles this)

**Items needing real-display verification (unchecked in qa_checklist.md):**
- Visual readability, camera feel, audio, input latency, menu contrast, full playthrough flow

### Added
- Project initialized.
- **Phase 17: World Orientation Fix (Recovery)**
  - `camera.py` — `Matrix4.look_at()` fixed: corrected forward vector direction (`target-eye` instead of `eye-target`), right vector cross product order (`f×up`), and column-major layout (vectors spread across columns, third column uses `-f`, translation sign fixed)
  - Result: `grid_center_above` now projects above `grid_center` on screen (y=418 vs y=447) — world-up = screen-up
  - All tiles, snake, apple, water, particles, shadows automatically corrected via the same fix
- **Phase 18: Scene Correctness Pass (Recovery)**
  - `main.py`: tile top faces now filled with lighting/color (were transparent, showing ground underneath)
  - `main.py`: spline positions reversed so `_spline_positions[0]` matches `snake[0]` (head)
  - `main.py`: connector circles between snake segments now draw at same z=2 as body segments (were at z=7.3, floating above)
  - `dev/verify_screenshots.py`: added `capture_paused()` function for paused state screenshot
- **Phase 19: Software-Path Performance Recovery (Recovery)**
  - `main.py`: bloom and tone map combined into a single small-surface pass using `surfarray.pixels3d()` — eliminated per-pixel `get_at`/`set_at` loops (71× speedup, 349ms→4.9ms)
  - `main.py`: film grain uses precomputed noise surface scrolled 3px/frame — no per-frame Surface creation
  - `main.py`: tile cache invalidation gated by camera movement threshold (3.5 units) — tiles/frame from 17ms→0.5ms
  - `main.py`: water reduced from 50→24 rows, third wave harmonic removed, reflection optimized
  - `resources.py`: sky uses `fill(rect)` instead of `draw.line()` — 5× faster
  - Result: post-on 37 FPS (from 2.3), post-off 77 FPS (from 27.5)
- **Phase 20: Effects Re-Level (Recovery)**
  - `main.py`: god rays gated by day cycle (`_day_cycle > 0.2`), softened to 6 subtle rays — no starburst on menus
  - `main.py`: removed redundant full-screen additive fog tint that washed out contrast
  - `main.py`: vignette toggle was broken (rendered unconditionally) — fixed to respect `settings['vignette']`
  - `resources.py`: fog gradient alpha reduced (max 45→20) for softer horizon falloff
  - `config.py`: `BLOOM_THRESHOLD` 0.3→0.55, `BLOOM_INTENSITY` 0.6→0.45 — bloom only highlights genuine emissives
- **Phase 16: Visual Verification Harness (Recovery)**
  - `dev/verify_screenshots.py` — headless harness that captures start/gameplay/game-over screenshots, measures FPS with per-stage timings, and records projection probe points
  - `implementation_plan/verification.md` — guide documenting what correct frames must show
  - `implementation_plan/README.md` — updated rule 7 to require harness runs for every phase
- **Phase 21: Playability Sign-Off (Recovery)**
  - `README.md`: updated with harness screenshots (start, gameplay, game over)
  - `implementation_plan/qa_checklist.md`: updated with verification results
  - `dev/verify_screenshots.py`: captures all 4 states (start, playing, paused, game over)
- **Phase 15: Packaging & Release**
  - `pyproject.toml` — proper Python packaging with `pip install .` support, console entry point (`snakev2`), `moderngl` as optional `[gl]` extra, Python >= 3.8
  - `__version__.py` — single-source version (`VERSION = (0,1,0)`, `__version__ = '0.1.0'`)
  - `__main__.py` — supports `python __main__.py` entry
  - `snakev2/__main__.py` — supports `python -m snakev2`
  - `build.py` — PyInstaller build script for standalone executable
  - `README.md` — rewritten for players with controls, install, build, and CLI docs
  - `main.py` — startup hardening: friendly error messages for pygame init/display failures, CLI argument parsing (`--windowed`, `--fullscreen`, `--no-gl`, `--version`), app icon via `pygame.display.set_icon()`, version in window title
  - `resources.py` — `generate_app_icon()` function creates a 32x32 snake-head icon
  - `config.py` — imports `__version__` for reference
  - `AGENTS.md` — updated for final module layout and packaging
  - `CHANGELOG.md` — release entry for v0.1.0

- **Phase 06: Camera Dynamics**
  - Critically-damped spring smoothing (`CAM_SPRING_OMEGA = 5.0`) replaces plain lerp for camera eye and target tracking
  - Camera banking/roll into turns (`CAM_BANK_INTENSITY = 0.08`) via `on_turn(direction_change)`
  - Speed-based pull-back: camera distance/height increase with snake speed (`CAM_PULLBACK_SPEED = 0.3`)
  - Event reactions: eat punch-in (`CAM_EAT_PUNCH = 0.15` for `CAM_EAT_PUNCH_DURATION = 0.2s`), death slow pull-out (`CAM_DEATH_PULLOUT = 2.0x` over `CAM_DEATH_PULLOUT_DURATION = 0.5s`)
  - Camera-space screen shake via `shake(intensity, duration)` method — rotational noise applied in projection
  - Wrap-around snap detection: if camera-to-desired distance > threshold, instant snap with no swing
  - Camera height clamped to `CAM_MIN_HEIGHT = 20` to prevent ground clipping
  - Screen-space roll rotation applied in `project()` for banking effect
  - `config.py`: added `CAM_SPRING_OMEGA`, `CAM_BANK_INTENSITY`, `CAM_PULLBACK_SPEED`, `CAM_EAT_PUNCH`, `CAM_EAT_PUNCH_DURATION`, `CAM_DEATH_PULLOUT`, `CAM_DEATH_PULLOUT_DURATION`, `CAM_MIN_HEIGHT`

- **Phase 05: Particle Physics Upgrade**
  - `Particle.update()` uses configurable gravity (`PARTICLE_GRAVITY = 9.8 * 0.3`), air drag (`PARTICLE_AIR_DRAG = 0.99`), ground bounce with energy loss (`PARTICLE_BOUNCE = 0.4`), and ground friction (`PARTICLE_GROUND_FRICTION = 0.95`)
  - `ParticlePool` emitter methods: `emit_apple_burst(cx, cy, cz)` — juicy splash + sparks, `emit_movement_dust(cx, cy, cz, dir_x, dir_y)` — faint puffs on direction change, `emit_death_burst(cx, cy, cz)` — dramatic 40-particle burst, `emit_ambient_mote(cx, cy, cz)` — drifting motes/fireflies
  - `_spawn_eat_particles()` simplified to call `emit_apple_burst`
  - `update_ambient_particles()` simplified to call `emit_ambient_mote`
  - `move_snake()` emits movement dust on direction change
  - `initiate_death()` emits death burst
  - `config.py`: added `PARTICLE_GRAVITY`, `PARTICLE_BOUNCE`, `PARTICLE_GROUND_FRICTION`, `PARTICLE_AIR_DRAG`, `MAX_PARTICLES`

- **Phase 04: Procedural Animation & Squash-and-Stretch**
  - Eating animation: head squash-stretch (1.2x horizontal, 0.8x vertical for 0.15s via `EAT_SQUASH_DURATION`) and swallow bulge traveling down body (0.5s via `EAT_BULGE_DURATION`)
  - Apple spawn pop-in: scale 0→1 over `APPLE_SPAWN_SCALE_TIME = 0.3s` via `apple_anim` state
  - Snake idle life: eye blink every `BLINK_INTERVAL = 4.0s` (eyes close for 0.1s)
  - Death animation: 0.5s (`DEATH_ANIM_DURATION`) head recoil + body scale collapse toward tail before game-over screen
  - Death uses `initiate_death()` — sets death_anim state, prevents further movement, transitions to GAME_OVER after timer
  - `config.py`: added `EAT_SQUASH_DURATION`, `EAT_BULGE_DURATION`, `BLINK_INTERVAL`, `APPLE_SPAWN_SCALE_TIME`, `DEATH_ANIM_DURATION`

- **Phase 03: Spline-Based Continuous Snake Motion**
  - `utils.py`: new `sample_spline_path(path_points, num_segments)` — samples evenly-spaced positions from a Catmull-Rom curve traced through hex path history, returns `(px, py, tx, ty)` with tangent
  - `main.py`: `self.path_history = deque(maxlen=MAX_PATH_LENGTH)` stores head's recent hex positions
  - Snake segments positioned along the spline curve every frame — no more cell-to-cell hopping
  - Head orientation derived from spline tangent, causing natural banking into turns
  - Toroidal wrap detected by comparing wrapped vs unwrapped positions; on wrap, path_history is cleared and re-initialized from current snake positions
  - Growth on eating handled naturally by the spline curve; last segment lingers as new segments spread out
  - `_compute_dirty_rects()`, `render()` depth calculation, and `draw_snake_segment()` all use spline positions
  - `config.py`: added `SEGMENT_SPACING = 0.35`, `MAX_PATH_LENGTH = 60`

- **Phase 07: Unified Lighting Model**
  - Dynamic sun: `compute_sun_light()` rotates LIGHT_DIR around Z axis over time with varying ambient/sun_color
  - `compute_lighting()` helper for diffuse+specular on any surface given dynamic light params
  - All draw calls (tiles, snake, apple) use the same dynamic light computed once per frame
  - Emissive accent constants (`HEAD_EMISSIVE`, `EYE_EMISSIVE`, `APPLE_EMISSIVE`, `TILE_EDGE_EMISSIVE`)
  - GLSL shaders updated with `u_light_dir`, `u_ambient`, `u_sun_color`, `u_fog_color` uniforms
  - `gl_renderer.py` passes dynamic light uniforms to tile shader and post chain

- **Phase 08: Shadows & Ambient Occlusion**
  - Projected soft shadows: `draw_shadow()` projects shadow onto ground plane along current light direction
  - Shadow position = `(world_x + light_dir.x * height / -light_dir.z, ...)` with height-based stretch and softness
  - Snake segments and apple cast dynamic shadows that move with the sun
  - Tile AO improved: height variance from noise influences occlusion; occupied tiles get extra darkening via `AO_TILE_OCCUPIED`
  - Config constants: `SHADOW_ALPHA`, `SHADOW_SOFTNESS`, `SHADOW_MAX_LENGTH`, `AO_TILE_OCCUPIED`, `AO_TILE_EDGE`

- **Phase 09: Post-Processing Stack**
  - Software fallback: threshold-based bloom (only emissive/highlight pixels bloom), Reinhard tone mapping (`color / (color + 1)`), film grain overlay
  - GL path: toggleable staged pipeline (tone mapping → bloom → god rays → film grain → fog composite)
  - New GLSL shaders: `GL_TONE_MAP_FS` (filmic Uncharted2 curve), `GL_FILM_GRAIN_FS`
  - Bloom shader uses `u_bloom_threshold` uniform instead of hardcoded 0.25
  - God rays shader uses `u_sun_color` uniform instead of hardcoded blue-white
  - Event-driven color grading: warm orange flash on eat, cool blue shift on pause, desaturate/darken on death
  - Screenshot key (F12): saves composited frame to `screenshot_YYYYMMDD_HHMMSS.png`
  - Config toggles: `POST_BLOOM_ENABLED`, `POST_TONE_MAP_ENABLED`, `POST_GOD_RAYS_ENABLED`, `POST_VIGNETTE_ENABLED`, `POST_FILM_GRAIN_ENABLED`, `BLOOM_THRESHOLD`, `BLOOM_INTENSITY`, `FILM_GRAIN_STRENGTH`

- **Phase 10: Atmosphere & Environment**
  - Dynamic sky: `_update_sky()` regenerates sky gradient using `compute_sky_color()` — top/mid/horizon colors lerp based on day cycle with warm tint at dusk/dawn
  - Stars fade in/out based on day_cycle (`SKY_STAR_FADE_START`/`SKY_STAR_FADE_END`)
  - Water: wave speed/amplitude tied to `WATER_WAVE_SPEED`/`WATER_WAVE_AMP`; color tinted by sky; sun glints use dynamic `sun_color`
  - Depth fog tinted by current sky color (`self._fog_tint` computed per frame)
  - Ambient birds: V-shaped silhouettes that fly across the screen, respawning at edges
  - Island rim detail: tiles near max distance from center (dist_from_center > 0.7) get extra rock/debris decoration
  - Water shader accepts `u_water_color` and `u_water_highlight` uniforms
  - Config: `SKY_STAR_FADE_START`, `SKY_STAR_FADE_END`, `WATER_WAVE_SPEED`, `WATER_WAVE_AMP`, `FOG_DENSITY`, `ISLAND_EDGE_VARIATION`, `AMBIENT_BIRD_COUNT`, `AMBIENT_CLOUD_COUNT`

- Phase 11: Audio System
  - New `audio.py` module with `AudioManager` class
  - Procedurally generated sounds (eat chirp, slither rumble, death sting, UI click, score chime)
  - Generative ambient wind/water loop and day/night music with mood crossfade
  - Separate volume controls for music, SFX, and ambience channels
  - Ducking on death, mute toggle (M key), and pause audio handling
  - Safe no-op fallback when audio device is unavailable

- **Phase 13: Persistence**
  - New `persistence.py` module with `PersistenceManager` class
  - Save file in platform-appropriate user data directory (`platformdirs` if available, fallback to `~/.snakev2/`)
  - Human-readable JSON format with schema version field for future migration
  - Persists: high score, top-5 scores with ISO dates, all Phase 12 settings, lifetime stats (games played, apples eaten, total play time, longest snake)
  - Load on startup with full validation: missing file → defaults, corrupt file → defaults + overwrite, unknown fields → safe ignore, old/new schema → reset to defaults
  - Save on: settings change, game over, and clean quit (SIGINT/atexit)
  - Atomic writes via temp file + `os.replace` to prevent corruption mid-write
  - Game tracks per-session stats (apples eaten, max snake length, play duration) and records on game over
  - Saved settings auto-applied on next launch (volume, post-processing toggles, FPS display)
  - Title screen shows high score + lifetime summary line
  - Game-over "View Stats" overlay shows lifetime stats and top-5 leaderboard
  - `config.py`: added `PERSISTENCE_DIR`, `SAVE_FILENAME`, `SCHEMA_VERSION`

- **Phase 12: Menus, Settings & HUD Polish**
  - Title screen: animated "SNAKE V2" logo with glow pulse, live 3D scene backdrop with camera breathing drift
  - Menu system: Play / Settings / Quit with keyboard navigation (arrow keys + Enter) and mouse support
  - Settings screen: live-adjustable audio volumes (Music, SFX, Ambience), post-processing toggles (Bloom, Tone Map, God Rays, Vignette, Film Grain), Show FPS toggle
  - Pause menu: Resume / Settings / Restart / Quit with score display, dim overlay using `PAUSE_BLUR_ALPHA`
  - Game over: animated score count-up over 1.5s, "NEW RECORD!" bounce callout, menu options after count-up
  - HUD: score pop animation on change (`SCORE_POP_DURATION = 0.3`), speed indicator (dots), minimap restyled with panel border
  - Smooth fade transitions between all screens (`MENU_FADE_SPEED = 4.0`)
  - New `game_state.py`: `GameState.SETTINGS`
  - `camera.py`: `update_idle()` — gentle sinusoidal breathing drift for menu/idle states
  - `main.py`: restructured `run()` as continuous state machine, updated `handle_events()` with menu navigation, transition system with fade overlay
  - `ui.py`: consolidated draw helpers (`_draw_panel`, `_draw_menu_items`), all menu screens keyboard + mouse navigable
  - `config.py`: added `MENU_FADE_SPEED`, `SCORE_POP_DURATION`, `SPEED_INDICATOR_DOTS`, `PAUSE_BLUR_ALPHA`

### Changed
- **Phase 02: Performance Foundation**
  - Static tile data (world-space hex corners, base colors, grass blades, dist_factor, tex_variation) pre-computed at startup in `ResourceManager._init_scene_data()`
  - Added `_tile_static_cache` and `_ground_static_cache` dicts on ResourceManager for per-frame reuse
  - `draw_tile()` and `_draw_tile_decorations()` refactored to use pre-computed cache; only camera projection and dynamic lighting run per frame
  - `_build_tile_cache()` now has early-return check (`_tile_cache_valid`) — skips rebuild when cache is valid
  - `_build_ground()` separated from `_build_tile_cache()`; uses pre-computed world-space bottom corner data
  - `all_hexes()` result cached at module level in `utils.py` (avoids generator recreation)
  - Removed `_full_redraw_counter >= 60` forced full redraw (negated dirty-rect optimization)
  - GL FBO read (`fbo_tile.read()`) now only occurs when tile cache is invalid
  - Added `_debug_overlay` toggle (F1 key) and `_perf_timings` dict with per-stage timing instrumentation
  - Added `draw_debug_overlay()` in `ui.py` — shows FPS and per-stage frame times (tiles, snake, particles, post-FX, UI)
  - `render()` wrapped each section (tiles, snake, post, particles, UI) with `time.perf_counter()` timers
  - `_compute_dirty_rects()` uses `self._snake_set` (computed once per frame at top of render)
  - Performance overlay toggles on/off with F1 key without game restart

- **Phase 01: Fixed Timestep & Frame-Rate Independence**
  - Game loop rewritten with fixed-timestep accumulator (FIXED_DT = 1/180s)
  - Simulation decoupled from rendering; render runs at RENDER_FPS (60) via `clock.tick(RENDER_FPS)`
  - `update(dt)` always receives FIXED_DT for consistent physics stepping
  - `camera.follow_snake()` moved out of `update()` into `render()` (once per frame)
  - `eat_flash` and `screen_shake` converted from frame-counter to time-based (seconds)
  - `update_ambient_particles` probability scaled by `dt * 60` to maintain constant spawn rate
  - `frame_count` removed; replaced by `render_time` (accumulated real-time seconds)
  - Pause no longer accumulates simulation time; resume causes no time jump
  - Game-over uses separate particle accumulator (particles animate at fixed rate)
  - Start screen uses `clock.tick(RENDER_FPS)` (was 30)
  - `config.py`: added `FIXED_DT`, `RENDER_FPS`; removed unused `FPS`
