# Frame Checks

Run the checker:

```sh
python3 dev/check_frames.py
```

All thresholds are in the `CHECKS` dict at the top of `dev/check_frames.py`.

## Per-screenshot pixel checks

These run against four screenshots saved to `dev/screenshots/`:
`start_screen.png`, `gameplay.png`, `paused.png`, `game_over.png`.

Pixels are sampled on an 8×8 grid (every 8th pixel in x and y).

| Check | Threshold | Rationale |
|---|---|---|
| **mean_luma** | 8 ≤ value ≤ 140 | Catches black-out (mean < 8) and white-out (mean > 140). A healthy frame has visible content without being crushed or blown out. |
| **white_pct** | ≤ 5.0 % | Fewer than 5 % of sampled pixels may have luma > 240. Catches full-screen overlays that brighten every pixel (the known white-out bug). |
| **saturation** | ≥ 6.0 | Mean colour saturation (max(R,G,B) − min(R,G,B)) must be at least 6. Catches grey-wash where the scene has no colour. |
| **distinct_colors** | ≥ 100 | At least 100 unique (R,G,B) tuples among sampled pixels. Catches blank/flat frames (solid colour, missing geometry). |

## Orientation probe (`orientation`)

A world point at `(0, 0, 10)` must project to a **smaller screen y** (higher on screen) than the same point at `(0, 0, 0)`. This verifies the camera's z-up is not inverted.

| Check | Threshold | Rationale |
|---|---|---|
| orientation | above_y < ground_y | Detects upside-down camera. |

## FPS (`fps`)

Gameplay FPS measured with **default settings** (all post-processing enabled)
over 50 rendered frames. The game is in `PLAYING` state, advanced ~30 fixed
timesteps before measurement.

| Check | Threshold | Rationale |
|---|---|---|
| fps | ≥ 55 | Real-time playability at 60 Hz target. |

## Text contrast (`text_contrast`)

On each screenshot, specific pixel coordinates that should land on rendered
text (anchors) are compared against the local background at a small offset.
The luma difference must be at least `TEXT_CONTRAST_MIN` (50).

### Text anchors

| Screen | Anchor | Text position | Background offset |
|---|---|---|---|
| start_screen | `title` | center 640, 120 | +8, +8 |
| start_screen | `menu_play` | center 640, 260 | +8, +8 |
| start_screen | `footer` | center 640, 760 | +8, −8 |
| gameplay | `score` | 40, 35 | +6, +6 |
| paused | `paused_title` | center 640, 290 | +8, +8 |
| game_over | `game_over_title` | center 640, 260 | +8, +8 |

### Check

| Check | Threshold | Rationale |
|---|---|---|
| text_contrast | ≥ 50 luma diff | Text must be legible against the scene behind it; shadow/backing must provide sufficient separation. |

## Baseline output (2026-07-04)
