# Phase 10 — Atmosphere & Environment

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** The floating hex island lives in a rich, believable world — sky, water,
fog, and ambient life that react to the day cycle.

**Depends on:** Phases 07 and 09.

## Scope
- Sky: gradient and star/cloud layers follow the sun's day cycle (dawn/dusk warmth,
  darker zenith at night-phase); stars fade in only during the dark phase.
- Water around the island: animated waves with sun glints, plus a soft reflection
  hint of the island; water color tracks the sky.
- Depth fog: distance-based atmospheric fog consistent between both render paths,
  tinted by the current sky color.
- Island edges: tiles at the rim get natural variation (grass tufts, small rocks or
  overhang detail) so the island edge doesn't look machine-cut.
- Ambient life: drifting clouds above, occasional birds or floating leaves — sparse
  and subtle.

## Out of Scope
- Gameplay changes. Audio (phase 11).

## Likely Files
`resources.py`, `main.py`, `shaders.py`, `gl_renderer.py`, `config.py`, `utils.py`

## Acceptance Criteria
- Watching one full day cycle shows sky, water, fog, and lighting changing in concert.
- Water visibly moves and glints; the island reads as floating above it.
- Distant tiles fade into atmosphere; near tiles are crisp.
- Frame budget holds; software fallback shows the same scene with simpler effects.
