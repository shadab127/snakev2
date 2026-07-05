# Phase 04 — Terrain Reads as One Surface

Read `implementation_plan/README.md` first. Requires phase 02 (body size is
final before terrain contrast is tuned).

**Problem:** Every hex tile is drawn as a separate extruded prism: dark side
faces appear between neighboring tiles in every direction, so the ground looks
like loose blocks and the snake appears to run in grooves between them
("hexagonal blocks holding the snake body" — see both symptom screenshots).

## Scope
1. Interior tile side faces must not be visible: side faces are drawn only on
   the outer rim of the island (tiles with a missing neighbor on that side).
   Between two adjacent tiles there must be zero dark gap — their tops meet.
2. Keep the hex pattern readable on the surface itself: a subtle edge line or
   the existing per-tile color variation on the tops (tunable in `config.py`),
   NOT 3D grooves.
3. The island rim keeps its extruded look (side faces + underside) so the
   floating-island silhouette is preserved.
4. Re-check tile draw order after the change: no missing/overlapping triangles
   at any camera heading (run the checker turn script and look).
5. Add checker check `terrain_gaps`: in the bottom-center region of a gameplay
   frame, measure the fraction of near-black pixels (< 12 luma) — with grooves
   gone it must drop below 2%. Must FAIL before, PASS after (measure first; if
   today's value is under 2%, tighten the threshold to today's value − 5pts and
   note it in `checks.md`).

## Do NOT
- Do not change tile top colors/palette beyond the edge-line tunable.
- Do not touch snake, water, sky, camera, or the GL path beyond keeping it
  compiling/consistent (if the GL tile shader draws side faces, apply the same
  neighbor rule there).

## Files
`main.py` (software tile draw), `gl_renderer.py` (same rule), `utils.py` (a
neighbor-lookup helper if needed), `config.py`, `dev/check_frames.py` (one check).

## Done when
- `terrain_gaps` PASSes; full checker exits 0; tests green.
- Gameplay screenshot saved: continuous green surface with a visible hex
  pattern, dark edges only at the island rim; snake clearly on top of the
  surface, not between blocks.
