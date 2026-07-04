# Phase 14 — Test Harness & QA

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** Confidence the game is correct and stays correct: automated tests for the
logic, a headless soak test for stability, and a documented manual QA pass.

**Depends on:** All previous phases (run this near the end).

## Scope
- Set up `pytest` with a `tests/` folder (currently no test infrastructure exists).
- Unit tests for pure logic: hex math and wrapping, spline/path sampling, speed
  curve, collision rules, camera math (projection of known points), persistence
  round-trip and corruption handling, particle physics stepping.
- Headless simulation test: drive the game loop without a display (dummy video
  driver) with scripted/random inputs for thousands of steps — asserts no crash and
  no logic invariant violations (snake length matches score, positions always on
  valid tiles, etc.). Refactor only as needed to make the sim drivable headless.
- Fix every bug these tests surface (expect several — wrapping and state-machine
  edges are likely candidates).
- Write `implementation_plan/qa_checklist.md`: a manual test script covering every
  feature from phases 01–13, and run through it once, fixing what fails.
- Document how to run tests in `AGENTS.md`.

## Out of Scope
- Visual regression tooling, CI pipelines.

## Likely Files
New `tests/`, small refactors across modules for testability, `AGENTS.md`

## Acceptance Criteria
- `pytest` passes; suite covers every logic area listed above.
- Headless soak run of at least 10,000 simulation steps completes clean.
- QA checklist exists and every item is checked off.
