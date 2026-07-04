# Phase 02 — Remove the White-Out Overlays; Safe Defaults

Read `implementation_plan/README.md` first. Requires phase 01 (checker exists and
currently fails).

**Goal:** The screen shows the actual scene instead of a near-white wash, with
default settings and with old save files.

## Verified Cause
With default settings the frame has mean luma ~196 and saturation ~1 (white).
Disabling the film-grain overlay and the fog tint reveals a correct scene.
The grain overlay covers the whole screen and is blitted additively every frame;
the fog tint is another full-screen additive blit on top.

## Scope
- Delete the full-screen film-grain overlay and its config/settings entries
  entirely — game code, config, settings UI, and saved-settings handling. Do not
  try to "fix" it; remove it. (Rule 6: full-screen additive overlays are banned.)
- Replace the full-screen additive fog tint with nothing for now (phase 07 adds
  correct per-tile depth fade). Remove its dead config if unused elsewhere.
- Audit the render path for any other full-screen additive blits; list each one
  found in the changelog entry and remove or convert any that brighten the whole
  frame (per-object glows and the bloom composite may stay if the checker passes).
- Old save files must not resurrect removed toggles: unknown/removed settings keys
  in the save file are dropped on load. Verify by loading a save that has
  `film_grain: true`.
- Sweep every game state (start, settings, playing, paused, game over): no state
  may show the wash.

## Out of Scope
- Making the underlying scene prettier or brighter (phase 03). Snake/apple visuals
  (04–05). Performance beyond not regressing.

## Files
`main.py`, `config.py`, `persistence.py`, `ui.py` (settings menu), maybe `resources.py`

## Acceptance Criteria
- Checker: luma / white-pixel / saturation / distinct-color checks PASS for all
  four states (FPS may still fail; that's later).
- A save file containing removed settings keys loads cleanly and does not
  re-enable anything.
- Screenshots visibly show the game world in every state.
- Test suite green.
