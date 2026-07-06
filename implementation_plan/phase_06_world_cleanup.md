# Phase 06 — World Cleanup: Water Stripes, Tile Edges, Horizon

Read `implementation_plan/README.md` first. Requires phase 02.

**Problem (see `symptom_turn.png`):** Three things make the world look bad:
- Blue striped water polygons leak ABOVE the horizon mid-turn (top-right of
  the symptom screenshot) — strip endpoint culling is still incomplete.
- Tile edges are thick dark bevel bands: every hex is outlined in near-black,
  which reads as a cartoon grid, and at the island rim they stack into black
  steps.
- The horizon is a hard line between the tile field and the sky gradient;
  distant tiles get no atmospheric fade, so the island edge looks pasted on.

## Do
1. Water: compute the horizon screen height each frame (project a far point
   at ground level); clip every water strip's screen polygon to below that
   line, in addition to the endpoint validity check. No water pixel above the
   horizon, at any camera heading, ever.
2. Tile edges: replace the near-black edge color with a color only ~20% darker
   than the tile top; reduce edge thickness to 1–2 px equivalent. Keep the
   hex pattern visible but subtle (`TILE_EDGE_*` tunables in `config.py`).
3. Depth fade: blend each tile's final color toward the sky horizon color by
   a factor of its camera distance (0 near, up to ~0.5 at the far rim),
   tunable in `config.py`. This is a per-tile color blend at draw time — NOT
   a full-screen overlay (banned).
4. Extend the checker sky-purity check to also scan the horizontal band ±5%
   around the computed horizon for blue-stripe colors during the turn script.
   Must FAIL before (stripes present), PASS after.

## Do NOT
- Do not touch snake, shadow, head, apple, speed, camera motion.
- Do not add new effects beyond the depth fade described.
- Do not change the sky gradient itself.

## Files
`main.py` (water clip, tile edge color, depth fade), `config.py`,
`dev/check_frames.py` (extend one check)

## Done when
- Extended sky-purity check PASSes; checker exit 0 except later-phase checks;
  tests green; FPS unchanged.
- Screenshots straight + mid-double-turn saved: no stripes anywhere, subtle
  hex edges, far tiles fading gently into the sky. Visibly better than
  `symptom_turn.png`.
