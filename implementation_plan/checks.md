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


## Turn script pixel checks (`turn_script`)

After the random-turn gameplay capture, the checker performs a scripted
double-turn sequence (L, L, R, R) with a few idle steps between each turn.
For each of the four turns, ~10 frames are captured at 10%, 20%, … 100%
of the turn interpolation steps (~40 total frames).

Turn frames are analysed with the same per-screenshot pixel checks as steady
gameplay (luma window 40–110, ≤5% white, ≥6 saturation, ≥100 distinct colors).
An additional **sky purity** check samples only the top quarter of the frame.

| Check | Threshold | Rationale |
|---|---|---|
| **mean_luma** | 40 ≤ value ≤ 110 | Catches dark/blown-out frames during camera swing (same as gameplay). |
| **white_pct** | ≤ 5.0 % | Catches full-screen overlays during turns. |
| **saturation** | ≥ 6.0 | Catches grey-wash during camera motion. |
| **distinct_colors** | ≥ 100 | Catches blank/flat frames during turns. |
| **sky_purity** | ≤ 5.0 % non-sky pixels in top quarter | Catches mirrored-geometry wedges (warm/tan/bright-green) in the sky. |

## Sky purity (`turn_script/sky_purity`)

Only checked on `turn_script` frames. The top quarter of the screen
(y = 0 to `HEIGHT//4`) is sampled on the same 8×8 grid.

A sampled pixel is **non-sky** if it does **not** match either condition:

- **Sky-blue**: `b > 1.5 × r AND b > 1.5 × g AND b > 30`
- **Near-black**: luma < 15

Non-sky pixels include any warm/tan/bright-green colours that should never
appear in the sky region. If more than 5 % of top-quarter sampled pixels are
non-sky, the check fails.

The worst turn frame (the one with the highest percentage of non-sky pixels)
is saved as `dev/screenshots/turn_worst.png` for visual inspection.

| Check | Threshold | Rationale |
|---|---|---|
| sky_purity | ≤ 5.0 % non-sky in top quarter | Detects projection-corruption wedges painting non-sky colours into the sky. |

## Baseline output (2026-07-05, post-fix)

```
SnakeV2 Frame Checker
========================================================================

Check table
----------------------------------------------------------------------------------------------------------------
  Check                                         Measured                       Threshold            PASS
----------------------------------------------------------------------------------------------------------------

  [start_screen]  start_screen.png  (16000 samples)
    start_screen/mean_luma                      59.3                           8–140                PASS
    start_screen/white_pct                      0.00%                          ≤ 5.0%               PASS
    start_screen/saturation                     39.9                           ≥ 6                  PASS
    start_screen/distinct_colors                642                            ≥ 100                PASS
    start_screen/text_contrast/title            102.4                          ≥ 50                 PASS
    start_screen/text_contrast/menu_play        62.7                           ≥ 50                 PASS
    start_screen/text_contrast/footer           79.4                           ≥ 50                 PASS

  [gameplay]  gameplay.png  (16000 samples)
    gameplay/mean_luma                          59.0                           40–110               PASS
    gameplay/white_pct                          0.78%                          ≤ 5.0%               PASS
    gameplay/saturation                         39.7                           ≥ 6                  PASS
    gameplay/distinct_colors                    476                            ≥ 100                PASS
    gameplay/text_contrast/score                103.6                          ≥ 50                 PASS

  [paused]  paused.png  (16000 samples)
    paused/mean_luma                            18.0                           8–140                PASS
    paused/white_pct                            0.00%                          ≤ 5.0%               PASS
    paused/saturation                           12.9                           ≥ 6                  PASS
    paused/distinct_colors                      339                            ≥ 100                PASS
    paused/text_contrast/paused_title           219.0                          ≥ 50                 PASS

  [game_over]  game_over.png  (16000 samples)
    game_over/mean_luma                         13.8                           8–140                PASS
    game_over/white_pct                         0.00%                          ≤ 5.0%               PASS
    game_over/saturation                        11.9                           ≥ 6                  PASS
    game_over/distinct_colors                   286                            ≥ 100                PASS
    game_over/text_contrast/game_over_title     120.1                          ≥ 50                 PASS

  [turn_script]  (40 frames)
    turn_script/mean_luma                       59.2                           40–110               PASS
    turn_script/white_pct                       0.00%                          ≤ 5.0%               PASS
    turn_script/saturation                      42.0                           ≥ 6                  PASS
    turn_script/distinct_colors                 578                            ≥ 100                PASS
    turn_script/sky_purity                      3.08%                          ≤ 5.0%               PASS
    orientation                                 above_y=557.7  ground_y=591.7  above_y < ground_y   PASS
    behind_camera                               sx=-999.0 sy=-999.0            sx == -999 (rejected) PASS
    head_position                               sx=640.0 sy=502.6              x=512–768 y=440–640  PASS
    sun_anchoring                               sun visible in one frame (sx1=1704 sx2=-999) dx >= 100px or behind->visible PASS
    turn_head_band                              0/40 out of band               0 out of band        PASS
    turn_yaw_rate                               3.67°/frame                    ≤ 4.0°/frame         PASS
    fps                                         78.8                           ≥ 55                 PASS
----------------------------------------------------------------------------------------------------------------

Overall: ALL PASS
```

### Observations (2026-07-05, post-fix)

- All checks pass at default time, midnight (--time 0.0), dawn (--time 0.25), and noon (--time 0.5).
- gameplay/mean_luma raised from 37.6→59.0 (scene exposure brightened via palette and config tuning).
- turn_script/distinct_colors raised from 73→578 (richer scene detail visible during camera swing).
- fps raised from 54.4→78.8 (performance optimisation of the rounded tube body rendering).
- 0 failures, all phases 01–08 complete.
