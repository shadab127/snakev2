# Phase 05 — Snake Body: Rounded, Shaded Tube

Read `implementation_plan/README.md` first. Requires phase 02 (its polygons must
respect near-plane rules).

**Goal:** The snake looks like a snake: one continuous, rounded, shaded tube
from head to tail. Today it's a flat light-green ribbon with a glossy sphere
head (see `symptom_straight.png`) — the "rectangular block" the player sees.
The ribbon already bends smoothly along the spline; what's missing is any
rounded, shaded 3D form.

## Scope
- Replace the flat ribbon with a single coherent body:
  dense sampling along the existing spline so cross-sections overlap into a
  smooth tube; each cross-section shaded as a rounded form (lit top, darker
  flanks — the existing sphere-sprite look, but sized and spaced to merge into
  one body, not read as separate balls).
- One unified color scheme along the body: the current mismatch (bright flat
  green strip vs dark balls) must be gone; use the existing `SNAKE_COLORS`
  gradient head→tail with the lighting model applied consistently.
- Width tapers smoothly to the tail; no sprite pops when segment sizes change.
- Turns: the tube bends smoothly through corners with no gaps, kinks, or
  self-intersection artifacts at any speed, including during camera swings and
  torus wraps.
- Draw order: the tube renders as one depth-sorted object relative to tiles and
  apple (no tile edges poking through the middle of the body).
- Keep eat-bulge, death-collapse, and breathing animations working on the tube.

## Out of Scope
- Head/eyes/tongue detail and apple (unchanged this phase). Grounding/shadow
  (06). Gameplay logic.

## Files
`main.py` (snake drawing), `utils.py` (spline sampling density), `resources.py`
(body sprites), `config.py`

## Acceptance Criteria
- Straight-run screenshot: one continuous shaded tube, no visible ribbon, no
  separate balls; committed next to a copy of `symptom_straight.png` for
  comparison.
- Turn screenshots (from the checker's turn capture): tube bends smoothly, no
  gaps/kinks/streaks.
- Full checker passes apart from phase-07 luma reds; FPS check passes (denser
  sampling must fit the budget — use cached sprites, not per-pixel work).
- Tests green.
