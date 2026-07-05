# Phase 04 — Camera Turn Motion

Read `implementation_plan/README.md` first. Requires phase 02 (turns no longer
draw garbage).

**Goal:** Turning feels smooth and comprehensible — the player never loses track
of where they're heading, even on rapid double turns (120° direction changes).

## Verified Problems
- On a hex grid a single turn is a 60° heading change and a double turn is 120°;
  the camera swings that entire arc in a handful of frames — disorienting even
  without the (now fixed) rendering garbage.
- Camera roll ("banking") is applied as a screen-space rotation on top of the
  swing, adding to the chaos on quick successive turns.

## Scope
- The camera's heading must rotate smoothly **around the snake's head** along
  the shortest arc, with an angular speed cap (tunable in `config.py`) so a
  120° change takes a readable amount of time (~0.4–0.7s) instead of snapping.
- Successive quick turns compose: target heading updates mid-swing without
  jerk or overshoot flip-flop.
- Banking stays subtle: cap total roll, and roll must decay to zero within ~1s
  after the last turn. If banking still muddies readability, set its default
  intensity to 0 in config and say so in the changelog.
- The head must remain inside its checker framing band during the entire swing
  (the world pivots around the snake, the snake doesn't fly around the screen).
- Extend the checker turn-sequence check: head stays in band on every captured
  turn frame; consecutive-frame yaw change stays under a max-degrees-per-frame
  threshold at 60 FPS.

## Out of Scope
- Sky/sun (03). Snake visuals (05–06). Event punch-ins (already exist).

## Files
`camera.py`, `config.py`, `dev/check_frames.py` (turn-frame assertions above)

## Acceptance Criteria
- Checker (with new assertions) passes apart from phase-07's luma reds.
- Committed frame sequence of a double turn: sky and grid rotate smoothly, head
  stays in the framing band, no snap between any two consecutive frames.
- Tests green.
