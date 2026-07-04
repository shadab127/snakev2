# Phase 12 — Menus, Settings & HUD Polish

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** A complete, animated front-end: title screen, settings, pause menu, and a
polished in-game HUD that feel like one designed product.

**Depends on:** Phases 01, 09 (for menu backdrop effects), 11 (for audio settings).

## Scope
- Title screen: animated backdrop (live game scene idling under the camera's
  breathing drift), logo treatment, and a small menu (Play, Settings, Quit) with
  keyboard navigation and hover/selection feedback.
- Settings screen: audio volumes, post-processing toggles, FPS display toggle,
  control display. Changes apply live.
- Pause menu: resume / restart / settings / quit, over a blurred-or-dimmed frozen scene.
- Game over: animated score count-up, best-score callout ("new record!"), quick
  restart. No instant jarring cut from gameplay — sequence in after the phase-04
  death animation.
- HUD: score with pop animation on change, current speed indicator, and the minimap —
  restyled to match one visual language (spacing, font sizes, panel styling).
- All screens navigable by keyboard alone; every transition animated (fade/slide),
  nothing pops.

## Out of Scope
- Persistence of settings/scores (phase 13 — but structure values so they're easy to
  persist).
- New gameplay modes.

## Likely Files
`ui.py`, `main.py`, `game_state.py`, `config.py`, `resources.py`

## Acceptance Criteria
- Full flow works: title → settings → play → pause → settings → resume → death →
  game over → restart, all via keyboard.
- Every settings change takes effect immediately and audibly/visibly.
- No screen transition is an instant cut.
- HUD elements share consistent styling and never overlap each other.
