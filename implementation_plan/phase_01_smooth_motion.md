# Phase 01 — Smooth Per-Frame Motion

Read `implementation_plan/README.md` first.

**Problem:** The snake jumps one hex cell per move step; between steps it does
not move at all. `move_lerp` (0→1 progress toward the next step, already
computed in `run()` in `main.py`) is never consumed by any drawing code.

## Scope
1. In the render path, compute the head's **drawn** position by advancing it
   along its movement direction by `move_lerp` × one cell distance (use the
   existing spline/`path_history`; the logical grid position must NOT change).
2. Every body sample moves forward the same fractional amount along the path,
   so the whole snake flows continuously every frame.
3. The camera follows the drawn (interpolated) head, not the cell center.
4. Eating, collision, wrapping stay purely logical — they already trigger on
   grid positions; do not touch that code.
5. Add one checker check `motion_continuity`: during a straight run at default
   speed, capture 20 consecutive frames; the head's screen position must change
   on EVERY frame, and no single-frame jump may exceed 2× the median per-frame
   movement. This check must FAIL before your fix and PASS after.

## Do NOT
- Do not change movement speed, input handling, or collision.
- Do not touch tiles, water, shadow, sky, or body appearance (beads stay for
  now — phase 02 owns looks).

## Files
`main.py`, `dev/check_frames.py` (the one new check), `config.py` if a tunable
is needed.

## Done when
- `motion_continuity` PASSes; full checker exits 0; tests green.
- Save 3 consecutive-frame screenshots mid-move to `dev/screenshots/` — the
  snake is at a visibly different position in each, with no cell-sized jump.
