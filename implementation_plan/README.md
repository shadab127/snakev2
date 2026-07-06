# SnakeV2 — Fix Plan v6

Read this file fully. Do ONLY your assigned phase. Screenshots of today's build:
`symptom_straight.png`, `symptom_turn.png`.

## Verified problems (2026-07-06)

1. **The last agent deleted the guardrails.** Commit `c60377c` ("Simplify
   codebase") deleted `tests/`, `dev/check_frames.py`, `AGENTS.md`, and the
   implementation plan. Phase 01 restores them. THIS MUST NEVER HAPPEN AGAIN —
   see rule 1.
2. **Body snaps forward every move step.** Measured per-frame body movement:
   ~0.4 world-units for 8 frames, then a 52.5-unit jump (one full cell) at the
   step. Cause: the high-res body spline lerps between ADJACENT high-res
   samples (1/10 cell apart) instead of advancing one full cell per step. The
   head/camera (low-res spline, 1 cell spacing) move smoothly — the body
   visibly snaps ~7×/second. This is the remaining "not smooth".
3. **Snake reads as a chain of green spheres.** The body is still drawn as
   overlapping sphere sprites (`generate_sphere_sprite`, ring pattern +
   specular dot per sample). v5 required flat cross-section shading; the agent
   kept the sphere sprites.
4. **Snake is too fast.** `BASE_MOVE_INTERVAL = 0.15` → 6.7 cells/sec at
   score 0. Way too fast for a starting speed.
5. **Shadow looks cheap.** Per-sample dark quads overlap → double-darkened
   patches and a square blotch behind the head.
6. **World blemishes:** blue water stripes still leak into the sky mid-turn
   (see `symptom_turn.png` top-right); tile edges are thick dark bevel bands
   that read as black outlines.

## Rules — follow exactly

1. NEVER delete or rewrite `tests/`, `dev/`, `AGENTS.md`, or
   `implementation_plan/`. No "cleanup" or "simplification" commits. If a file
   seems dead, note it in the changelog — do not delete it.
2. Do ONLY what your phase lists under **Do**. Touch ONLY the files under
   **Files**.
3. Before starting and before declaring done, run:
   `python dev/check_frames.py` (exit 0 required at done) and
   `python -m pytest tests/ -q` (green required). Use `.venv/bin/python` if
   `python` lacks pygame.
4. Never loosen or delete a checker check. Add only what your phase says.
5. New checks must FAIL on the pre-fix build and PASS after — prove it by
   running the checker before your code change.
6. Look at the screenshots your phase says to save; if they don't match the
   Done description, you are not done.
7. Tunables in `config.py`. One short `CHANGELOG.md` entry. Small diffs.

## Phases (strict order)

| Phase | Fixes |
|---|---|
| 01 | restore deleted tests/checker/AGENTS.md |
| 02 | body snap → truly smooth motion (#2) |
| 03 | speed tuning (#4) |
| 04 | body look: tube, not spheres (#3) |
| 05 | soft shadow (#5) |
| 06 | world cleanup: water stripes, tile edges, horizon (#6) |
| 07 | human sign-off |
