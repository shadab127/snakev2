# Phase 05 — Head and Apple Readability

Read `implementation_plan/README.md` first. Requires phase 04.

**Goal:** The two most important objects on screen — the snake's head and the
apple — are unmistakable at a glance while moving at full speed.

## Scope
- Head: clearly larger than body segments, distinct color (config already has
  `HEAD_COLOR`), eyes visible and facing the direction of travel.
- Apple: sits on its tile (not floating, not sunken), sized close to a body
  segment so it reads as "food", clearly red against the green tiles, with its
  existing subtle glow/bob kept only if it doesn't violate rule 6.
- Both must remain readable at the far side of the board (small on screen) —
  check a frame where the apple is distant.
- Verify the eat interaction looks right: head reaches the apple's tile, apple
  disappears, particles fire at the apple's position (not offset).

## Out of Scope
- Camera (06). Balance/speed. New effects.

## Files
`main.py` (head/apple drawing), `config.py`

## Acceptance Criteria
- Screenshot with apple near and another with apple far: both instantly readable;
  commit both.
- A non-player looking at one gameplay frame can point to the head and the apple
  without hints (describe frames in the changelog note).
- Checker passes; test suite green.
