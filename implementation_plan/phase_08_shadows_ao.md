# Phase 08 — Shadows & Ambient Occlusion

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** Objects are grounded in the world by real contact shadows and soft
occlusion, instead of floating on evenly-lit tiles.

**Depends on:** Phase 07.

## Scope
- Projected blob/soft shadows for the snake (every segment) and the apple, cast onto
  tile tops along the current sun direction, stretching/softening with object height.
- Shadow darkness blends with the lighting model (never pure black; respects ambient).
- Improve tile-to-tile ambient occlusion: crevices between tiles and the base of tile
  sides get subtle darkening; occupied tiles darken under the snake body.
- Both render paths (GL and software) must show shadows; quality may differ, presence
  may not.

## Out of Scope
- True shadow-mapping — soft projected shadows are the target, not depth-buffer shadows.
- Post-processing (phase 09).

## Likely Files
`main.py`, `gl_renderer.py`, `shaders.py`, `utils.py`, `config.py`

## Acceptance Criteria
- Snake and apple each cast a visible soft shadow that moves with the sun direction.
- Shadows lengthen/shift consistently with the lighting phase of the day cycle.
- No z-fighting or shadow flicker while moving.
- Frame budget holds.
