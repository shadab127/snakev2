# Phase 13 - Periodic World Rendering

Requires: Phase 12.

## Goal

Render the continuous board around the unwrapped visual camera.

## Do

1. Render and cull the nearest periodic terrain instances around the camera.
2. Render the nearest periodic copies of apples, grass interactions, shadows,
   and particles.
3. Make terrain caches understand visual period offset and retain deterministic
   material, height, AO, and neighbor continuity across seams.
4. Implement the same visible topology in software and GL paths.
5. Add captures for all six seam directions and two-axis corners.

## Files

`main.py`, `resources.py`, `gl_renderer.py`, `utils.py`, `particle.py`,
`dev/check_frames.py`, and tests.

## Done When

Every seam has continuous terrain with no blank gap, exposed island rim, doubled
object, or large per-frame cost, and the existing movement tests remain green.

## Do Not

- Do not draw every possible periodic copy every frame.
- Do not add the world roll before the board itself is continuous.
