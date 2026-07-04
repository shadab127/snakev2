# Phase 05 — Particle Physics Upgrade

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** Particles behave like physical objects in the 3D world — with gravity,
bounce, and drag — instead of simple 2D screen sprites.

**Depends on:** Phase 02 (works best after 04).

## Scope
- Particles simulate in world space with gravity, air drag, ground bounce with energy
  loss, and lifetime fade; they render through the camera like everything else.
- Distinct effects, each tuned in `config.py`:
  - Apple burst: juicy splash plus a few sparks that bounce on the ground.
  - Movement dust: faint puffs at the ground on direction changes.
  - Death: dramatic burst matching the phase-04 death animation.
  - Ambient: occasional drifting motes/fireflies in the air.
- Keep the existing object pool; cap active particles with graceful degradation
  (oldest die first when over budget).

## Out of Scope
- Glow/bloom treatment of particles (phase 09 handles that).
- Weather systems (phase 10).

## Likely Files
`particle.py`, `main.py`, `config.py`

## Acceptance Criteria
- Sparks visibly fall, hit the ground plane, and bounce with reduced energy.
- Particles farther from the camera render smaller/dimmer (they live in the world).
- All four effect types trigger in the right situations.
- Frame budget holds even during a burst with the particle cap reached.
