# Phase 06 — Camera Dynamics

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** The follow camera feels like a physical camera operator — smooth, weighty,
and reactive to game events.

**Depends on:** Phase 03.

## Scope
- Replace plain lerp following with critically-damped smoothing (position and
  look-target track with velocity, no overshoot wobble unless intended).
- Subtle banking/roll into turns; smooth speed-based pull-back so a faster snake gets
  a slightly wider view.
- Event reactions: small punch-in on eating; slow dramatic pull-out on death; gentle
  breathing drift while on menus/idle screens.
- Replace the current screen-shake with camera-space shake (rotational, decaying
  noise) that respects the 3D pipeline.
- Camera never clips into the ground; look direction never degenerates (no flips).
- Wrap-around handling: when the snake teleports across the torus edge, the camera
  must transition without a violent swing (choose and document one strategy, e.g.
  snap-with-fade or shortest-path tracking).

## Out of Scope
- Player-controlled camera (zoom/orbit) — not in this plan.
- Rendering/lighting changes.

## Likely Files
`camera.py`, `config.py`, `main.py`

## Acceptance Criteria
- No overshoot jitter when the snake turns repeatedly; motion feels damped, not laggy.
- Eating and dying each produce a visible, tasteful camera response.
- Crossing every torus edge in each direction produces no camera whiplash.
- Old screen-shake code paths are removed.
