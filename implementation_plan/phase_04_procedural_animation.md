# Phase 04 — Procedural Animation & Squash-and-Stretch

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** Lifelike secondary motion so the snake and apple read as physical,
organic objects.

**Depends on:** Phase 03.

## Scope
- Eating: the head does a quick squash-stretch pulse, and a visible swallow bulge
  travels down the body to the tail.
- Apple: gentle idle bob and slow rotation; pop-in scale animation on spawn.
- Snake idle life: subtle breathing scale on the body, occasional eye blink, and a
  periodic tongue flick.
- Death: a short physical reaction (recoil/collapse) plays before the game-over
  screen appears.
- All effect strengths and durations tunable from `config.py`.

## Out of Scope
- Particle effects (phase 05).
- Camera reactions (phase 06).

## Likely Files
`main.py`, `config.py`, `game_state.py`

## Acceptance Criteria
- Each listed animation is visible in play and driven by elapsed time.
- Animations freeze correctly while paused and resume cleanly.
- Gameplay timing (movement interval, input response) is unchanged.
- Frame budget from `frame_budget.md` still holds.
