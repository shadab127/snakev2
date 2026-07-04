# SnakeV2 Verification Harness Guide

Run the verification harness to capture screenshots, FPS measurements,
and projection probe points. **Every phase from 16 onward must run this
harness and inspect the outputs before declaring the phase complete.**

## Quick start

```sh
python dev/verify_screenshots.py
```

Output goes to `dev/screenshots/`:
- `start_screen.png` — title screen
- `gameplay.png` — mid-game state (score > 0, snake visible, apple visible)
- `game_over.png` — game-over screen with score and menu
- `fps_report.txt` — render FPS with post-processing on and off
- `probe_points.txt` — world-to-screen coordinates for known points

## Options

| Flag | Default | Description |
|---|---|---|
| `--frames N` | 300 | Number of rendered frames for FPS measurement |
| `--steps N` | 500 | Simulation steps for the gameplay screenshot |

## What a correct frame must show

### Start screen
- Centered **"SNAKE V2"** logo with green glow
- Subtitle: **"3D Hex Grid - Enhanced Edition"**
- Three menu items: **Play**, **Settings**, **Quit**
- The hexagonal island is visible behind the UI

### Gameplay
- Snake body segments rendered as green hexes with 3D-ish shading
- Head is brighter green with visible eyes
- A red apple on a tile somewhere
- The island is **below** the sky, with the tile grid visible
- Water at the bottom with wave animation
- Effects visible (bloom glow, god rays, fog)

### Game over
- **"GAME OVER"** title in red
- Score display (should be > 0)
- Three menu items: **Restart**, **View Stats**, **Title Screen**
- Darkened overlay over the game world

### FPS report
- `post_on` should be 20+ FPS (software path)
- `post_off` should be 30+ FPS (software path)
- Values below these indicate a regression.

### Probe points
- All points should have valid screen coordinates (not OFFSCR)
- `grid_center` should be roughly mid-screen or slightly above
- `grid_center_above` should be higher on screen than `grid_center`
- `snake_head` should be on screen near the center
- `apple` should be on screen

## When to run

1. **Before** starting a recovery phase — capture the baseline
2. **After** completing a recovery phase — verify the fix improved the output
3. Before any commit that touches rendering, post-processing, or camera code

## Troubleshooting

- If the harness crashes with "pygame.error: No available video device",
  make sure SDL_VIDEODRIVER=dummy is set (the script does this automatically).
- If screenshots show a black screen, check that `game.render()` is being
  called (the harness calls it at each capture step).
