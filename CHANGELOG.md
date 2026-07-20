# Changelog

## v9 — Post-Sign-Off Review Fixes

A code review of Phases 01–16 found two player-visible bugs, several latent
correctness bugs, incomplete Phase 14/15 requirements, and checker guardrails
that overstated what they enforced. All findings addressed:

### Player-visible bugs

- **Double-wrap transition snap (main.py).** A second seam crossing landing
  inside an already-active wrap transition retriggered a fresh transition
  dict, snapping `roll_angle`/`dive_amount` back to 0 mid-roll — a hard cut.
  `move_snake()` now leaves an in-flight transition running untouched.
- **Periodic terrain copy misalignment (main.py, utils.py, gl_renderer.py).**
  The Phase 13 seam fill blitted the tile cache a second time shifted by a
  flat world-space pixel offset — invalid under a perspective camera, since
  the screen-space delta for a one-period world shift isn't constant across
  the frame. It was producing a visible duplicated-terrain ghost at seams.
  Replaced with `utils.nearest_period_offset()`, which solves for the
  correct whole-period axial shift per tile/entity and re-projects it through
  the real camera; verified pixel-exact against ground truth. Applied to both
  the software tile cache and the GL `render_tiles_to_fbo` path.

### Phase 14 — World flip state

- Composed the wrap-transition world roll into the camera's existing
  screen-space rotation (`Camera.world_roll`, additive with banking `roll`)
  instead of `pygame.transform.rotate()` on a captured full-screen surface
  each animated frame. Verified mathematically identical to rotating
  `Camera.up` around the view-forward axis, to floating-point precision.
- Head sprite (and the body strip's neck cap, found during verification —
  both draw a head-colored blob at the same spot) are now hidden within
  `WRAP_HEAD_HIDE_WINDOW` radians of the roll midpoint (`roll_angle == pi/2`,
  the instant the world is edge-on to the camera).

### Phase 15 — Under-seam occlusion

- Split the dynamic draw into three passes: under-seam (submerged tail
  segments, on an empty cache), seam/tile occluder (the terrain blit), and
  above-world (apple, emerged body, heads) — replacing the old approach of a
  color-fade tint depth-sorted against terrain. `_compute_body_segments` now
  returns a `submerged_start` split index; `_draw_continuous_shadow` uses the
  same seam threshold so no shadow patch is left orphaned above hidden body.
- Added `check_wrap_transition_midpoint` (dev/check_frames.py): drives a real
  wrap transition to its roll midpoint and verifies (via render-diff against
  the same simulation state with the hide condition defeated — exact-color
  matching is unreliable once bloom/tone-map are applied) the head is hidden
  and the HUD stays upright and legible.

### Latent correctness bugs

- `MAX_PATH_LENGTH` (60) was below the max possible snake length (225 cells on
  the full board) — the path deque silently dropped tail history past that,
  desyncing the body spline. Now `(2*GRID_RADIUS+1)**2 + 1`.
- `perlin_noise`'s cache key omitted `persistence`, so `tile_noise`'s `crack`
  channel (same x/y/scale/octaves as `moss`, different persistence) silently
  aliased `moss` — cracks were drawn from moss noise. Key now includes it.
- The catch-up overrun counter checked `sim_accumulator > cap` after the
  accumulator was already clamped to that cap, so the check was always false.
  Moved the check before the clamp.
- `draw_minimap` centered on the head using raw unwrapped pixel distance, so
  cells more than half a board away rendered at their far (unwrapped)
  position instead of wrapping to their near side. Now wraps the axial delta
  to its shortest toroidal representative before projecting to the minimap.
- `compute_tile_ao` used the pre-Phase-11 hexagon-board edge-distance formula
  (`max(|q|,|r|,|q+r|)/R`). Replaced with the parallelogram-board formula
  (`max(|q|,|r|)/R`) matching `in_bounds()`/`wrap_coords()`.

### Guardrail honesty (dev/check_frames.py)

- `turn_yaw_rate` label now reads `≤ 230°/s` (the actual enforced threshold)
  instead of the stale `≤ 4.0°/frame`.
