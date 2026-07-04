# Phase 04 — Snake Body Continuity

Read `implementation_plan/README.md` first. Requires phase 03.

**Goal:** The snake reads as one connected creature. Today it renders as a column
of small separated rings floating above the tiles (see
`reference_good_frame.png`) — it does not look like a snake at all.

## Scope
- Body segments must visually connect: consecutive segments overlap or are joined
  so there are no gaps at any speed, including mid-move interpolation and while
  turning.
- Segments sit **on** the tile tops (contact, not hovering). If segment height
  comes from a config offset, fix the offset; if it comes from projection misuse,
  fix that at the source.
- Segment size scales sensibly: body roughly two-thirds of a tile across, slight
  taper toward the tail; no donut/ring look — segments are solid.
- The body must not draw a streak when the snake wraps across the torus edge.
- Death and eating animations still work on the fixed body.

## Out of Scope
- Head detail and apple (phase 05). Camera (06). New animation features.

## Files
`main.py` (snake drawing), `config.py`, maybe `utils.py` (spline sampling)

## Acceptance Criteria
- Gameplay screenshot after ~50 steps shows one continuous snake resting on tiles;
  commit before/after shots.
- 30+ turns simulated headless: no frame shows detached segments or a wrap streak
  (spot-check several captured frames, including one straddling the torus edge —
  drive the snake across an edge in the harness run).
- Checker still passes; test suite green.
