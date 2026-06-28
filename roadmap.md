# Roadmap

## Overview

This roadmap covers the next major features for the project — transforming it from a fixed-isometric
monolithic snake game into a modular, dynamic 3D follow-cam experience with a scrolling toroidal
world, progressive difficulty, and a mini-map.

---

## Phase 2 — Progressive Speed

**Objective:** Snake starts slow and accelerates as it eats apples.

- Add `base_move_interval` attribute (e.g. `0.07` seconds per tick).
- Compute effective interval as `max(0.025, base_move_interval - score * 0.0005)`.
- Replace the fixed `1.0 / FPS` threshold in `update()` with the dynamic value.
- Reset to base on `reset()`.

**Files touched:** `snake.py` or `main.py` — `__init__`, `reset`, `update`.
**Effort:** Easy (~5 lines).
**Dependencies:** None.

---

## Phase 3 — Mini-Map

**Objective:** Small top-down hex map at top-left showing snake body, apple position, and grid outline.

- New `draw_minimap(surf)` method in `ui.py`.
- Render a simplified top-down hex grid on a small surface (~140×140 px).
- Draw snake segments as bright green dots, apple as a red dot.
- Position: top-left corner, after bloom/post-processing but before vignette.
- Semi-transparent dark background for readability.

**Files touched:** `ui.py`, `main.py` (call site).
**Effort:** Medium (~40 lines).
**Dependencies:** Phase 1 (modules exist).

---

## Phase 4 — Camera System Overhaul (Follow Cam + Toroidal World)

This is the flagship change. It has two tightly coupled sub-items.

### 4a — Toroidal World (Wrap Instead of Die)

**Objective:** Snake wraps around grid edges instead of dying.

- Remove the `in_bounds()` death check in `move_snake()`.
- Convert axial coordinates `(q, r)` to offset coordinates `(col, row)`, apply modulo on the grid
  extent, convert back.
- This gives a seamless wrapping toroidal grid.

**Files touched:** `grid.py`, `snake.py`.
**Effort:** Medium.

### 4b — 3D Follow Camera

**Objective:** Replace the fixed isometric `project()` with a full 3D view/projection pipeline
that follows the snake head.

- **Camera position:** Offset above and behind the snake head:
  `cam_pos = head_world_pos + reverse_direction * DISTANCE + vec3(0, 0, HEIGHT_OFFSET)`
- **Look-at target:** Snake head position + small forward lookahead.
- **Up vector:** `(0, 0, 1)` — keeps the world upright from the user's perspective.
- Implement a lightweight 4×4 matrix stack (lookAt + perspective projection) in `camera.py`.
- Replace every call to `project(x, y, z)` with the new pipeline: world → view → projection → viewport.
- **Tile frustum culling:** Only render tiles within visible range of the camera, avoiding drawing
  all 169 tiles when most are off-screen.

**Files touched:** `camera.py`, `utils.py`, `renderer.py`, `gl_renderer.py`, `renderer_soft.py`,
`grid.py`, `ui.py`, `main.py` — ~30–40 call sites.
**Effort:** Very Hard — core architectural change.
**Dependencies:** None.

---

## Risks

### Phase 2 (Progressive Speed)
- **Regression:** Speed curve may feel unbalanced.
- **Mitigation:** Expose `base_move_interval` as a constant in `config.py` for easy tweaking.

### Phase 3 (Mini-Map)
- **Regression:** Overlaps with score panel at top-left.
- **Mitigation:** Place mini-map below or beside the score panel, or give it its own corner.

### Phase 4a (Wrapping)
- **Regression:** Hex wrapping via offset coordinates may drift visually on non-rectangular hex grids. The hexagonal play area (`max(|q|,|r|,|q+r|) <= GRID_RADIUS`) means offset-coordinate modulo wraps corner cells outside valid hex bounds.
- **Mitigation:** Use rectangular wrapping (treat grid as ~15×15 parallelogram in offset coords) — simpler and visually effective. Clamp post-wrap coordinates to valid range if needed. Test thoroughly at all 6 edges.

### Phase 4b (3D Camera)
- **Regression:** Every rendering function changes; any missed `project()` call causes visual glitches.
- **Regression:** New projection may change the apparent size/position of tiles, water, particles, etc.
- **Mitigation:** Keep the old `project()` alongside the new pipeline during development for A/B
  comparison. Add visual regression markers (known screen positions) to verify correctness.
- **Regression:** Camera may clip into the ground or tilt unexpectedly.
- **Mitigation:** Clamp camera height and distance; never let the up-vector align with the
  look direction (gimbal lock prevention).
