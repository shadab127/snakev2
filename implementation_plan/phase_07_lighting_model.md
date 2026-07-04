# Phase 07 — Unified Lighting Model

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** One consistent lighting model across every rendered object, with a moving
sun that changes the scene's mood over time.

**Depends on:** Phase 02. Independent of the physics track.

## Scope
- Single light definition (sun direction + color + ambient) used by tiles, snake,
  apple, and particles — both in the GL path and the software fallback. Today each
  object shades itself ad hoc; unify it.
- Day cycle: the sun position already animates — make lighting actually follow it
  (warmer/lower light at cycle extremes, cooler at the top), slowly and subtly.
- Snake and apple get proper diffuse + specular response so their curved surfaces
  read as glossy and round under the sun.
- Emissive accents (snake eyes, apple shine, tile edge glow) defined consistently so
  phase 09 bloom can pick them up.
- All light colors/intensities in `config.py`.

## Out of Scope
- Shadows and AO (phase 08). Post-processing (phase 09). Sky visuals (phase 10).

## Likely Files
`shaders.py`, `gl_renderer.py`, `main.py`, `config.py`, `utils.py`

## Acceptance Criteria
- Rotating sun visibly changes tile face brightness and object highlights together —
  nothing is lit from a stale direction.
- GL path and software fallback show the same lighting direction and comparable mood.
- Snake body shows a moving specular highlight as it slithers.
- Frame budget holds.
