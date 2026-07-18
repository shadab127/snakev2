# Phase 01 - Frame Instrumentation

Requires: none.

## Goal

Measure the complete frame honestly before optimizing it.

## Do

1. Time background, terrain cache build/hit, snake, particles, post-effects,
   UI, and final display presentation separately.
2. Replace the growing frame-time list with a fixed-size `collections.deque`.
3. Show p50, p95, p99, worst frame, backend, resolution, and active quality
   settings in the debug overlay.
4. Add a checker benchmark for warm idle rendering and normal moving gameplay.

## Files

`main.py`, `ui.py`, `dev/check_frames.py`, and focused tests.

## Done When

The checker prints per-scenario percentiles that include `flip` or `update`,
and the in-game debug overlay reports the same data without allocations that
grow over time.

## Do Not

- Do not alter rendering behavior or frame limits in this phase.
- Do not use one warm, idle render loop as the only benchmark.
