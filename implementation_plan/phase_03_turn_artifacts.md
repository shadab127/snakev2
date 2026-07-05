# Phase 03 — Kill the Water Wedge and the Black Shadow Band

Read `implementation_plan/README.md` first. Requires phase 02 (the shadow
follows the fixed body).

**Problem:** Two remaining turn/geometry artifacts (see `symptom_long_turn.png`):
- **Blue striped wedge** upper-left: water strips are drawn if their *center*
  projects on-screen, but their endpoints (±1000 world units) can be beside/
  behind the camera and mirror into the sky.
- **Solid black band** under the body: the continuous shadow is one big
  polygon (left edge points + reversed right edge points); when the path bends
  sharply the polygon self-intersects and fills the concave region solid.

## Scope
1. Water: draw each strip only if BOTH endpoints project validly (not the
   -999 sentinel) AND the strip stays below the horizon line on screen; split
   long strips into shorter spans so culling is per-span. No strip pixel may
   ever appear in the top quarter of the frame.
2. Shadow: draw the shadow as short per-sample quads (each sample's left/right
   edge pair to the next sample's), skipping any quad with an invalid
   projection — never one giant concave polygon. Same visual softness
   (`SHADOW_ALPHA`), no self-intersection possible.
3. Extend the checker turn script: also sample the bottom half for
   near-black (< 10 luma) regions wider than 5% of the frame directly under
   the body path — catches the black band. Must FAIL before, PASS after.

## Do NOT
- Do not redesign water visuals, sun, or sky. Only culling/splitting.
- Do not touch body rendering, tiles, camera.

## Files
`main.py` (water strips, continuous shadow), `dev/check_frames.py` (one check).

## Done when
- Checker (incl. new check + existing sky purity) exits 0; tests green.
- Mid-double-turn screenshot saved: no blue wedge anywhere, shadow is a soft
  band that follows the body with no solid black region.
