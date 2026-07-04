# Phase 18 — Scene Correctness Pass (Recovery)

Before starting: read `AGENTS.md` and `implementation_plan/README.md` (Recovery
section). Requires the phase-17 orientation fix.

**Goal:** With the world right-side up, everything in the scene looks like what it
is: hexes look like hexes, the snake looks like one connected creature, water and
sky sit where they belong.

**Depends on:** Phase 17.

## Observed Symptoms (verified, pre-17 — recheck each after 17)
- Tiles render as sheared checkerboard quads rather than hexagonal prisms.
- Snake body appears as separate floating blobs, not a connected body on the ground.
- Water/fog band position looks arbitrary; scene composition is unreadable.

## Scope
- Re-verify each symptom after phase 17 (many may be consequences of the inverted
  view). Fix what remains:
  - correct tile top/side face visibility and painter's-algorithm depth order from
    the follow camera at all angles;
  - snake body segments connected and grounded, spline path hugging tile tops,
    correct overlap order with tiles and apple;
  - water plane, island underside, and fog band composed correctly relative to the
    horizon;
  - minimap orientation agrees with the world (turning left on screen moves the
    minimap dot the same way).
- Screenshot every state (start, playing, paused, game over) via the harness and
  check composition in each.

## Out of Scope
- Performance (phase 19), post-processing tuning (phase 20), UI text (phase 21).

## Likely Files
`main.py`, `gl_renderer.py`, `utils.py`, `resources.py`

## Acceptance Criteria
- Screenshots show recognizable hexagonal tiles, a connected snake resting on them,
  apple on a tile, water below the island edge, sky above the horizon.
- No draw-order popping while the snake moves and turns for 30+ seconds.
- Minimap movement direction matches on-screen movement.
