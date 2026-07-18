# Phase 02 - Frame Pacing

Requires: Phase 01.

## Goal

Prevent a slow frame from causing a visible simulation catch-up spiral.

## Do

1. Select exactly one pacing authority per backend: working display vsync or a
   software frame cap.
2. Clamp pathological elapsed time and cap fixed-update catch-up work per
   rendered frame while retaining a bounded accumulator remainder.
3. Cache camera roll sine/cosine once per camera update rather than per point
   projected during a frame.
4. Add tests for a deliberately injected long frame and checker output for its
   recovery time.

## Files

`main.py`, `camera.py`, `config.py`, `dev/check_frames.py`, and camera tests.

## Done When

A synthetic slow frame recovers without an unbounded update loop, normal snake
movement remains deterministic, and only one limiter is active for each path.

## Do Not

- Do not lower snake speed or simulation frequency to hide stutter.
- Do not change collision timing.
