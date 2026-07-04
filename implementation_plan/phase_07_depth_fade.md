# Phase 07 — Per-Tile Depth Fade

Read `implementation_plan/README.md` first. Requires phases 03 and 06.

**Goal:** Restore a sense of atmosphere and depth — distant tiles fade gently
toward the sky color — without any full-screen overlay (rule 6).

## Scope
- Fade each tile's own draw color toward the sky/horizon color as a function of
  its camera distance (per-tile color blend at draw time — the fog factor per
  tile can reuse the projected depth that already exists).
- Applies to tile tops, tile sides, and the island's under-side/water edge so the
  far rim doesn't pop against the sky.
- Snake, apple, and particles are NOT faded (they stay readable — gameplay wins
  over realism here).
- Strength tunable in `config.py`; zero must mean visually off.
- FPS must not drop: the blend happens on colors already being computed per tile,
  not as a new pass. Verify with the checker's FPS check.

## Out of Scope
- Bloom/god-ray rework. Weather. Any full-screen pass.

## Files
`main.py` (tile color computation), `config.py`

## Acceptance Criteria
- Screenshot: near tiles full color, far tiles visibly blended toward the horizon,
  no banding, no washed frame — checker saturation/luma checks still pass.
- Setting the strength to 0 reproduces the phase-06 frame (commit both shots).
- Checker FPS check still passes; test suite green.
