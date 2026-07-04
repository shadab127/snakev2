# Phase 01 — Frame Checker with Pass/Fail Gates

Read `implementation_plan/README.md` first.

**Goal:** One command that measures the game's rendered frames and prints PASS or
FAIL per check, with exit code 0 only when everything passes. This is the gate
every later phase must clear. Do **not** fix the game in this phase.

## Scope
- New script `dev/check_frames.py` (reuse logic from `dev/verify_screenshots.py`
  where helpful). Headless (dummy video driver), no ModernGL needed. It must:
  1. Launch the game, capture screenshots of: start screen, gameplay (after ~50
     simulation steps), paused, game over. Save them to `dev/screenshots/`.
  2. For each screenshot, sample pixels on a grid and check:
     - mean luma between 8 and 140 (catches black-outs and white-outs);
     - fewer than 5% of sampled pixels near pure white;
     - mean color saturation ≥ 6 (catches grey wash);
     - at least 100 distinct sampled colors (catches blank/flat frames).
  3. Orientation probe during gameplay: a world point above the ground must
     project **higher** on screen than the same point at ground level.
  4. Measure gameplay FPS with default settings over ~50 frames: PASS at ≥ 55.
  5. Print a table of every check with measured value vs threshold and PASS/FAIL;
     exit 0 only if all pass.
- Write `implementation_plan/checks.md` documenting each check, its threshold,
  and how to run the script.
- Run it once and commit its output table (as text in `checks.md`) as the
  baseline. **Expected result today: FAIL** on luma/white/saturation for all
  states (the white-out bug) and possibly FPS. That failing baseline is correct.

## Out of Scope
- Any change to game code. This phase only observes.

## Files
New `dev/check_frames.py`, new `implementation_plan/checks.md`

## Acceptance Criteria
- `python dev/check_frames.py` runs headless, prints the table, exits non-zero
  today (correctly detecting the white-out), and would exit 0 on a healthy frame.
- Thresholds live in the script in one obvious place, documented in `checks.md`.
- Screenshots land in `dev/screenshots/` for human spot-checks.
