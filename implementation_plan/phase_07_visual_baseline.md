# Phase 07 - Visual Regression Baseline

Requires: Phase 06.

## Goal

Create deterministic evidence for later graphics work.

## Do

1. Capture straight, turning, long-snake, food, death, dawn, day, and night
   frames for every supported renderer and default quality.
2. Add durable automated checks for body continuity, no water above the horizon,
   readable HUD contrast, and no detached shadow.
3. Store only intentional golden captures and document their generation command.
4. Record the Phase 01 timing data alongside each capture set.

## Files

`dev/check_frames.py`, `dev/screenshots/`, focused tests, and release notes.

## Done When

The checker creates reproducible baseline captures and fails on a deliberately
introduced body, horizon, or HUD regression.

## Do Not

- Do not change world or snake art in this phase.
- Do not weaken a visual check to accept an existing artifact.
