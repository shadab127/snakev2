# Phase 3 — Mini-Map

## Status
✅ **IMPLEMENTED** (all changes complete)

| Item | Location | Status |
|---|---|---|
| `MINIMAP_SIZE`, `PADDING`, `ALPHA` | `config.py:95-97` | Done |
| `draw_minimap()` function | `ui.py:161-206` | Done |
| Call in `render()` | `main.py:989` | Done |

## Objective
Small top-down hex map at top-left that provides spatial awareness: snake body, apple position, and grid outline in a compact minimap.

## Implementation

### 1. Add constants to `config.py` (lines 95-97)

```python
MINIMAP_SIZE = 140
MINIMAP_PADDING = 10
MINIMAP_ALPHA = 180
```

### 2. Implement `draw_minimap()` in `ui.py:161-206`

**Function signature:**
```python
def draw_minimap(surf, snake, apple, game):
```

**Algorithm:**

```
1. Create 140×140 SRCALPHA surface
2. Fill with (0, 0, 0, 180) for semi-transparent dark background
3. Get all hexes via all_hexes()
4. Convert each to pixel coords, compute bounding box
5. Scale to fit inside MINIMAP_SIZE - 2*margin with 0.9 padding factor
6. For each hex:
   - If (q,r) == apple:       draw red   dot (radius 4, color 255,60,60)
   - If (q,r) in snake_set:   draw green dot (radius 3, color 80,255,120)
   - Otherwise:               draw muted  dot (radius 2, color 60,120,90)
7. Blit to corner at (MINIMAP_PADDING, MINIMAP_PADDING)
```

**Important details:**
- Uses `hex_to_pixel()` directly — no camera projection (top-down view)
- Draw order: empty tiles first, then snake, then apple (always visible on top)
- Semi-transparent `Surface.blit()` renders on top of the game scene

### 3. Call `draw_minimap()` in `render()` (`main.py:989`)

Placed **after** `draw_game_over()` / `draw_pause_overlay()` but **before** `vignette_surf`:

```python
# main.py:989 — within render(), just before vignette
draw_minimap(surf, self.snake, self.apple, self)
surf.blit(self.vignette_surf, (0, 0))  # vignette on top of everything
```

This positioning ensures:
- Minimap is visible during pause (not obscured by pause overlay)
- Minimap is visible during game over (not obscured by game-over overlay)
- Vignette darkens the minimap slightly (intentional — keeps focus on center)

## Verification

| Test | Procedure | Expected |
|---|---|---|
| Minimap visible | Start game, check top-left | 140×140 semi-transparent grid appears |
| Snake segments shown | Move snake to several tiles | Green dots follow snake position |
| Apple shown | Look for red dot | Single red dot at apple's grid position |
| Grid matches play area | Compare minimap to game world | Hex grid layout matches actual tile positions |
| Not clipped by score panel | Check overlap | Minimap is at very top-left; score panel at slightly lower left |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Overlaps score panel | Low | Low (cosmetic) | POSITION at `(PADDING, PADDING)` — score panel starts at `(20, 18)` with 200×72 size |
| Performance hit (169 hex iterations per frame) | Low | Low | Only 169 dots; trivial cost |
| Snake dots invisible on dark background | Low | Low | Bright green (80,255,120) against dark background — sufficient contrast |

## Dependency Chain
- Depends on: Phase 2 (score is displayed in score panel, but minimap is independent)
- Phase 3 → Phase 4a (minimap needs `all_hexes()` which changes in Phase 4a)
