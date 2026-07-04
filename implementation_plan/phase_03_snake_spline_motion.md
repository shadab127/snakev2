# Phase 03 — Continuous Snake Motion (Spline Body)

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** The snake moves as one continuous creature flowing along a smooth curve,
instead of segments hopping cell-to-cell.

**Depends on:** Phase 02.

## Scope
- The body follows a smooth curve traced through the head's recent path; segments are
  placed at even spacing along that curve every frame.
- Rounded cornering: turns sweep through an arc instead of pivoting instantly at
  hex-cell centers.
- Head orientation (and eye placement) comes from the direction of travel along the
  curve, so the head banks naturally into turns.
- Toroidal wrap-around stays seamless: when the head wraps to the far edge, the body
  must not draw a streak across the whole map.
- Growth after eating extends the body smoothly from the tail.

## Out of Scope
- Squash-and-stretch or other secondary animation (phase 04).
- Camera changes (phase 06).
- Any change to the logical grid movement, collision, or speed rules.

## Likely Files
`main.py`, `utils.py`, `config.py`

## Acceptance Criteria
- At all speeds, no visible popping or snapping between cells anywhere on the body.
- Turns are visibly rounded and every body segment follows the exact path the head took.
- Wrapping at all edges shows no visual artifacts.
- Self-collision and apple-eating behave exactly as before (logic unchanged).
