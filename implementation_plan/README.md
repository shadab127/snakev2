# SnakeV2 — Rebuild Plan (v3)

Fresh plan. The two previous plans are deleted; their phases reported "done" while
the game stayed unplayable. Read this whole file before doing any phase.

## Why the previous plans failed (do not repeat this)

1. **Round 1** built 15 features and verified them with logic tests only. Nobody
   rendered a frame and looked at it. The game shipped upside-down at 4 FPS.
2. **Round 2** fixed camera orientation and speed, but nobody re-checked the
   *default-settings* frame. One full-screen overlay additively brightens every
   pixel, so the player sees a white screen. All 129 unit tests pass anyway.

Lesson: unit tests cannot see the screen, and "inspect the screenshot" is not a
reliable instruction. So this plan uses a **frame checker**: a script that measures
screenshots (brightness, color, FPS, orientation) and prints PASS or FAIL with a
proper exit code. A phase is done only when the checker passes.

## Current verified state (2026-07-04)

- Camera orientation: **correct** (up is up).
- FPS: ~45 with default settings, ~89 with effects off (target: 60).
- Default-settings frame: **near-white wash** — mean luma ~196, saturation ~1.
  Cause: a full-screen overlay is additively brightening every pixel each frame.
  With that overlay and the fog tint disabled, a correct dark scene appears.
- Effect toggles are saved to the player's save file, so old saves re-enable
  removed effects unless the save handling is also fixed (phase 02 covers this).
- The bare scene underneath is too dark, the snake renders as separated floating
  rings, and the apple is tiny — later phases fix these.
- `implementation_plan/reference_good_frame.png` shows the current bare scene:
  correct composition, wrong exposure. Use it as the composition reference.

## Rules (every phase, every agent)

1. Do exactly one phase per session, in numeric order. Read `AGENTS.md` first.
2. Run the checker (`python dev/check_frames.py`, built in phase 01) **before**
   your change (note the baseline) and **after** (must pass, or improve exactly
   as your phase specifies). If your change makes it worse, revert and stop.
3. Never edit, loosen, or skip the checker outside phase 01. Never mark a phase
   done with a failing checker.
4. The game must run with **pygame only**. ModernGL stays optional, never required.
5. Tunable values go in `config.py`, never hardcoded.
6. **Never add a full-screen additive overlay.** This bug class killed the game
   twice. Darkening overlays and per-object glows are fine; whole-screen additive
   brightening is banned.
7. Run `python -m pytest tests/ -q` — must stay green.
8. Update `CHANGELOG.md` with one line when done.
9. Stay in scope. Small diffs. Do not start the next phase.

## Phase index (strictly sequential)

| Phase | Title |
|---|---|
| 01 | Frame checker with pass/fail gates |
| 02 | Remove the white-out overlays; safe defaults |
| 03 | Scene exposure and sky |
| 04 | Snake body continuity |
| 05 | Head and apple readability |
| 06 | Camera framing |
| 07 | Per-tile depth fade |
| 08 | UI text contrast |
| 09 | Human playability sign-off |
