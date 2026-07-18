# Phase 05 - Dynamic Render Work

Requires: Phase 04.

## Goal

Keep long snakes and particle bursts from creating frame-time spikes.

## Do

1. Cache spline topology between movement steps while preserving existing smooth
   interpolation.
2. Remove snake draw work that does not produce visible pixels.
3. Reuse a bounded shadow scratch surface instead of allocating one per frame.
4. Enforce `MAX_PARTICLES` as a hard cap and avoid unnecessary particle sorting
   or smoothscaling.
5. Benchmark a long snake and maximum particle burst using Phase 01 metrics.

## Files

`main.py`, `particle.py`, `config.py`, `dev/check_frames.py`, and tests.

## Done When

The long-snake and particle scenarios have no repeatable spike above the Phase
01 budget, and body motion, shadow shape, and particle behavior remain correct.

## Do Not

- Do not reduce snake length, remove the body strip, or disable particles.
- Do not regress eat or death animations.
