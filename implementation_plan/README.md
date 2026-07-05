# SnakeV2 — Fix Plan v5

Read this file fully, then do ONLY your assigned phase.

## Verified problems (2026-07-05, screenshots in this folder)

Screenshots: `symptom_straight.png`, `symptom_long_turn.png`.

1. **Motion is not smooth.** The snake teleports one cell per move step
   (~7 times/second) while the camera glides. Cause: `move_lerp` is computed in
   the run loop but **never used** — no drawing code reads it. Raw FPS is fine
   (100+); the judder is discrete stepping, not slow rendering.
2. **Body is a bead chain, and too long.** The body renders as overlapping
   sphere sprites (beads). Worse: spline samples spread over the whole
   `path_history`, which is longer than the snake — in `symptom_long_turn.png`
   a 13-segment snake renders as ~25 beads spanning the map.
3. **Turn garbage remains.** `symptom_long_turn.png` top-left: blue striped
   wedge (water strips leaking into the sky — only strip centers are culled,
   not endpoints). Middle: solid black band under the body (the continuous
   shadow polygon self-intersects when the path bends).
4. **Tiles look like separate blocks.** Every tile is an extruded prism with
   deep dark grooves on all sides; the snake appears to run in a canyon between
   blocks ("blocks holding the snake"). Terrain should read as one surface.
5. The checker currently prints ALL PASS — it cannot see any of the above.
   Each phase below adds the check that would have caught its bug.

## Rules — read twice, follow exactly

1. Do ONLY what your phase file lists under Scope. If you think something else
   needs fixing, write it in the changelog note — do not fix it.
2. Touch ONLY the files your phase lists. No new files unless listed.
3. Before starting AND before declaring done, run BOTH:
   - `python dev/check_frames.py`  (must exit 0 when you finish)
   - `python -m pytest tests/ -q`  (must pass)
   If `python` lacks pygame, use `.venv/bin/python`.
4. Never loosen, skip, or delete a checker check. Add only what your phase says.
5. Look at the screenshots your phase tells you to save. If the picture does
   not match the acceptance description, the phase is not done.
6. No full-screen additive overlays. Tunables go in `config.py`.
7. One short `CHANGELOG.md` entry when done. Small diffs.

## Phases (strict order, one per session)

| Phase | Fixes problem |
|---|---|
| 01 | #1 — smooth per-frame motion via move_lerp |
| 02 | #2 — correct body length, one tube instead of beads |
| 03 | #3 — kill water wedge + shadow band |
| 04 | #4 — terrain reads as one surface |
| 05 | frame pacing on a real display |
| 06 | human sign-off |