- `body_beads` label now reads `p90 ≤ max(40, median×5)` (the actual dynamic
  threshold) instead of a stale fixed `≤ 30`.
- `fps` renamed to `render_fps (render() only)` — it only times `render()`,
  not the full per-frame loop (`check_frame_pacing`, which does, runs ~2x
  slower per frame).
- `check_sky_purity`'s grass-silhouette clause now requires both blue and red
  channels above a floor relative to green, so saturated pure-green garbage
  (0,255,0) — which is green-dominant but has near-zero blue/red, unlike real
  desaturated terrain colors — no longer passes.
- `check_sun_anchoring` no longer auto-passes whenever the sun is off-screen
  in exactly one of the two frames; it now also requires the visible frame's
  sun position to be far enough from center that "swept past the edge" is a
  plausible explanation.

### Performance / cleanup

- Cached camera banking-roll `sin`/`cos` per camera update instead of
  recomputing per projected point (~30 projection sites/frame) in
  `Camera.project()`.
- Resolved the dual pacing authority: `clock.tick(RENDER_FPS)` is now only
  used as a software cap when display vsync did not engage; when it did,
  `clock.tick()` (no arg) just measures elapsed time without adding a second
  cap. Debug overlay now shows vsync status.
- `_frame_times` is now a `collections.deque(maxlen=FRAME_TIME_WINDOW)`
  instead of a plain list re-sliced every frame. Debug overlay adds p50 and
  resolution.
- Cached the score-pop and NEW-RECORD-bounce `pygame.font.Font` objects by
  size (ui.py) instead of constructing a fresh one every frame. Reused a
  persistent `_fade_surf` for the transition fade overlay instead of
  allocating a fresh full-screen `SRCALPHA` surface every fade frame.
- Removed dead code: unused `_visual_head_pos` method; unused
  `trimmed`/`extended` locals in the snake-draw-items block of `render()`.

### Test coverage

- Added `TestWrapTransitionStateMachine` (tests/test_headless.py): dive→roll→
  emerge phase progression, roll-angle monotonicity, clean reset on
  completion, and a targeted regression test for the double-wrap-during-
  active-transition bug (forces the second wrap to land during the roll
  phase specifically, since landing during dive — before roll_angle rises off
  zero — would pass even with the bug present).
- Added `test_catch_up_overrun_counter_fires` (tests/test_headless.py).

## v8 — Small-Step Smooth World Plan (Phase 16 Sign-Off)

Phase 16 proves the performance, graphics, and world-flip work of Phases 01–15
hold together in real gameplay. Running the sign-off matrix surfaced three
defects (two of them incomplete earlier phases), which were fixed and verified
before sign-off, per the rule "do not waive a failed scenario because normal
movement looks correct."

### Fixes found during sign-off

- **Board topology (completes Phase 11).** `wrap_coords()` wraps over the full
  15×15 axial parallelogram (225 cells), but `all_hexes()`/`in_bounds()` still
  described the old 169-cell hexagon. The snake could step onto ~56 reachable
  cells that had no terrain and floated over empty water. `in_bounds()` and
  `all_hexes()` now describe the same parallelogram `wrap_coords()` maps onto, so
  every reachable cell has terrain. Added regression tests: board matches the
  wrap domain exactly and is closed under all six moves + wrap.
- **Sun reflection / god rays (main.py).** Both filled `(*sun_color, alpha)` rows
  then blitted with `BLEND_ADD`, which ignores per-pixel alpha and added the full
  color — producing saturated white blocks in the sky and over-bright rays.
  Premultiplied the color by intensity so both stay faint.
- **Wrap-transition redraw + rim darkness.** During the world roll the whole
  screen is rotated, but only the first transition frame forced a full redraw, so
  later rotated frames used stale dirty-rects computed in un-rotated space. Now
  every active-transition frame does a full redraw (the rotate is ~2 ms, cheap).
  The larger parallelogram board also exposed near-black corner rims; raised the
  tile side-face light floor (0.10 → 0.18) so distant rims never read as pure
  black (which looked like a hole).

### Checker refinements (guardrails, not behavior)

- `check_sky_purity`: accepts legitimate terrain silhouette (the bigger board's
  far corner rises into the top quarter during hard turns) while still catching
  water-blue leaks and warm garbage. Verified against synthetic leaks/garbage.
