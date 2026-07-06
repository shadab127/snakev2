# Phase 02 — Fix the Body Snap (True Smooth Motion)

Read `implementation_plan/README.md` first. Requires phase 01.

**Problem (measured):** The body's world position advances ~0.4 units/frame for
8 frames, then jumps 52.5 units (one full cell) in one frame, every move step.

**Cause:** In `render()` in `main.py` there are TWO spline blocks. The low-res
block (head/camera) interpolates `raw[i+1] → raw[i]` where samples are ONE
CELL apart — correct. The high-res block (body, `n_high = len(snake) * 10`)
interpolates `raw_high[i+1] → raw_high[i]` where samples are 1/10 CELL apart —
so during a step the body creeps 1/10 of a cell, then snaps 9/10 of a cell
when `path_history` gains the new head cell.

## Do
1. In the high-res block, make `lerp_t` advance each sample by ONE FULL CELL
   (10 high-res samples), matching the low-res block: sample i interpolates
   from `raw_high[i + 10]` toward `raw_high[i]` (sample the spline one extra
   cell long to provide the +10 window; the extended path already includes
   `next_head_pos()`).
2. Verify the drawn head (high-res sample 0) still coincides with the low-res
   head every frame — no gap between head sprite and neck.
3. Update the checker `motion_continuity` check to measure the BODY (a
   mid-body high-res sample), not just the head: over 20 consecutive frames at
   default speed, max single-frame world-distance jump ≤ 2× median. Must FAIL
   before your fix (the 52-unit snap), PASS after.

## Do NOT
- Do not touch speed constants, camera, sprites, shadow, tiles, water.
- Do not restructure render(); this is an indexing/window fix inside the
  existing high-res block.

## Files
`main.py`, `dev/check_frames.py` (the one check update)

## Done when
- `motion_continuity` (body version) PASSes; checker exit 0 except checks
  owned by later phases (record them); tests green.
- Save 4 consecutive mid-step frames to `dev/screenshots/`: the whole body
  advances a similar small distance in each frame — no snap.
