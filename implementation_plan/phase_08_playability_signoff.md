# Phase 08 — Human Playability Sign-Off

Read `implementation_plan/README.md` first. Requires phases 01–07 with the
checker exiting 0.

**Goal:** A human plays on a real display and confirms the two original
complaints are gone: turning no longer blows up the view, and the snake looks
like a snake.

## Scope
- Play a full session on a real display (`python main.py`): start → play → many
  rapid turns including double turns → eat 10+ apples → cross the torus edge in
  all directions → pause/resume → die → restart → quit.
- Specifically verify, fixing only small issues:
  - rapid turning at high speed (long snake) stays clean and comprehensible;
  - the snake reads as one creature at every length from 3 to 20+ segments;
  - sun/sky/water stay coherent through any sequence of turns;
  - steady ~60 FPS on the perf overlay throughout, including during turns;
  - input feels immediate; no crash or stuck state anywhere.
- Anything bigger than a small fix: write a new numbered phase file with
  verified symptoms instead of fixing it here (keep the plan honest).
- Final: checker exit 0, tests green, refresh root `README.md` screenshots with
  the fixed game, changelog entry "v4 sign-off: playable, turn-stable,
  recognizable snake — human verified".

## Out of Scope
- New features, refactors, balance redesign.

## Files
Small fixes where found; `CHANGELOG.md`, root `README.md`, possibly new phase files.

## Acceptance Criteria
- Full session completes; both original complaints confirmed fixed by a human.
- Checker exit 0 and tests green on the final commit.
