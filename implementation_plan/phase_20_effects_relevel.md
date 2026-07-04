# Phase 20 — Effects Re-Level (Recovery)

Before starting: read `AGENTS.md` and `implementation_plan/README.md` (Recovery
section). Requires phases 17–19 (correct, fast scene to grade on top of).

**Goal:** Post-processing and atmosphere enhance the scene instead of obscuring it.
Today the frame is washed out by additive haze, and god rays render as a harsh
white line starburst pinned mid-screen.

**Depends on:** Phases 17, 18, 19.

## Observed Symptoms (verified)
- God rays: ~12 hard white lines radiating from a fixed point — dominates every
  frame including menus; not tied to a visible sun disc.
- A full-screen additive fog tint plus fog surface plus haze band flattens contrast;
  everything reads pale blue-grey.
- Ambient particles/stars render over UI panels and over the whole frame uniformly,
  adding to the washed-out look.

## Scope
- God rays: visible only when the actual sun disc is on/near screen, soft and subtle,
  emanating from the sun's screen position, never drawn as bare lines. If the sun
  isn't part of the composed scene, draw the sun first — rays need a source.
- Fog/atmosphere: one coherent depth-fog design — distance-based, horizon-weighted,
  never a uniform full-screen additive wash. Contrast between near tiles and sky
  must survive.
- Re-tune bloom threshold/intensity so only genuine emissives glow (per phase 09's
  original intent), on both paths.
- Layer ordering: nothing atmospheric draws over HUD/menus; effects respect the
  scene/UI boundary.
- Walk every toggle in settings and confirm each effect's on/off states both look
  intentional.

## Out of Scope
- New effects. Performance beyond keeping phase-19 numbers.

## Likely Files
`main.py`, `shaders.py`, `gl_renderer.py`, `resources.py`, `config.py`

## Acceptance Criteria
- Screenshots: no stray line starburst; sun-anchored soft rays only when the sun is
  visible; near tiles crisp with real contrast, distance fading naturally.
- HUD and menu text render over effects, never under them.
- Phase-19 FPS target still met with all effects on.
