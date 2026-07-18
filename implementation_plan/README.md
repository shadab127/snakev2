# SnakeV2 Small-Step Smooth World Plan v8

## Status

This is the active plan for future work. It breaks the three project goals into
small, independently testable phases. Superseded plan files are removed so
only one plan gives implementation instructions.

## Rules

1. Do one phase at a time. Do not combine later work into an earlier patch.
2. Before and after every phase, run `python -m pytest tests/ -q` and
   `python dev/check_frames.py`.
3. Measure the phase's stated scenario before changing it, then record the
   result after the change.
4. Keep gameplay state canonical. Presentation-only state must not alter score,
   food, collision, persistence, or controls.
5. Put new tuning values in `config.py` and add a focused regression test.
6. Keep UI readable and upright at all times, including world flips.

## Ordered Phases

| Phase | Small Deliverable |
| --- | --- |
| 01 | Accurate frame-time instrumentation |
| 02 | Stable frame pacing and bounded catch-up |
| 03 | Reuse sky, water, and UI render surfaces |
| 04 | Precompute and stabilize terrain caching |
| 05 | Bound snake, shadow, and particle render work |
| 06 | Make renderer selection and quality presets explicit |
| 07 | Capture a durable visual regression baseline |
| 08 | Improve tile, horizon, water, and vegetation materials |
| 09 | Improve snake head, body, and silhouette |
| 10 | Unify lighting, shadows, food, and particles |
| 11 | Define one periodic board topology |
| 12 | Add continuous unwrapped visual movement |
| 13 | Render periodic terrain and world objects |
| 14 | Add the dive and 180-degree world-flip state machine |
| 15 | Add true under-seam occlusion and transition effects |
| 16 | Run the full wrap, performance, and visual sign-off matrix |

## Completion

The plan is complete only after Phase 16 passes on the software renderer and,
when available, the GL renderer. Manual testing must cover long snakes, all six
directions, corner wraps, food pickup, pause, death, restart, and repeated
world flips on a real display.
