# Phase 06 — Human Sign-Off

Read `implementation_plan/README.md` first. Requires phases 01–05, checker
exit 0.

**Goal:** A human confirms the three original complaints are gone:
1. motion is smooth (no per-cell teleporting, no stutter);
2. the snake looks like one correctly-sized creature, on top of the terrain;
3. the terrain reads as one surface, not separate blocks holding the snake.

## Scope
- Play on a real display: start → play → 10+ apples → rapid double turns →
  torus wrap in all directions → pause/resume → die → restart → quit.
- Watch the F1 overlay while playing: steady 60 with no spikes over 25ms.
- Fix only small issues found. Anything structural: write a new numbered phase
  file with a symptom screenshot instead of fixing it here.
- Refresh root `README.md` screenshots. Changelog entry:
  "v5 sign-off: smooth motion, correct body, unified terrain — human verified".

## Done when
- The three complaints above are confirmed fixed by a human playing the game.
- Checker exit 0 and tests green on the final commit.
