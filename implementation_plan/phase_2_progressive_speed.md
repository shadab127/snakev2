# Phase 2 — Progressive Speed

## Status
✅ **IMPLEMENTED** (all changes complete)

| Item | Location | Status |
|---|---|---|
| `BASE_MOVE_INTERVAL` | `config.py:16` | Done |
| `MIN_MOVE_INTERVAL` | `config.py:17` | Done |
| `SPEED_DECAY_PER_POINT` | `config.py:18` | Done |
| Dynamic interval in `update()` | `main.py:397` | Done |
| `move_timer` reset on eat | `main.py:338` | Done |

## Objective
Snake starts slow and accelerates as it eats apples, providing a gradual difficulty curve from 14 moves/sec up to 40 moves/sec.

## Implementation

### 1. Add constants to `config.py` (line 15-18)

```python
FPS = 30
BASE_MOVE_INTERVAL = 0.07
MIN_MOVE_INTERVAL = 0.025
SPEED_DECAY_PER_POINT = 0.0005
```

| Constant | Value | Effect |
|---|---|---|
| `BASE_MOVE_INTERVAL` | 0.07s | Initial speed at score 0 (~14 moves/sec) |
| `MIN_MOVE_INTERVAL` | 0.025s | Maximum speed cap (~40 moves/sec) |
| `SPEED_DECAY_PER_POINT` | 0.0005 | Interval decreases 0.5ms per point |

### 2. Replace interval calculation in `update()` (`main.py:396-398`)

Replace the fixed FPS interval with a dynamic one:

```python
# Before — fixed 30fps interval (no progressive speed)
self.move_timer += dt
interval = 1.0 / FPS  # was ~0.033s

# After — dynamic interval decaying with score
self.move_timer += dt
interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - self.score * SPEED_DECAY_PER_POINT)
```

### 3. Reset `move_timer` on eat (`main.py:338`)

When the snake eats an apple and the interval decreases, the old accumulated `move_timer` could cause an extra immediate move. Reset it:

```python
# In move_snake(), after scoring:
self.move_timer = 0
```

### 4. Reset interval on game restart (`main.py:298`)

In `reset()` the `move_timer` is set to 0, which resets the effective speed to base:

```python
# Already present in reset():
self.move_timer = 0
```

## Speed Curve Reference

```
Score     Interval    Moves/sec
   0      0.07000     14.3
  10      0.06500     15.4
  30      0.05500     18.2
  50      0.04500     22.2
  70      0.03500     28.6
  90      0.02500     40.0 (capped)
 100+     0.02500     40.0 (capped)
```

## Verification

| Test | Procedure | Expected |
|---|---|---|
| Initial speed | Start game, observe move rate | ~14 moves/sec (visible tick interval ~0.07s) |
| Speed increase | Eat 5+ apples | Noticeable acceleration after each apple |
| Speed cap | Eat until score ≥ 90 | Speed stops increasing; `interval` = 0.025s |
| No double-move on eat | Eat an apple, watch head position | Snake doesn't lurch forward 2 tiles on the eat frame |
| Reset on death | Die and restart | Speed resets to base |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Speed feels too fast/slow | Medium | Low (UX) | Tune `SPEED_DECAY_PER_POINT` and `BASE_MOVE_INTERVAL` in config |
| Double-move glitch on eat | Low | Medium | `move_timer = 0` in `move_snake()` on eat prevents this |
| Game becomes unplayable at high score | Low | Medium | `MIN_MOVE_INTERVAL` hard cap prevents infinite acceleration |

## Dependency Chain
- Phase 2 → Phase 3 (minimap draws current score) → Phase 4a
