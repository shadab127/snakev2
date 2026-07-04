# Phase 13 — Persistence

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** The game remembers the player between sessions — scores, settings, and
basic stats — robustly.

**Depends on:** Phase 12.

## Scope
- Save file in the platform-appropriate user data directory (not the repo folder),
  human-readable format (JSON), single small module owning all load/save.
- Persist: high score + top-5 scores with dates, all settings from phase 12, and
  lifetime stats (games played, apples eaten, total play time, longest snake).
- Load on startup with full validation: missing file, corrupt file, unknown fields,
  and older versions must all result in safe defaults, never a crash. Include a
  schema version field for future migration.
- Save on: settings change, game over, and clean quit. Writes must be atomic
  (write temp file, then rename) so a crash mid-write can't corrupt the save.
- Show the persisted data where relevant: best score on title and game-over screens,
  stats visible somewhere sensible (e.g. a stats line or subscreen).

## Out of Scope
- Cloud sync, multiple profiles, replays.

## Likely Files
New `persistence.py`, `main.py`, `ui.py`, `config.py`

## Acceptance Criteria
- Set a high score, change settings, quit, relaunch: everything is remembered.
- Manually corrupting the save file (truncate it) → game launches with defaults and
  overwrites cleanly, no crash.
- Save file never appears inside the repo working tree.
- Kill the process during play → next launch is still consistent.
