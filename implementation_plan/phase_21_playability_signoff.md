# Phase 21 — Playability Sign-Off (Recovery)

Before starting: read `AGENTS.md` and `implementation_plan/README.md` (Recovery
section). This is the gate that declares the game recovered.

**Goal:** A human can sit down, play a full session, and everything works and feels
right. This phase is mostly verification and small fixes, not construction.

**Depends on:** Phases 16–20.

## Scope
- Full manual playthrough of `qa_checklist.md` on a real display (not headless):
  title → settings → play → eat 10+ apples → pause/resume → die → game over →
  restart → quit. Fix every failure found; re-run until clean.
- Feel checks that headless tests can't catch, fixing what fails:
  - input latency: a turn keypress takes effect on the next movement step;
  - readability: snake, apple, and upcoming tiles clearly distinguishable at speed;
  - camera: no nausea-inducing swings, wrap-around crossing is smooth (per phase 06);
  - difficulty: starting speed is comfortable, ramp is noticeable but fair;
  - audio matches events with no crackle (per phase 11).
- Confirm menu text/contrast issues seen in the broken build are gone (start-screen
  title double-draw, dim unreadable menu items over the scene).
- Verify the packaged/entry-point launches (`python main.py`, console command, and
  the phase-15 flags) all reach the playable game.
- Update `qa_checklist.md` with any new checks this recovery revealed; final
  `CHANGELOG.md` entry; refresh `README.md` screenshots with the fixed game.

## Out of Scope
- New features or balance redesign beyond the tuning above.

## Likely Files
Small fixes wherever the playthrough finds them; `qa_checklist.md`, `CHANGELOG.md`, `README.md`

## Acceptance Criteria
- Every `qa_checklist.md` item passes on a real display.
- Harness screenshots + FPS attached/committed as the "after" baseline.
- The one-line answer to "is it fun to play for five minutes?" is yes, from an
  actual human playtest, with any showstopper they report fixed.
