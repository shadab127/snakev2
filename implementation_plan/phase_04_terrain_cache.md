# Phase 04 - Terrain Cache Work

Requires: Phase 03.

## Goal

Make terrain cache rebuilds rare, bounded, and based on precomputed data.

## Do

1. Precompute tile corner heights, neighbor relationships, and static grass
   inputs in `ResourceManager`.
2. Remove repeated full height-map reconstruction from tile and decoration
   drawing.
3. Separate static terrain rasterization from dynamic effects such as eat
   flashes and snake interaction.
4. Define explicit cache invalidation reasons and record cache hit/build timing.
5. Add cold-cache and moving-camera checker scenarios.

## Files

`resources.py`, `main.py`, `utils.py`, `dev/check_frames.py`, and tests.

## Done When

Terrain rebuilds use only precomputed static data, dynamic events do not rebuild
unrelated tiles, and cold/warm cache timings are both reported and bounded.

## Do Not

- Do not change the board topology yet.
- Do not remove terrain detail merely to avoid a cache rebuild.
