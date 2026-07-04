# Phase 02 — Performance Foundation

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** Stable 60 FPS with clear headroom, plus a way to measure it, before the
physics and graphics phases add rendering cost.

**Depends on:** Phase 01.

## Scope
- Stop recomputing static per-tile data every frame (noise lookups, material colors,
  world-space corner geometry). Compute once at startup; only camera projection
  happens per frame.
- Profile the render path and fix the top remaining hotspots (the tile cache is known
  to be rebuilt every frame — see "Known quirks" in `AGENTS.md`).
- Add a debug performance overlay, toggled by a key, showing FPS and per-stage frame
  time (tiles, snake, particles, post-processing, UI).
- Document the frame budget per stage in this folder as `frame_budget.md` so later
  phases can check against it.

## Out of Scope
- Any visual change. Screenshots before/after must look identical.
- New rendering features.

## Likely Files
`main.py`, `gl_renderer.py`, `utils.py`, `resources.py`, `config.py`

## Acceptance Criteria
- Steady 60 FPS during normal play, including with a long snake (20+ segments).
- Performance overlay toggles on/off and shows per-stage timings.
- No visible difference in the rendered scene compared to before this phase.
