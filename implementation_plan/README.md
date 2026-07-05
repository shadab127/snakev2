# SnakeV2 — Visual & World-Physics Fix Plan (v4)

Previous plan (v3) built the frame checker and got the scene visible, but the game
is still bad to play. This plan fixes what a real play session shows today.

## Verified problems (2026-07-05, screenshots in this folder)

1. **Turning blows the view apart.** `symptom_turn_blowup.png`: during a turn,
   huge dark wedges and a tan "bowtie" tear across the sky, blue streaks smear the
   left edge. Proven cause: the projection function does not reject points
   **behind the camera** — they come back as valid-looking screen coordinates
   (mirrored). Any polygon with one vertex behind the camera (water bands, tile
   faces, body strips) draws as a giant garbage triangle. It only happens while
   the camera swings, which is why steady screenshots pass.
2. **The snake is not recognizable.** `symptom_straight.png`: the body is a flat,
   unshaded light-green 2D ribbon painted on the tiles with an oversized glossy
   sphere as the head. A "rectangular block with a dumb sphere" — accurate.
   (A commit on 2026-07-05 made the ribbon bend smoothly and removed the extra
   ball sprites; it is still a flat ribbon, not a body.)
3. **Sky/sun/water are not world-anchored.** The sun disc is blitted at a fixed
   screen position and the water is a stack of screen-projected strips, so when
   the camera yaws they swing or stay put incoherently.
4. **Checker gaps let all this through.** The checker only screenshots steady
   moments — never mid-turn — and two of its checks are failing right now
   (gameplay luma 29.9 vs 40–110, game-over luma 7.9 vs ≥ 8) yet phases were
   marked done anyway.

## Rules (every phase, every agent — no exceptions)

1. One phase per session, in numeric order. Read `AGENTS.md` first.
2. Run `python dev/check_frames.py` before and after your change.
   **If the checker exits non-zero after your change, the phase is NOT done** —
   fix it or revert. "Most checks pass" does not exist; the exit code decides.
   (The two luma FAILs above are pre-existing; phases state when they must turn
   green. Never introduce a new FAIL.)
3. Never loosen a checker threshold or delete a check. Adding checks is allowed
   only where a phase says so.
4. pygame-only must work; ModernGL stays optional.
5. Tunables in `config.py`. No full-screen additive overlays (this killed the
   game twice).
6. `python -m pytest tests/ -q` stays green. One-line `CHANGELOG.md` entry per phase.
7. Small diffs. Stay in scope. Do not start the next phase.

## Phase index (strictly sequential)

| Phase | Title | Fixes |
|---|---|---|
| 01 | Checker: turn-sequence capture | the escape route |
| 02 | Near-plane projection correctness | turn blow-up (root) |
| 03 | Sky, sun, water world-anchoring | incoherent backdrop |
| 04 | Camera turn motion | disorienting swing |
| 05 | Snake body: rounded shaded tube | "block + sphere" snake |
| 06 | Snake grounding & motion feel | floating/physics feel |
| 07 | Exposure: clear the last checker reds | dark scene, dark game-over |
| 08 | Human playability sign-off | final gate |
