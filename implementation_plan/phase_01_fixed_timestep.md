# Phase 01 — Fixed Timestep & Frame-Rate Independence

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** Simulation runs at a fixed logical rate, fully decoupled from rendering,
so game speed and animations are identical on any machine.

**Depends on:** None. This is the foundation for all physics phases.

## Scope
- One timing scheme for the whole game loop: simulation steps at a fixed rate,
  rendering runs as fast as the display allows and interpolates between steps.
- Replace every animation that counts frames with elapsed-time-based animation.
- Remove the mixed frame caps (the loop currently ticks at 30 in some states and 60
  in others) — one render FPS target, defined in `config.py`.
- Pause, menus, and the game-over screen must not accumulate simulation time;
  resuming must cause no jump.

## Out of Scope
- Any change to movement feel, speed curve, physics, or visuals.

## Likely Files
`main.py`, `config.py`, `particle.py`, `ui.py`

## Acceptance Criteria
- Gameplay speed is unchanged when the render FPS cap is temporarily halved or doubled.
- A search for frame-counter-driven animation timing finds no remaining cases.
- Pausing for 10+ seconds and resuming causes no time jump in movement or effects.
- Game plays exactly as before at the normal frame rate.
