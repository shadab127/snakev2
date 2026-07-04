# Phase 06 — Camera Framing

Read `implementation_plan/README.md` first. Requires phase 04 (a visible snake to
frame).

**Goal:** The follow camera frames the action so the player can plan ahead: snake
head in the lower third of the screen, several tiles of lookahead visible, horizon
comfortably high.

## Scope
- Tune existing camera constants in `config.py` (distance, height, lookahead, FOV)
  — this phase should be mostly constant tuning, not new code:
  - head projects into the lower-central band of the screen (checker: head screen
    position between 55% and 80% of screen height, horizontally centered ±10%);
  - at least 4 tiles of clear lookahead ahead of the head are on screen;
  - the horizon line sits in the upper third; sky never fills more than ~40% of
    the frame during normal play.
- Turning: after a turn the camera settles behind the new direction within ~1
  second without overshoot oscillation (capture a burst of frames after a turn
  and confirm the settle).
- Torus wrap: crossing every edge produces a smooth camera transition — capture
  frames straddling a wrap to prove it.
- Add the head-position band as a checker gameplay check.

## Out of Scope
- Rewriting camera math (orientation is already correct). Event punch-ins/shake
  tuning beyond what framing requires.

## Files
`config.py`, `camera.py` (only if constants can't achieve it), `dev/check_frames.py`
(add the head-band check)

## Acceptance Criteria
- Checker (with new head-band check) passes.
- Committed screenshots: straight run, mid-turn, and wrap crossing — all framed
  per the targets above.
- Test suite green.
