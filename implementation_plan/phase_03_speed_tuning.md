# Phase 03 — Speed Tuning

Read `implementation_plan/README.md` first. Requires phase 02 (smooth motion
changes how speed feels — tune after, not before).

**Problem:** Starting speed is 6.7 cells/sec (`BASE_MOVE_INTERVAL = 0.15`).
Too fast to plan moves; the player asked for slower.

## Do
1. In `config.py` set:
   - `BASE_MOVE_INTERVAL = 0.35`  (≈2.9 cells/sec start)
   - `SPEED_DECAY_PER_POINT = 0.004`
   - `MIN_MOVE_INTERVAL = 0.12`   (≈8.3 cells/sec cap, reached ~score 60)
2. Nothing else. These three constants are the whole phase.
3. Add checker check `speed_sanity`: assert the three constants satisfy
   `BASE_MOVE_INTERVAL ≥ 0.3` and `MIN_MOVE_INTERVAL ≥ 0.1` (guards against a
   future agent "re-balancing" them back).

## Do NOT
- Do not change FIXED_DT, RENDER_FPS, camera speed constants, or any other
  config value.
- Do not add difficulty modes, settings entries, or new mechanics.

## Files
`config.py`, `dev/check_frames.py` (one check)

## Done when
- Constants set; `speed_sanity` PASSes; checker exit 0 except checks owned by
  later phases; tests green (update any test that asserts the old constant
  values — that is a legitimate test update).
