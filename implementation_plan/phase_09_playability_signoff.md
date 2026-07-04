# Phase 09 — Human Playability Sign-Off

Read `implementation_plan/README.md` first. Requires phases 01–08 all done with
the checker passing.

**Goal:** A human plays the game on a real display and confirms it's actually
good. This phase is verification plus small fixes only.

## Scope
- Run `python main.py` on a real display (not headless) and play a full session:
  start → settings (change something, confirm it applies) → play → eat 10+
  apples → cross a torus edge → pause/resume → die → game over → restart → quit.
- Check and fix small issues found in:
  - input: every keypress registers; a turn takes effect on the next move step;
  - speed ramp: start comfortable, gets faster per apple, never impossible;
  - audio: events have sounds, nothing crackles, mute works;
  - FPS: perf overlay steady at ~60 on the software path while playing;
  - state flow: no crash or stuck state anywhere in the loop above.
- If anything found requires more than a small fix, do NOT fix it here — add a
  new numbered phase file describing symptoms (like the phase files before this
  one) and note it in the changelog. The plan stays honest.
- Final pass: `python dev/check_frames.py` and `python -m pytest tests/ -q` both
  clean; update `README.md` (repo root) screenshots; changelog entry
  "playable — signed off by human playtest".

## Out of Scope
- New features, big refactors, balance redesign.

## Files
Small fixes where found; `CHANGELOG.md`, root `README.md`, possibly new phase files.

## Acceptance Criteria
- The full session above completes with zero crashes and no showstopper.
- A human states the game is playable and fun for at least five minutes.
- Checker and tests pass on the final commit.
