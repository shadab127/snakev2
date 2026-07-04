# Phase 08 — UI Text Contrast

Read `implementation_plan/README.md` first. Requires phase 03 (final scene
exposure to contrast against).

**Goal:** Every piece of text and UI in the game is comfortably readable over the
actual scene behind it.

## Scope
- Start screen: title drawn once (it currently double-draws as two offset copies),
  menu items clearly readable in both selected and unselected states, hint line
  at the bottom legible.
- Settings screen: labels, values, and the selected row obvious at a glance.
- HUD: score panel, best score, and minimap readable over the brightest part of
  the scene; minimap keeps a contrasting border and background.
- Pause and game-over screens: dim/blur the scene behind them enough that their
  text passes contrast, without whiting or blacking the frame out (checker states
  must stay in range).
- Where text sits over variable scene content, give it a local backing (panel,
  shadow, or outline) — never a full-screen brightness change (rule 6).
- Add a simple checker text-contrast check: sample the pixel rows behind known
  text anchors on each screen and assert a minimum luma difference between text
  color and its local background (document anchors in `checks.md`).

## Out of Scope
- New menus or settings entries. Redesigning layout beyond fixing readability.

## Files
`ui.py`, `main.py` (start-screen title), `config.py`, `dev/check_frames.py`

## Acceptance Criteria
- Committed screenshots of all five screens; every string readable in each.
- The title renders exactly once.
- Checker (including the new contrast check) passes; test suite green.
