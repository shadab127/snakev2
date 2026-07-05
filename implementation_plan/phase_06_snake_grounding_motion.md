# Phase 06 — Snake Grounding & Motion Feel

Read `implementation_plan/README.md` first. Requires phase 05 (the tube exists).

**Goal:** The snake belongs to the world physically: it hugs the terrain, has
weight, and its motion reads as slithering rather than sliding.

## Scope
- Contact: the tube's underside meets the tile tops (a slight flatten at
  contact is ideal); the head sits at the same height as the body, not floating
  above it (today the head sphere hovers noticeably).
- One soft contact shadow under the whole body, following the tube (today each
  ball casts its own blob, reinforcing the "separate balls" look).
- Slither: a subtle lateral S-wave along the body while moving (amplitude and
  wavelength in `config.py`, small enough not to affect gameplay readability;
  the head follows the logical path exactly — only the body weaves).
- Weight cues: brief head dip/settle on eating (compose with the existing
  squash), and the existing death collapse lands the tube onto the ground, not
  through it.
- Apple physical consistency: rests on its tile with a matching contact shadow
  (reuse the body-shadow approach).
- Never violate world rules: no part of the body may clip below tile tops or
  through tile sides during any animation, wrap, or turn.

## Out of Scope
- New gameplay mechanics. Particles. Camera.

## Files
`main.py` (snake/apple drawing, shadow), `config.py`, maybe `utils.py`

## Acceptance Criteria
- Screenshots straight/turning/eating: body visibly in contact with tiles, one
  continuous shadow, no floating head, no clipping into tiles.
- Slither wave visible in a 3-frame sequence but subtle (amplitude a small
  fraction of body width); with the config set to 0 it fully disables.
- Full checker passes apart from phase-07 luma reds; FPS passes; tests green.
