# Phase 11 - Periodic Board Topology

Requires: Phase 10.

## Goal

Give movement, terrain, and food one shared toroidal board definition.

## Do

1. Define the canonical 15 by 15 axial parallelogram that matches
   `wrap_coords()` exactly.
2. Add a pure helper that returns a wrapped coordinate and its whole-board
   period delta from a raw coordinate.
3. Migrate tile generation, apple placement, AO, grass, and neighbor lookup to
   the same canonical-cell set.
4. Key terrain noise and materials by canonical cell so periodic copies match.
5. Test all six edges and simultaneous q/r corner wrapping.

## Files

`utils.py`, `resources.py`, `main.py`, `tests/test_utils.py`, and focused tests.

## Done When

Every reachable gameplay coordinate has terrain, food placement, and periodic
neighbor data; all edge and corner period-delta tests pass.

## Do Not

- Do not add a flip animation yet.
- Do not retain mixed `all_hexes()` and `in_bounds()` board assumptions.
