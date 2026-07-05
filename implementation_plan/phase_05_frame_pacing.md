# Phase 05 — Frame Pacing on a Real Display

Read `implementation_plan/README.md` first. Requires phase 01 (interpolation
exists — pacing problems are visible only when motion is continuous).

**Problem:** Headless FPS measures 100+, yet play feels unsmooth. Remaining
causes to eliminate: no vsync on the window, uneven frame times (spikes), and
simulation/render beat interference from the accumulator loop.

## Scope
1. Create the window with vsync (`pygame.display.set_mode(..., vsync=1)` path;
   keep a config fallback if the platform refuses it).
2. Instrument frame-time variance: extend the perf overlay (F1) to show, over
   the last 120 frames, average / 95th percentile / max frame time. All
   measurement code already has hooks in `_perf_timings`.
3. Find and fix frame-time spikes over 25ms during normal play. Known
   suspects to verify (fix only confirmed ones, smallest change that works):
   - full tile-cache rebuild triggered by camera movement threshold — if it
     costs a visible spike, stagger it or rebuild incrementally;
   - per-frame Python allocation hotspots in the body/tile loops (reuse lists);
   - anything logged by the overlay as an outlier stage.
4. Add checker check `frame_pacing` (headless proxy): over 120 rendered
   frames, 95th-percentile frame time ≤ 1.5× median. Must PASS when done.

## Do NOT
- Do not change visuals at all. Screenshots before/after must be identical.
- Do not rewrite the game loop structure (fixed timestep stays).

## Files
`main.py`, `ui.py` (overlay lines), `config.py`, `dev/check_frames.py` (one check).

## Done when
- `frame_pacing` PASSes; full checker exits 0; tests green.
- On a real display (if available to you): 10 seconds of play with the overlay
  shows no frame over 25ms; note the numbers in the changelog entry. If no
  display is available, state that explicitly — phase 06 (human) covers it.