- `check_shadow_band`: now requires a dark band to have vertical thickness
  (≥3 adjacent scanlines) so a 1-pixel tile-seam crease under the body no longer
  trips it. A pre-existing single-scanline flake; a real solid band still fails.
- Seeded the checker's RNG (`random.seed`) so terrain decoration/particles/grass
  are deterministic run-to-run — removes borderline pixel-check flakiness.
- Refreshed the visual regression baseline to match the parallelogram board.

### Sign-off results (Phase 16)

- **Automated:** `pytest` 135 passed / 5 skipped; `dev/check_frames.py` ALL PASS
  (stable across repeated runs after RNG seeding).
- **Gameplay/wrap matrix (headless, driven as independent probes):** all six
  directions, two-axis corner wraps, 5+ repeated same-edge wraps, rapid per-move
  turns, food pickup (including on a seam), pause→resume→death→restart, maximum
  speed, and long-snake seam crossing — all pass with canonical state valid
  (every segment in-bounds and on terrain), no crash, and no visible body/camera
  teleport at seams.
- **Transition review:** pre-dive, submerged, mid-flip (90°), emergence, and
  post-flip captures all render correctly; UI/HUD/minimap stay upright through the
  roll; end-of-transition is seamless (last rolled frame == post frame rotated
  180° within ~1.8 luma — no hard cut).
- **Frame budget (Apple M4 Pro, macOS 26.5, Python 3.9.6, pygame 2.6.1/SDL 2.28.4,
  software renderer, quality=high, 1280×800):**
  - Normal gameplay: p50 7.5 ms, p95 8.0 ms, p99 14.0 ms (~133 fps median).
  - Hardest scenario (repeated world flips): p50 9.0 ms, p95 11.5 ms,
    p99 25.3 ms. The p99 is a single warm-up outlier; the sustained transition
    budget holds well under the 60 fps frame time.
  - Checker `fps` 133, `frame_pacing` p95/median ratio ~1.0.

### Backends and limitations

- **Software renderer is the validated, default backend** and passes the full
  sign-off. `moderngl` is an optional extra and not installed by default.
- **OpenGL backend (Apple M4 Pro, GL 4.1 Metal):** renders visually correct
  output — the full frame checker passes on GL, and it inherits the parallelogram
  board fix automatically (it shares `all_hexes()`/`in_bounds()`). **Limitation:**
  `_build_tile_cache` reads the tile FBO back to the CPU via a per-pixel Python
  `struct.unpack` loop over ~1M pixels (~1 s per full rebuild), so the GL path is
  not real-time on a full redraw. This is pre-existing (Phase 14/15) and out of
  Phase 16's scope; a proper fix needs a vectorized (numpy) readback. Recommend
  running with the software renderer until that is addressed.
- **`dev/check_frames.py --compare-baseline` (pre-existing, opt-in only):** this
  optional mode saves the baseline from a single static gameplay frame but
  compares against a 50-random-step gameplay capture, so the two paths never
  agree on `distinct` color count and gameplay always exceeds the 200 tolerance.
  It fails on the pristine tree too and is independent of the primary
  `check_frames.py` sign-off (which passes ALL). Left as-is; a real fix would
  align the two capture paths or compare a static frame on both sides.

## v6 — Fix Plan v6

### Phase 01 — Restore Guardrails
- Restored `tests/`, `dev/check_frames.py`, `AGENTS.md` from commit `62a4805`
- Updated tests: `compute_lighting` removed from utils (2 skipped), `Camera.shake` removed (3 skipped), `PersistenceManager.set_high_score` → `add_score`
- Appended guardrail rule 1 to AGENTS.md
- Checker: ALL PASS

### Phase 02 — Body Snap Fix
- Replaced independent high-res spline computation with subsampling of the low-res spline positions (`_subsample_spline_positions`) — eliminates the 52px body snap caused by divergent spline calculations at move-step boundaries
- Updated `motion_continuity` checker to measure mid-body high-res sample instead of head, with 50-frame window to capture move steps
- Checker: ALL PASS, Tests: 124 passed
