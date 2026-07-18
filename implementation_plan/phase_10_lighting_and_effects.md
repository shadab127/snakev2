# Phase 10 - Lighting and Event Effects

Requires: Phase 09.

## Goal

Make lighting, shadows, food, and particles support the improved world and
snake rather than compete with them.

## Do

1. Apply the same sun and ambient model to terrain, snake, apple, and shadows.
2. Match the soft contact shadow to the actual body-strip silhouette and fade it
   with snake height, death, and later seam submersion.
3. Refine apple glow and event particles using cached assets and the world color
   palette.
4. Keep bloom, tone map, god rays, and vignette optional; the scene must still
   be clear with all post-effects off.
5. Recheck depth ordering around foreground tile sides.

## Files

`main.py`, `particle.py`, `resources.py`, `config.py`, `gl_renderer.py`,
`shaders.py`, and `dev/check_frames.py`.

## Done When

Food, particles, shadows, and lighting are coherent in baseline captures, with
no detached shadow, obscured snake, or Phase 01 performance regression.

## Do Not

- Do not add an always-on full-screen pass.
- Do not solve the seam transition in this phase.
