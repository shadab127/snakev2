# Phase 01 — Restore Deleted Tests, Checker, AGENTS.md

Read `implementation_plan/README.md` first.

**Problem:** Commit `c60377c` deleted the test suite, the frame checker, and
AGENTS.md. They exist intact at commit `62a4805`.

## Do
1. Run exactly:
   `git checkout 62a4805 -- tests/ dev/check_frames.py AGENTS.md`
2. Run `python -m pytest tests/ -q`. If any test fails because code was
   legitimately renamed/removed since `62a4805`, update THAT TEST minimally to
   match current code. Do not delete tests. Do not change game code.
3. Run `python dev/check_frames.py`. Same rule: minimal updates to the
   checker only where it references renamed code. Record its pass/fail table
   in the changelog entry (some checks may legitimately FAIL — later phases
   own fixing the game; do NOT "fix" a failing check by weakening it).
4. Append rule 1 from the plan README (never delete tests/dev/AGENTS.md/
   implementation_plan) to `AGENTS.md`.

## Do NOT
- Do not modify game code (`main.py`, `camera.py`, etc.) at all.
- Do not delete or skip any restored test or check.

## Files
`tests/`, `dev/check_frames.py`, `AGENTS.md`, `CHANGELOG.md`

## Done when
- Both commands run; tests green; checker runs end-to-end and prints its
  table (exit code may be non-zero — record which checks fail and why).
