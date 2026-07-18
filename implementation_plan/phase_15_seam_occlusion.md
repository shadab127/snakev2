# Phase 15 - Under-Seam Occlusion

Requires: Phase 14.

## Goal

Make the snake actually appear to pass below the outgoing world seam.

## Do

1. Give transition body samples presentation-only depth, visibility, and shadow
   factors.
2. Split dynamic drawing into under-seam, seam/tile occluder, and above-world
   passes.
3. Draw submerged body before the seam occluder, then draw emerged body after
   it.
4. Fade matching shadows, glow, dust, and nearby particles as their source
   sample submerges.
5. Force the correct cache/redraw behavior for every animated transition frame.
6. Add midpoint pixel checks for hidden body, clean seam, and upright HUD.

## Files

`main.py`, `particle.py`, `resources.py`, `gl_renderer.py`, `config.py`,
`dev/check_frames.py`, and tests.

## Done When

The submerged snake is visibly occluded by terrain, no orphaned shadow or glow
remains above it, and no stale tile or dirty-rectangle artifact appears.

## Do Not

- Do not rely only on existing item depth buckets; terrain is already composited
  before dynamic items.
- Do not alter canonical collision height or position.
