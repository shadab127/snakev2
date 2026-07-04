# Phase 03 — Scene Exposure and Sky

Read `implementation_plan/README.md` first. Requires phase 02 (scene visible).

**Goal:** The bare scene revealed by phase 02 is currently under-exposed — near-black
sky, very dark tiles (see `reference_good_frame.png`). Make the scene clearly
readable: a player must instantly distinguish sky, tiles, snake, and apple.

## Scope
- Brighten and re-balance the palette in `config.py` (tiles, sky gradient, water)
  so gameplay frames land at a comfortable mid exposure — checker target: mean
  gameplay luma between 40 and 110 instead of ~18 today. Prefer tuning the
  existing constants over new code.
- The sky band above the horizon gets a visible vertical gradient (not flat
  near-black); stars remain but subtle.
- Tile top faces must be clearly lighter than tile side faces, so the hex relief
  reads at a glance.
- Keep the day-cycle: verify the scene stays inside the luma window at the
  brightest and darkest points of the cycle (run the checker at two different
  ambient times — add a `--time` option to the checker if needed; that is the
  one allowed checker change, it must only *add* strictness).
- Tighten the checker's gameplay luma window to 40–110 once achieved, so later
  phases can't drift the exposure.

## Out of Scope
- Snake/apple geometry (04–05). New effects. Fog (07).

## Files
`config.py`, `resources.py` (sky), `dev/check_frames.py` (only the additions above)

## Acceptance Criteria
- Checker passes with the tightened luma window at both tested day-cycle times.
- Side-by-side before/after screenshots committed under `dev/screenshots/`;
  tiles, sky, snake, and apple each clearly distinguishable in the after shot.
- No full-screen additive overlay introduced (rule 6).
- Test suite green.
