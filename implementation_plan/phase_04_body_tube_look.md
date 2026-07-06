# Phase 04 — Body Look: Tube, Not Spheres

Read `implementation_plan/README.md` first. Requires phase 02.

**Problem:** The body is drawn by blitting a sphere sprite per spline sample
(`generate_sphere_sprite` — ring pattern + specular dot). Overlapping spheres
read as "a continuation of green spheres", not a snake (see
`symptom_straight.png`).

## Do
1. Stop blitting sphere sprites for body samples. Draw the body as a filled
   polygon strip instead: for each consecutive pair of high-res samples,
   connect their left/right edge points (perpendicular to the tangent, width
   from the existing taper formula) into one quad; fill with the segment's
   color. This yields ONE continuous silhouette.
2. Color along the strip: `SNAKE_COLORS` gradient head→tail, multiplied by
   the existing sun-diffuse factor. Per-quad flat fill is fine; no specular.
3. On top, add a single narrow highlight strip: same construction but ~35% of
   the width, offset slightly toward the light, one lighter color
   (`add_color(base, (35,35,35))`). This gives the tube a rounded read
   without per-sample sphere shading.
4. Round the two ends: one filled circle at the neck (under the head sprite)
   and one at the tail tip, same colors as their strip ends.
5. Keep eat-bulge and death-collapse working (they modulate the width used in
   step 1).
6. Update the checker `body_beads` check (add if missing): along the body
   midline in a straight-run frame, luma variation between adjacent samples
   must be small (no bright/dark bead rhythm). Must FAIL before, PASS after.

## Do NOT
- Do not touch the head sprite, apple, tiles, water, shadow, camera, speed.
- Do not remove `generate_sphere_sprite` (the head/apple may use it).
- Do not add glow, bloom, or any full-screen effect.

## Files
`main.py` (body drawing), `config.py` (highlight tunables), `resources.py`
(only if a strip-color helper belongs there), `dev/check_frames.py` (one check)

## Done when
- `body_beads` PASSes; checker exit 0 except later-phase checks; tests green.
- Screenshots straight + mid-turn saved: one smooth green tube with a single
  highlight line, rounded tail, no repeating sphere pattern. Visibly better
  than `symptom_straight.png`.
