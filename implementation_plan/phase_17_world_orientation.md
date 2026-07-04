# Phase 17 — World Orientation Fix (Recovery)

Before starting: read `AGENTS.md`, `implementation_plan/README.md` (Recovery section),
and run the phase-16 harness to see the current broken state.

**Goal:** The world renders right-side up. This is the single biggest reason the
game is unplayable.

**Depends on:** Phase 16.

## Observed Symptoms (verified)
- The hex island renders at the **top** of the screen like a ceiling; sky/water fill
  the bottom. The snake hangs below the tiles as a vertical chain.
- Projection probe: a world point 18 units **above** the ground projects **lower**
  on screen than the ground point — world +z maps to screen-down. It must map to
  screen-up.

## Scope
- Fix the camera/projection math (view matrix, up-vector, or NDC-to-screen mapping —
  find the actual root cause, don't patch symptoms elsewhere) so that:
  - up in the world is up on the screen;
  - the island sits in the lower/middle of the frame with sky above the horizon;
  - the snake rests on top of the tiles.
- Verify the fix applies to both render paths (software always; GL if available) and
  to everything projected: tiles, snake, apple, particles, shadows, water.
- Verify controls match the view after the fix: turning left visibly turns the snake
  left on screen. Fix input mapping only if the corrected view proves it wrong.
- Re-run the phase-16 probe and screenshots; update the baseline.

## Out of Scope
- Performance (phase 19). Post-processing looks (phase 20). Camera feel tuning
  (already implemented; only correctness here).

## Likely Files
`camera.py`, possibly `main.py` / `gl_renderer.py` call sites, `config.py`

## Acceptance Criteria
- Probe: elevated points project above ground points; head projects above its tile.
- Screenshots: horizon with sky above, island below; snake sits on the tiles.
- Depth ordering of near/far tiles is not regressed by the fix.
- All existing tests still pass.
