# Phase 03 - Background and UI Surface Reuse

Requires: Phase 02.

## Goal

Remove cheap-but-constant full-screen allocation and blit work from normal
frames.

## Do

1. Reuse or quantize the sky gradient instead of allocating a new surface every
   render.
2. Skip star blits at zero alpha and refresh the reflected-sky cache only when
   its source sky changes.
3. Reuse fade, water, and grade surfaces; clear only the regions they own.
4. Cache static HUD and minimap layers, leaving only values and markers dynamic.
5. Measure the before/after background and UI timing from Phase 01.

## Files

`resources.py`, `main.py`, `ui.py`, `config.py`, and `dev/check_frames.py`.

## Done When

Normal gameplay creates no new sky, fade, or static UI full-screen surface per
frame, and the recorded background/UI p95 time improves or stays neutral.

## Do Not

- Do not make the sky or water stop animating.
- Do not change world materials in this phase.
