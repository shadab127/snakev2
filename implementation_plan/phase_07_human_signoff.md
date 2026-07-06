# Phase 07 — Human Sign-Off

Read `implementation_plan/README.md` first. Requires phases 01–06, checker
exit 0, tests green.

**Goal:** A human confirms the four v6 complaints are gone:
1. motion is smooth — no snap, no stutter, at start speed and after 20 apples;
2. the snake reads as one tube, not a chain of spheres;
3. starting speed is comfortable (~3 cells/sec) and ramps gently;
4. the shadow is soft and the world has no stripes/black-edge artifacts.

## Do
- Play on a real display: start → play → 10+ apples → rapid double turns →
  torus wrap all directions → pause/resume → die → restart → quit.
- Fix only small issues. Anything structural: new numbered phase file with a
  symptom screenshot, not a fix.
- Refresh root `README.md` screenshots. Changelog entry:
  "v6 sign-off: smooth, tube body, sane speed, soft shadow — human verified".

## Done when
- All four complaints confirmed fixed by a human playing the game.
- Checker exit 0, tests green on the final commit.
