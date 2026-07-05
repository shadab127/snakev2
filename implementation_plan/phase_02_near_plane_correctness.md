# Phase 02 — Near-Plane Projection Correctness

Read `implementation_plan/README.md` first. Requires phase 01 (checker that can
see the bug).

**Goal:** Nothing behind or beside the camera ever draws garbage. This is the
root cause of "the whole game blows up when I turn".

## Verified Cause
`Camera.project()` returns normal-looking screen coordinates for points **behind
the camera** (negative-w mirror). Verified: a point directly behind the eye
projects to an on-screen coordinate instead of being rejected. Polygons whose
vertices straddle the near plane (water strips ±1000 units wide, tile faces,
snake body strips, ground) then rasterize as huge mirrored triangles during
camera swings.

## Scope
- `project()` must clearly signal "invalid — behind camera" (its callers must be
  able to tell, not receive plausible coordinates).
- Every polygon/line drawn from projected points must handle that signal:
  - all vertices invalid → skip the primitive;
  - some vertices invalid → skip or clip the primitive (either is acceptable if
    no garbage appears; document the choice per call site in the changelog).
  Audit every `project()` call site that feeds a polygon, line, or blit position
  — tiles, ground, water, snake strip/segments, apple, particles, shadows,
  minimap markers, god rays.
- Very wide primitives (the ±1000-unit water strips) must be split or bounded so
  a single primitive never spans from far-in-front to behind-the-camera.

## Out of Scope
- Camera motion feel (phase 04). Sky/sun/water redesign (phase 03) — here they
  only need to stop producing wedges. Snake looks (05).

## Files
`camera.py`, `main.py` (draw call sites), possibly `gl_renderer.py`

## Acceptance Criteria
- Checker turn-sequence and sky-purity checks PASS; `turn_worst.png` shows a
  clean sky (no wedges/bowtie/streaks).
- A behind-the-camera probe point is reported invalid, not on-screen (add this
  as a tiny checker assertion alongside the orientation probe).
- Steady-state visuals unchanged; FPS check still passes; tests green.
