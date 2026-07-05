# Phase 01 — Checker: Turn-Sequence Capture

Read `implementation_plan/README.md` first.

**Goal:** The frame checker catches the turn blow-up. Today it only screenshots
steady moments, so the worst frames in the game are never measured. Do not fix
the game in this phase — only extend the checker.

## Scope
- Extend `dev/check_frames.py`:
  1. During gameplay capture, perform a scripted **double turn** (two lefts a few
     steps apart, then two rights) and capture ~10 frames spread across each
     camera swing.
  2. Every captured turn frame must pass the same pixel checks as steady
     gameplay (luma window, white %, saturation, distinct colors).
  3. New **sky purity** check on turn frames: in the top quarter of the frame,
     at most a small percentage of sampled pixels may fall outside the sky
     palette (dark blues/near-black); warm/tan/bright-green pixels up there mean
     mirrored-geometry wedges. Save the worst turn frame as
     `dev/screenshots/turn_worst.png`.
  4. Make the script runnable as `python dev/check_frames.py` from the repo root
     without setting PYTHONPATH manually.
- Update `implementation_plan/checks.md` with the new checks and thresholds.
- Run it and record the baseline table in `checks.md`. **Expected today:** turn
  frames FAIL sky purity (and possibly luma); steady gameplay luma FAIL 29.9 is
  already known. That failing baseline is the correct outcome of this phase.

## Out of Scope
- Any change to game code.

## Files
`dev/check_frames.py`, `implementation_plan/checks.md`

## Acceptance Criteria
- Checker performs the turn script headless, saves `turn_worst.png`, prints
  per-turn-frame rows in the table, and exits non-zero today because of them.
- Visually confirm `turn_worst.png` shows the wedge/bowtie corruption (compare
  `symptom_turn_blowup.png`) — proof the new check sees the real bug.
- Test suite green.
