# Phase 12 - Unwrapped Visual Path

Requires: Phase 11.

## Goal

Keep the snake body and camera moving one cell at a time across a wrapped edge.

## Do

1. Retain canonical `self.snake` for gameplay and add unbounded visual history,
   visual head/lookahead, and accumulated period offset for presentation.
2. Populate the visual path from raw next positions instead of rebuilding it
   from wrapped positions.
3. Drive both spline sampling and camera following from the visual path.
4. Rebase visual coordinates only by whole periods when no visible sample jumps.
5. Test canonical food/collision behavior and bounded camera/body movement at
   each seam.

## Files

`main.py`, `camera.py`, `utils.py`, `tests/test_headless.py`,
`tests/test_camera.py`, and `dev/check_frames.py`.

## Done When

A q-edge sequence renders as continuous positions such as `7 -> 8 -> 9` while
canonical gameplay is `7 -> -7 -> -6`, with no visible body or camera jump.

## Do Not

- Do not remove only the old path reset; replace it with the unwrapped path.
- Do not make score, collision, or food depend on visual coordinates.
