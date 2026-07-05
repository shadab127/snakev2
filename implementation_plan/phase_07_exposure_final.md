# Phase 07 — Exposure: Clear the Last Checker Reds

Read `implementation_plan/README.md` first. Requires phases 03 and 05 (final
backdrop and body to expose against).

**Goal:** Every checker luma check green. Two are red right now and were left
red by the previous plan: gameplay mean luma 29.9 (window 40–110) and game-over
mean luma 7.9 (window 8–140).

## Scope
- Gameplay: raise the scene into the 40–110 luma window by brightening existing
  `config.py` palette values (tiles, sky band, water) and, if needed, the
  ambient light level. No new render passes, no overlays (rule 5).
- Verify across the full day cycle: the darkest cycle point must stay ≥ 40 mean
  luma, the brightest ≤ 110 (run the checker at multiple `--time` points; add
  that option if the checker lacks it — additive change only).
- Game-over screen: its dimming overlay currently crushes the frame to
  luma 7.9. Lighten the dim so the scene remains visible behind the panel while
  the panel text keeps its contrast check green.
- Hex relief must survive the brightening: top faces clearly lighter than side
  faces (spot-check screenshots; don't flatten the depth cue).
- Re-check every state's screenshots at the end — this phase owns making the
  **entire checker exit 0** for the first time. That includes anything a
  previous phase left red.

## Out of Scope
- New effects or passes. Geometry. Gameplay.

## Files
`config.py`, `ui.py` (game-over dim), `dev/check_frames.py` (only `--time` if missing)

## Acceptance Criteria
- `python dev/check_frames.py` exits 0 — every check green, at every tested
  day-cycle time.
- Committed before/after screenshots for gameplay and game-over.
- Tests green.
