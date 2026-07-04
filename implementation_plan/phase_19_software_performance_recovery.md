# Phase 19 — Software-Path Performance Recovery

Before starting: read `AGENTS.md` and `implementation_plan/README.md` (Recovery
section). Use the phase-16 harness FPS report before and after.

**Goal:** Hit the 60 FPS target on the software (pygame-only) path, which is the
path most machines actually use. Measured today: **~4 FPS** with default settings,
~18 FPS with all post-processing off.

**Depends on:** Phase 16 (measure), ideally after 17–18 (don't optimize wrong pixels).

## Measured Hotspots (from profiling — re-profile before starting)
1. Software "bloom" and "tone map" walk half the screen with per-pixel
   `get_at`/`set_at` — ~30 million pixel calls per second of gameplay. This one
   change accounts for most of the 4 FPS.
2. Film grain scatters 2,000 per-pixel dots into a fresh full-screen surface every
   frame.
3. `_build_ground` re-projects and redraws every tile's underside polygon every
   frame, even though the camera barely moves between frames.
4. Full tile repaint every frame (~18k polygon draws per 60 frames).

## Scope
- Software post-processing must use whole-surface operations (scaling, blits,
  blend flags, precomputed overlays) — never per-pixel Python loops in the frame
  path. Any effect that can't be done that way cheaply gets dropped from the
  software path (visual honesty over parity).
- Cache ground/tile rendering so static geometry is only re-projected when the
  camera actually moved beyond a threshold, and reuse cached frames while it hasn't.
- Re-profile after each fix; chase the next hotspot until the target is met.
- Update `frame_budget.md` with real measured numbers per stage on this machine.

## Out of Scope
- Visual changes beyond simplifying software-path effects (GL path untouched).
- New features. Gameplay logic.

## Likely Files
`main.py`, `resources.py`, `utils.py`, `config.py`

## Acceptance Criteria
- Harness reports ≥ 60 FPS average during gameplay on the software path with
  default settings, and no per-frame stage over its `frame_budget.md` budget.
- No per-pixel Python loop remains in the per-frame render path.
- Screenshots before/after post-simplification still look acceptable (bloom-ish
  glow may be cheaper, but the scene must not look stripped bare).
