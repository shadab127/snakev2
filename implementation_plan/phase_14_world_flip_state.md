# Phase 14 - Dive and World-Flip State

Requires: Phase 13.

## Goal

Turn a continuous seam crossing into a smooth, intentional 180-degree world
flip without freezing gameplay.

## Do

1. Add a dedicated wrap-transition state separate from banking and menu fades.
2. Track seam axes, period delta, duration, dive progress, visual orientation,
   and completion state.
3. Ease the snake dive, 0-to-180-degree world roll, and emergence together;
   hide the head at the midpoint of the roll.
4. Compose the world rotation with an orthonormal camera basis or retained world
   stage. Do not linearly invert `Camera.up` or allocate a rotated full screen
   surface every frame.
5. Keep UI, menus, minimap labels, input, and canonical controls upright.
6. Allow normal logical movement during an active transition.

## Files

`main.py`, `camera.py`, `config.py`, `ui.py`, `dev/check_frames.py`, and tests.

## Done When

A seam crossing produces one smooth dive, a 180-degree world roll, and an
upright UI with no dropped, duplicated, or delayed gameplay move.

## Do Not

- Do not couple normal turn banking to world orientation.
- Do not use a hard cut or full-screen fade to hide the wrap.
