# SnakeV2 — Production Upgrade Plan

Transform SnakeV2 from a demo into a production-quality 3D snake game with realistic
motion physics, cinematic graphics, full audio, and release packaging.

## How to use this folder

Each `phase_NN_*.md` is one self-contained unit of work, sized to be completed in a
single session by one agent. Implement phases in numeric order unless the dependency
notes say otherwise.

## Rules for every phase (read before starting any phase)

1. Read `AGENTS.md` at the repo root first — it explains the module layout.
2. The game must always run with **pygame only** (software fallback). ModernGL is optional;
   never make it required.
3. All new tunable values go in `config.py`, never hardcoded inline.
4. Do not exceed the frame budget: steady 60 FPS during normal play.
5. Update `CHANGELOG.md` with a short entry when the phase is done.
6. Verify by running `python main.py` and playing; check every acceptance criterion.
7. Stay inside the phase's scope. Do not start the next phase.

## Phase index

| Phase | Title | Track |
|---|---|---|
| 01 | Fixed timestep & frame-rate independence | Foundation |
| 02 | Performance foundation | Foundation |
| 03 | Continuous snake motion (spline body) | Physics |
| 04 | Procedural animation & squash-and-stretch | Physics |
| 05 | Particle physics upgrade | Physics |
| 06 | Camera dynamics | Physics |
| 07 | Unified lighting model | Graphics |
| 08 | Shadows & ambient occlusion | Graphics |
| 09 | Post-processing stack | Graphics |
| 10 | Atmosphere & environment | Graphics |
| 11 | Audio system | Production |
| 12 | Menus, settings & HUD polish | Production |
| 13 | Persistence | Production |
| 14 | Test harness & QA | Production |
| 15 | Packaging & release | Production |

## Dependencies

- Phases 01 → 02 are prerequisites for everything else.
- Physics track (03 → 04 → 05 → 06) and Graphics track (07 → 08 → 09 → 10) are
  independent of each other and may be done in parallel by different agents.
- Production track (11–15) requires 01–02; phase 12 benefits from 09; 14 and 15 go last.
