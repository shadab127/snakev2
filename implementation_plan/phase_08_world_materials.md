# Phase 08 - World Materials

Requires: Phase 07.

## Goal

Make the terrain, horizon, water, and vegetation read as one layered world.

## Do

1. Refine cached tile top, bevel, and side colors with low-frequency moss, dirt,
   height, and vegetation variation.
2. Use subtle tile-edge contrast instead of heavy black outlines.
3. Fade distant terrain toward the horizon while keeping nearby tile contrast.
4. Clip water to the real projected horizon for every camera heading and remove
   stale reflected-sky artifacts.
5. Keep vegetation density controlled by the existing quality preset.

## Files

`resources.py`, `main.py`, `config.py`, `gl_renderer.py`, `shaders.py`, and
`dev/check_frames.py`.

## Done When

Baseline captures show clean water/horizon separation, readable tile depth, and
natural material variation without a Phase 01 frame-budget regression.

## Do Not

- Do not alter board coordinates or wrapping yet.
- Do not add a full-screen effect to hide material issues.
