# Phase 16 — Visual Verification Harness (Recovery)

Before starting: read `AGENTS.md` and `implementation_plan/README.md` (Recovery section).

**Goal:** Make it impossible to "complete" a phase without actually looking at the
game. Every later recovery phase proves itself with screenshots and measured FPS.

**Depends on:** None. Do this first — phases 01–15 passed their own criteria while
the game was visibly broken, because nothing ever rendered a frame and looked at it.

## Scope
- A small dev script (not part of the game) that launches the game headless (dummy
  video driver), advances it to a given state (start screen / playing N steps /
  game over), and saves screenshots to a known folder.
- The same script reports measured render FPS over a fixed number of frames, with
  post-processing on and off, plus the per-stage timings from the existing perf overlay.
- A projection probe mode: print the screen position of a handful of known world
  points (grid center at ground level, a point above it, the snake head) so
  orientation bugs are visible in numbers.
- Document in this folder (`verification.md`) how to run it and what a correct frame
  must show; add "run the harness, attach/inspect screenshots" as a required step to
  the rules in `README.md`.

## Out of Scope
- Fixing anything the harness reveals. Later phases do that.
- CI, image-diff tooling.

## Likely Files
New dev script (e.g. under `tests/` or a `dev/` folder), `implementation_plan/verification.md`, `implementation_plan/README.md`

## Acceptance Criteria
- One command produces screenshots of start screen and mid-gameplay, an FPS report,
  and the probe-point table.
- The harness itself needs no display and no ModernGL.
- Current known-broken output is captured and committed as the "before" baseline.
