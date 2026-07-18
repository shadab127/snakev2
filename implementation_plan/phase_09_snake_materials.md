# Phase 09 - Snake Head and Body

Requires: Phase 08.

## Goal

Make the snake read as a single, responsive creature in every movement state.

## Do

1. Preserve the continuous body strip and improve its taper, neck blend, tail
   cap, and broad head-to-tail color gradient.
2. Add a darker underside and one directional dorsal highlight that follows the
   spline without creating bead-like bands.
3. Improve head readability through shape, eyes, and facial contrast in turns.
4. Keep slither, squash/stretch, eating bulge, and death collapse attached to
   the same body silhouette.
5. Add or update body-continuity capture checks.

## Files

`main.py`, `resources.py`, `config.py`, `dev/check_frames.py`, and tests.

## Done When

Straight and turning frames show one gap-free tapered snake with a legible head,
no sphere/bead rhythm, and no regression to motion continuity or frame budget.

## Do Not

- Do not restore per-segment sphere sprites.
- Do not change canonical snake movement.
