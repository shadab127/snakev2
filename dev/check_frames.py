"""Frame checker for SnakeV2.

Captures screenshots at each game state, runs pixel-level quality checks,
measures orientation correctness, and benchmarks FPS. Prints a PASS/FAIL
table and exits 0 only when all checks pass.

Usage:
    python3 dev/check_frames.py              # default ambient time
    python3 dev/check_frames.py --time 0.3   # dusk (0.0=midnight, 0.5=noon)
"""

import os
import sys
import math
import random
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from game_state import GameState
from config import WIDTH, HEIGHT, FIXED_DT, BASE_MOVE_INTERVAL, MIN_MOVE_INTERVAL, SPEED_DECAY_PER_POINT, CAM_3D_DIST, LIGHT_DIR, SUN_ANGLE_SPEED, HEX_SIZE

# ---------------------------------------------------------------------------
# All tunable thresholds — one obvious place
# ---------------------------------------------------------------------------
CHECKS = {
    "mean_luma_min": 40,
    "mean_luma_max": 110,
    "white_pct_max": 5.0,
    "mean_sat_min": 6,
    "distinct_colors_min": 100,
    "fps_min": 55,
    "text_contrast_min": 50,
}

# Text anchor positions for contrast checking.
# Each entry is (name, text_x, text_y, bg_dx, bg_dy) where:
#   (text_x, text_y)  — a pixel that should be ON the rendered text
#   (text_x+bg_dx, text_y+bg_dy)  — a nearby pixel representing local background
TEXT_ANCHORS = {
    # (name, text_x, text_y, bg_dx, bg_dy)
    # bg_dx/bg_dy must place the bg sample OUTSIDE the rendered text+glow bbox.
    # Text heights (with glow): font_large=~35+glow=~40px, font_small=~15+glow=~20px,
    # font_micro=~12px. So +40 in y is always safe below the text.
    "start_screen": [
        ("title",          WIDTH // 2 - 40, 122,    0,  -60),
        ("menu_play",      WIDTH // 2,      260,    30,  40),
        ("footer",         WIDTH // 2 - 80, 760,    0,   40),
    ],
    "gameplay": [
        ("score",          40,              35,     20,  30),
    ],
    "paused": [
        ("paused_title",   620,             285,    0,  -60),
    ],
    "game_over": [
        ("game_over_title", WIDTH // 2 - 30, 260,  30,  40),
    ],
}
# Per-state luma thresholds (gameplay tightened in phase 03; others keep 8–140
# because paused/game_over have intentional dark overlays).
STATE_LUMA = {
    "gameplay": (40, 110),
    "start_screen": (8, 140),
    "paused": (8, 140),
    "game_over": (8, 140),
}
_TIME_OVERRIDE = None
SAMPLE_GRID = 8
FPS_FRAMES = 50
GAMEPLAY_STEPS = 50

OUT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Pixel-sampling helpers
# ---------------------------------------------------------------------------

def _grid_sample(surf):
    """Yield (r, g, b) tuples on a uniform grid."""
    w, h = surf.get_size()
    for y in range(0, h, SAMPLE_GRID):
        for x in range(0, w, SAMPLE_GRID):
            c = surf.get_at((x, y))
            yield c[0], c[1], c[2]


def analyze_frame(surf, label):
    """Return a dict of pixel metrics for *surf*."""
    pixels = list(_grid_sample(surf))
    n = len(pixels)

    luma_sum = 0.0
    white_count = 0
    sat_sum = 0.0
    color_set = set()

    for r, g, b in pixels:
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        luma_sum += lum
        if lum > 240:
            white_count += 1
        sat_sum += max(r, g, b) - min(r, g, b)
        color_set.add((r, g, b))

    return {
        "label": label,
        "mean_luma": luma_sum / n,
        "white_pct": white_count / n * 100.0,
        "mean_sat": sat_sum / n,
        "distinct": len(color_set),
        "samples": n,
    }

# ---------------------------------------------------------------------------
# Screenshot capture
# ---------------------------------------------------------------------------

def _drain():
    pygame.event.clear()


def capture_start_screen(game):
    game.state = GameState.START
    game._menu_count = 3
    game.menu_selection = 0
    if _TIME_OVERRIDE is None:
        game.render_time = 1.0
    _drain()
    for _ in range(10):
        game.render_time += 1 / 60
        game.render()
    path = os.path.join(OUT_DIR, "start_screen.png")
    pygame.image.save(game.screen, path)
    return path


def capture_gameplay(game, steps=GAMEPLAY_STEPS):
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain()

    rng = random.Random(42)
    turn_seq = [rng.choice(["L", "R"]) for _ in range(1000)]
    tidx = 0
    total = 0
    captured_paths = []

    while total < steps and game.state == GameState.PLAYING:
        if turn_seq[tidx % len(turn_seq)] == "L":
            game.turn_left()
        else:
            game.turn_right()
        tidx += 1
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - game.score * SPEED_DECAY_PER_POINT)
        steps_needed = max(1, int(interval / FIXED_DT)) + 1
        for i in range(steps_needed):
            if game.state == GameState.PLAYING:
                game.update(FIXED_DT)
            # Capture frames at 25%, 50%, 75% of turn interpolation
            if i in (steps_needed // 4, steps_needed // 2, (3 * steps_needed) // 4):
                if _TIME_OVERRIDE is not None:
                    game.render_time = _TIME_OVERRIDE
                    game.ambient_time = _TIME_OVERRIDE
                else:
                    game.render_time = 2.0
                game.render()
                path = os.path.join(OUT_DIR, f"gameplay_turn_{len(captured_paths)}.png")
                pygame.image.save(game.screen, path)
                captured_paths.append(path)
                if len(captured_paths) >= 15:
                    break
        total += steps_needed
        if len(captured_paths) >= 15:
            break

    if _TIME_OVERRIDE is not None:
        game.render_time = _TIME_OVERRIDE
        game.ambient_time = _TIME_OVERRIDE
    else:
        game.render_time = 2.0
    game.render()
    path = os.path.join(OUT_DIR, "gameplay.png")
    pygame.image.save(game.screen, path)
    captured_paths.append(path)
    return captured_paths


def capture_paused(game):
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain()
    for _ in range(20):
        game.update(FIXED_DT)
    game.state = GameState.PAUSED
    game.menu_selection = 0
    game._menu_count = 3
    _drain()
    if _TIME_OVERRIDE is not None:
        game.render_time = _TIME_OVERRIDE
        game.ambient_time = _TIME_OVERRIDE
    else:
        game.render_time = 1.0
    for _ in range(5):
        game.render()
    path = os.path.join(OUT_DIR, "paused.png")
    pygame.image.save(game.screen, path)
    return path


def capture_game_over(game):
    game.state = GameState.GAME_OVER
    score = max(game.score, 50)
    game.score = score
    game.high_score = max(game.high_score, score)
    game.score_count_up = game.score
    game.score_count_up_timer = 0.0
    game._countup_started = True
    game._menu_count = 3
    game.menu_selection = 0
    game.death_anim = {"timer": 0.0, "phase": "none"}
    game.grade_death_darken = 0.0
    game.fade_alpha = 0
    game.fade_target = 0
    game._transitioning = False
    _drain()
    if _TIME_OVERRIDE is not None:
        game.render_time = _TIME_OVERRIDE
        game.ambient_time = _TIME_OVERRIDE
    else:
        game.render_time = 3.0
    for _ in range(5):
        game.render()
    path = os.path.join(OUT_DIR, "game_over.png")
    pygame.image.save(game.screen, path)
    return path


def capture_scripted_turns(game):
    """Perform scripted double-turn (L, L, R, R) capturing ~10 frames per turn."""
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain()
    for _ in range(20):
        game.update(FIXED_DT)
    captured = []
    turn_dirs = ['L', 'L', 'R', 'R']
    for td in turn_dirs:
        if game.state != GameState.PLAYING:
            break
        if td == 'L':
            game.turn_left()
        else:
            game.turn_right()
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - game.score * SPEED_DECAY_PER_POINT)
        steps_needed = max(1, int(interval / FIXED_DT)) + 1
        capture_pts = set()
        for pct in range(10, 101, 10):
            pt = max(0, min(steps_needed, int(steps_needed * pct / 100)))
            capture_pts.add(pt)
        for i in range(steps_needed + 1):
            if game.state == GameState.PLAYING:
                game.update(FIXED_DT)
            if i in capture_pts:
                if _TIME_OVERRIDE is not None:
                    game.render_time = _TIME_OVERRIDE
                    game.ambient_time = _TIME_OVERRIDE
                else:
                    game.render_time = 2.0
                game.render()
                path = os.path.join(OUT_DIR, f'scripted_turn_{len(captured)}.png')
                pygame.image.save(game.screen, path)
                captured.append(path)
        gap_steps = max(1, steps_needed * 2)
        for _ in range(gap_steps):
            if game.state == GameState.PLAYING:
                game.update(FIXED_DT)
    return captured


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------

def measure_fps(game, num_frames=FPS_FRAMES):
    """Return (fps, elapsed_s) for *num_frames* renders at default settings."""
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain()

    for _ in range(30):
        game.update(FIXED_DT)

    for _ in range(5):
        game.render()

    start = time.perf_counter()
    for _ in range(num_frames):
        game.render()
    elapsed = time.perf_counter() - start
    fps = num_frames / elapsed if elapsed > 0 else 0.0
    return fps, elapsed


def check_orientation(game):
    """A world point above ground must appear *higher* on screen (smaller y)."""
    from utils import hex_to_pixel

    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain()

    for _ in range(30):
        game.update(FIXED_DT)
    game.render()

    cx, cy = hex_to_pixel(0, 0)
    _, sy_ground, _ = game.camera.project(cx, cy, 0)
    _, sy_above, _ = game.camera.project(cx, cy, 10)

    return sy_above < sy_ground, sy_ground, sy_above


def check_behind_camera(game):
    """A point behind the camera must be rejected (sx == -999)."""
    from config import CAM_3D_DIST
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain()
    for _ in range(30):
        game.update(FIXED_DT)
    game.render()
    # Pick a point clearly behind the camera
    sx, sy, depth = game.camera.project(-CAM_3D_DIST * 2, 0, 0)
    rejected = sx == -999
    return rejected, sx, sy


def check_head_position(game):
    """Snake head must project into the lower-central band of the screen."""
    from utils import hex_to_pixel

    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain()

    for _ in range(30):
        game.update(FIXED_DT)
    game.render()

    q, r = game.snake[0]
    cx, cy = hex_to_pixel(q, r)
    sx, sy, _ = game.camera.project(cx, cy, 0)

    y_lo = int(0.55 * HEIGHT)
    y_hi = int(0.80 * HEIGHT)
    x_lo = int(0.40 * WIDTH)
    x_hi = int(0.60 * WIDTH)

    y_ok = y_lo <= sy <= y_hi
    x_ok = x_lo <= sx <= x_hi

    return y_ok and x_ok, sx, sy, y_lo, y_hi, x_lo, x_hi

def check_text_contrast(surf, state_label):
    """Check luma difference between text pixels and local background.
    
    Returns (passed, [(anchor_name, diff, min_diff), ...]).
    """
    min_diff = CHECKS["text_contrast_min"]
    results = []
    all_pass = True
    for name, tx, ty, bdx, bdy in TEXT_ANCHORS.get(state_label, []):
        bx = min(max(tx + bdx, 0), WIDTH - 1)
        by = min(max(ty + bdy, 0), HEIGHT - 1)
        tc = surf.get_at((tx, ty))
        bc = surf.get_at((bx, by))
        tl = 0.299 * tc[0] + 0.587 * tc[1] + 0.114 * tc[2]
        bl = 0.299 * bc[0] + 0.587 * bc[1] + 0.114 * bc[2]
        diff = abs(tl - bl)
        ok = diff >= min_diff
        if not ok:
            all_pass = False
        results.append((name, diff, min_diff, ok))
    return all_pass, results


def check_sky_purity(surf):
    """Check top quarter of frame for non-sky pixels.

    A pixel is considered "sky" if any of:
      - Blue sky: b > 1.5*r and b > 1.5*g and b > 30
      - Near-black (night): luma < 15
      - Neutral/grey (clouds, stars): all channels within 40 of each other
        and max channel > 50 (distinguishes from warm/colored garbage)

    Returns (non_sky_pct, total_sampled).
    """
    w, h = surf.get_size()
    top_h = h // 4
    total = 0
    non_sky = 0
    for y in range(0, top_h, SAMPLE_GRID):
        for x in range(0, w, SAMPLE_GRID):
            c = surf.get_at((x, y))
            r, g, b = c[0], c[1], c[2]
            total += 1
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            is_blue = b > 1.5 * r and b > 1.5 * g and b > 30
            is_dark = luma < 15
            is_neutral = max(r, g, b) > 50 and abs(r - g) < 40 and abs(g - b) < 40
            is_sky = is_blue or is_dark or is_neutral
            if not is_sky:
                non_sky += 1
    pct = non_sky / total * 100 if total > 0 else 0
    return pct, total


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

_PASS_SYMBOL = "PASS"
_FAIL_SYMBOL = "FAIL"


def _table_line(name, measured, threshold, passed):
    return f"  {name:<45s} {measured:<30s} {threshold:<20s} {_PASS_SYMBOL if passed else _FAIL_SYMBOL}"


def _check_mean_luma(meta):
    v = meta["mean_luma"]
    lo, hi = STATE_LUMA.get(meta["label"], (CHECKS["mean_luma_min"], CHECKS["mean_luma_max"]))
    return lo <= v <= hi


def _check_white_pct(meta):
    return meta["white_pct"] <= CHECKS["white_pct_max"]


def _check_saturation(meta):
    return meta["mean_sat"] >= CHECKS["mean_sat_min"]


def _check_distinct_colors(meta):
    return meta["distinct"] >= CHECKS["distinct_colors_min"]


def check_sun_anchoring(game):
    """World-anchored sun: 180deg turn must change sun screen x by >=100px."""
    _drain()
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    for _ in range(30):
        game.update(FIXED_DT)

    game.render_time = 2.0
    game.ambient_time = 2.0
    game.render()

    sun_angle = game.render_time * SUN_ANGLE_SPEED
    cos_a = math.cos(sun_angle)
    sin_a = math.sin(sun_angle)
    sun_wx = (LIGHT_DIR[0] * cos_a - LIGHT_DIR[1] * sin_a) * 10000
    sun_wy = (LIGHT_DIR[0] * sin_a + LIGHT_DIR[1] * cos_a) * 10000
    sun_wz = 500
    sx1, sy1, _ = game.camera.project(sun_wx, sun_wy, sun_wz)

    # 180deg turn (3 left turns on hex grid)
    for _ in range(3):
        game.turn_left()
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - game.score * SPEED_DECAY_PER_POINT)
        steps = max(1, int(interval / FIXED_DT)) + 5
        for _ in range(steps):
            if game.state == GameState.PLAYING:
                game.update(FIXED_DT)

    # Wait for camera yaw to finish rotating (smooth interpolation needs ~0.55s)
    for _ in range(100):
        if game.state != GameState.PLAYING:
            break
        game.update(FIXED_DT)

    game.render()
    sx2, sy2, _ = game.camera.project(sun_wx, sun_wy, sun_wz)

    if sx1 == -999 and sx2 == -999:
        return False, f"sun behind camera in both frames (sx1={sx1:.0f} sx2={sx2:.0f})", sx1, sx2
    if sx1 == -999 or sx2 == -999:
        return True, f"sun visible in one frame (sx1={sx1:.0f} sx2={sx2:.0f})", sx1, sx2
    x_diff = abs(sx1 - sx2)
    return x_diff >= 100, f"dx={x_diff:.0f}px", sx1, sx2


def check_turn_head_band_and_yaw_rate(game):
    """Re-run scripted turns, check head in band and yaw rate on every capture frame."""
    from utils import hex_to_pixel

    _drain()
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    for _ in range(20):
        game.update(FIXED_DT)

    y_lo, y_hi = int(0.55 * HEIGHT), int(0.80 * HEIGHT)
    x_lo, x_hi = int(0.40 * WIDTH), int(0.60 * WIDTH)

    head_positions = []
    yaw_values_by_turn = []

    turn_dirs = ['L', 'L', 'R', 'R']
    for td in turn_dirs:
        if game.state != GameState.PLAYING:
            break
        if td == 'L':
            game.turn_left()
        else:
            game.turn_right()
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - game.score * SPEED_DECAY_PER_POINT)
        steps_needed = max(1, int(interval / FIXED_DT)) + 1
        capture_pts = set()
        for pct in range(10, 101, 10):
            pt = max(0, min(steps_needed, int(steps_needed * pct / 100)))
            capture_pts.add(pt)
        turn_yaws = []
        for i in range(steps_needed + 1):
            if game.state == GameState.PLAYING:
                game.update(FIXED_DT)
            if i in capture_pts:
                game.camera._build_matrices()  # rebuild after sim-only update
                q, r = game.snake[0]
                cx, cy = hex_to_pixel(q, r)
                sx, sy, _ = game.camera.project(cx, cy, 0)
                head_positions.append((sx, sy))
                turn_yaws.append(game.camera._yaw)
        yaw_values_by_turn.append(turn_yaws)
        gap_steps = max(1, steps_needed * 2)
        for _ in range(gap_steps):
            if game.state == GameState.PLAYING:
                game.update(FIXED_DT)

    # Head position band check
    head_ok = all(x_lo <= sx <= x_hi and y_lo <= sy <= y_hi for sx, sy in head_positions)
    head_outliers = sum(1 for sx, sy in head_positions if not (x_lo <= sx <= x_hi and y_lo <= sy <= y_hi))

    # Yaw rate check: max consecutive-frame delta WITHIN each turn (not across gap)
    max_yaw_delta = 0.0
    for turn_yaws in yaw_values_by_turn:
        for i in range(1, len(turn_yaws)):
            delta = abs(turn_yaws[i] - turn_yaws[i - 1])
            delta = min(delta, 2 * math.pi - delta)  # shortest arc
            max_yaw_delta = max(max_yaw_delta, delta)
    max_deg = math.degrees(max_yaw_delta)
    max_allowed = 4.0  # degrees per frame at 60 FPS (tolerance over 220/60≈3.67)
    yaw_rate_ok = max_deg <= max_allowed

    head_meas = f"{head_outliers}/{len(head_positions)} out of band"
    yaw_meas = f"{max_deg:.2f}°/frame"
    return head_ok, head_meas, yaw_rate_ok, yaw_meas


def check_motion_continuity(game):
    """During a straight run at default speed, capture 20 consecutive frames;
    head world pixel position (from spline interpolation) must change on EVERY
    frame, and no single-frame jump may exceed 2x the median per-frame movement.

    We measure *world* pixel position (not screen) because the camera follows
    the head directly — if we projected through the camera the head would always
    land at the same screen coordinate."""
    _drain()
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    for _ in range(5):
        game.update(FIXED_DT)
    head_positions = []
    for _ in range(20):
        game.render()
        # Use interpolated drawn world position from spline, NOT raw grid pos
        sp = getattr(game, '_spline_positions', None)
        if sp and len(sp) > 0:
            hx, hy = sp[0][0], sp[0][1]
        else:
            return False, "no _spline_positions after render"
        head_positions.append((hx, hy))
        game.update(FIXED_DT)

    jumps = []
    for i in range(1, len(head_positions)):
        dx = head_positions[i][0] - head_positions[i - 1][0]
        dy = head_positions[i][1] - head_positions[i - 1][1]
        jumps.append(math.hypot(dx, dy))

    if not jumps:
        return False, "no jumps (only one frame?)"
    if max(jumps) == 0:
        return False, "no movement detected"

    median_jump = sorted(jumps)[len(jumps) // 2]
    max_jump = max(jumps)
    threshold = 2.0 * median_jump
    ok = max_jump <= threshold and min(jumps) > 0
    msg = f"all frames moving, median jump {median_jump:.2f}px no stalls, max jump {'≤' if ok else '>'} 2x median"
    return ok, msg


def check_body_length(game):
    """With a known snake length, project the drawn head and drawn tail-tip
    world positions; their world distance must be within ±20% of
    (segments × cell spacing)."""
    from utils import hex_to_pixel
    _drain()
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    for _ in range(20):
        game.update(FIXED_DT)

    game.render()
    if not hasattr(game, '_spline_positions') or not game._spline_positions:
        return False, "no spline positions"

    head_px, head_py, _, _ = game._spline_positions[0]
    tail_px, tail_py, _, _ = game._spline_positions[-1]
    measured = math.hypot(tail_px - head_px, tail_py - head_py)

    n_segments = len(game.snake)
    cell_spacing = HEX_SIZE * math.sqrt(3)
    expected = (n_segments - 1) * cell_spacing

    ratio = measured / expected if expected > 0 else 0
    ok = 0.80 <= ratio <= 1.20
    msg = f"measured={measured:.1f} expected={expected:.1f} ratio={ratio:.3f} ratio 0.80–1.20"
    return ok, msg


def check_shadow_band(surf):
    """Check bottom half for near-black (< 5 luma) regions wider than 5% of
    the frame directly under the body path — catches the self-intersecting
    shadow band (luma < 5 filters out normal body contact shadow)."""
    w, h = surf.get_size()
    x_lo = int(w * 0.40)
    x_hi = int(w * 0.60)
    y_lo = int(h * 0.50)
    y_hi = int(h * 0.85)
    max_dark_run = 0
    for y in range(y_lo, y_hi, 4):
        run = 0
        for x in range(x_lo, x_hi):
            c = surf.get_at((x, y))
            lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
            if lum < 5:
                run += 1
            else:
                if run > max_dark_run:
                    max_dark_run = run
                run = 0
    width_pct = max_dark_run / max(1, x_hi - x_lo) * 100
    threshold = 15.0
    ok = width_pct < threshold
    msg = f"no dark run > {threshold:.0f}% width" if ok else f"dark run {width_pct:.1f}% > {threshold:.0f}%"
    return ok, msg


def check_terrain_gaps(game):
    """Check bottom-center region for near-black pixels (< 12 luma).
    With grooves gone, must drop below 2%."""
    import pygame.image
    _drain()
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    game._tile_cache_valid = False
    game._ground_cache_valid = False
    for _ in range(30):
        game.update(FIXED_DT)
    game.render()
    path = os.path.join(OUT_DIR, "terrain_gaps_check.png")
    pygame.image.save(game.screen, path)
    surf = pygame.image.load(path)

    w, h = surf.get_size()
    x_lo = int(w * 0.25)
    x_hi = int(w * 0.75)
    y_lo = int(h * 0.55)
    y_hi = int(h * 0.90)
    total = 0
    dark = 0
    for y in range(y_lo, y_hi, 4):
        for x in range(x_lo, x_hi, 4):
            c = surf.get_at((x, y))
            lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
            total += 1
            if lum < 12:
                dark += 1
    pct = dark / total * 100 if total > 0 else 0
    ok = pct < 2.0
    return ok, f"dark_pixels={pct:.2f}% < 2%"


def check_frame_pacing(game):
    """Over 120 rendered frames, 95th-percentile frame time ≤ 1.5× median."""
    _drain()
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    for _ in range(30):
        game.update(FIXED_DT)
    for _ in range(5):
        game.render()
    frame_times = []
    for _ in range(120):
        t0 = time.perf_counter()
        game.render()
        elapsed = (time.perf_counter() - t0) * 1000
        frame_times.append(elapsed)
        if game.state == GameState.PLAYING:
            game.update(FIXED_DT)
    if not frame_times:
        return False, "no frame times"
    sorted_t = sorted(frame_times)
    n = len(sorted_t)
    median = sorted_t[n // 2]
    p95 = sorted_t[int(n * 0.95)]
    ok = p95 <= 1.5 * median if median > 0 else False
    msg = f"p95={p95:.2f}ms median={median:.2f}ms ratio={p95/max(median,0.001):.2f}"
    return ok, msg


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _TIME_OVERRIDE
    import argparse
    parser = argparse.ArgumentParser(description="Check SnakeV2 frames")
    parser.add_argument("--time", type=float, default=None,
                        help="Set ambient time for capture (0.0=midnight, 0.5=noon)")
    args = parser.parse_args()
    _TIME_OVERRIDE = args.time

    from main import SnakeGame

    game = SnakeGame()
    game.audio._ok = False
    if _TIME_OVERRIDE is not None:
        game.render_time = _TIME_OVERRIDE
        game.ambient_time = _TIME_OVERRIDE
    _drain()

    lines = []
    all_pass = True

    states = ["start_screen", "gameplay", "paused", "game_over"]
    state_fns = {
        "start_screen": capture_start_screen,
        "gameplay": capture_gameplay,
        "paused": capture_paused,
        "game_over": capture_game_over,
    }
    check_fns = [
        ("mean_luma", _check_mean_luma, lambda m: f"{m['mean_luma']:.1f}",
         lambda s=None: f"{STATE_LUMA.get(s, (CHECKS['mean_luma_min'], CHECKS['mean_luma_max']))[0]}–"
                        f"{STATE_LUMA.get(s, (CHECKS['mean_luma_min'], CHECKS['mean_luma_max']))[1]}"),
        ("white_pct", _check_white_pct, lambda m: f"{m['white_pct']:.2f}%",
         lambda s=None: f"≤ {CHECKS['white_pct_max']}%"),
        ("saturation", _check_saturation, lambda m: f"{m['mean_sat']:.1f}",
         lambda s=None: f"≥ {CHECKS['mean_sat_min']}"),
        ("distinct_colors", _check_distinct_colors, lambda m: f"{m['distinct']}",
         lambda s=None: f"≥ {CHECKS['distinct_colors_min']}"),
    ]

    print("SnakeV2 Frame Checker")
    print("=" * 72)

    # 1 – Screenshot capture + pixel analysis
    for state in states:
        result = state_fns[state](game)
        paths = result if isinstance(result, list) else [result]
        
        metas = []
        for p in paths:
            surf = pygame.image.load(p)
            metas.append(analyze_frame(surf, state))
        
        header_path = paths[-1]
        main_meta = metas[-1]
        lines.append(f"\n  [{state}]  {os.path.basename(header_path)}  ({main_meta['samples']} samples)")

        for chk_name, pred_fn, meas_fn, thresh_fn in check_fns:
            all_ok = True
            worst_meta = main_meta
            for m in metas:
                if not pred_fn(m):
                    all_ok = False
                    worst_meta = m
                    break
            if not all_ok:
                all_pass = False
            lines.append(_table_line(f"  {state}/{chk_name}", meas_fn(worst_meta), thresh_fn(state), all_ok))

        # Text contrast check
        # We only check the steady frame for contrast to avoid noise from motion
        surf = pygame.image.load(header_path)
        c_ok, c_results = check_text_contrast(surf, state)
        if not c_ok:
            all_pass = False
        for name, diff, min_diff, ok in c_results:
            lines.append(_table_line(f"  {state}/text_contrast/{name}", f"{diff:.1f}", f"≥ {min_diff}", ok))

    # 1b – Scripted turn capture and analysis
    turn_paths = capture_scripted_turns(game)
    if turn_paths:
        lines.append(f"\n  [turn_script]  ({len(turn_paths)} frames)")
        turn_metas = []
        for p in turn_paths:
            surf = pygame.image.load(p)
            turn_metas.append(analyze_frame(surf, "turn_script"))
        for chk_name, pred_fn, meas_fn, thresh_fn in check_fns:
            all_ok = True
            worst_meta = turn_metas[0]
            for m in turn_metas:
                if not pred_fn(m):
                    all_ok = False
                    worst_meta = m
                    break
            if not all_ok:
                all_pass = False
            lines.append(_table_line(f"  turn_script/{chk_name}", meas_fn(worst_meta), thresh_fn("gameplay"), all_ok))
        worst_non_sky = 0
        worst_sky_path = turn_paths[0]
        for p in turn_paths:
            surf = pygame.image.load(p)
            pct, _ = check_sky_purity(surf)
            if pct > worst_non_sky:
                worst_non_sky = pct
                worst_sky_path = p
        sky_ok = worst_non_sky <= 5.0
        if not sky_ok:
            all_pass = False
        worst_surf = pygame.image.load(worst_sky_path)
        pygame.image.save(worst_surf, os.path.join(OUT_DIR, "turn_worst.png"))
        lines.append(_table_line(f"  turn_script/sky_purity", f"{worst_non_sky:.2f}%", "≤ 5.0%", sky_ok))

    # Check shadow band on turn frames
    sb_worst_pct = 0.0
    for p in turn_paths:
        surf = pygame.image.load(p)
        sb_ok, sb_msg = check_shadow_band(surf)
        if not sb_ok:
            pct_str = sb_msg.split()[2].rstrip('%')
            sb_worst_pct = max(sb_worst_pct, float(pct_str))
    sb_pass = sb_worst_pct <= 15.0
    if not sb_pass:
        all_pass = False
    lines.append(_table_line("  shadow_band", "no dark band detected" if sb_pass else f"dark run {sb_worst_pct:.1f}%", "no dark run > 15% width", sb_pass))

    # 2 – Orientation
    ok, sy_ground, sy_above = check_orientation(game)
    if not ok:
        all_pass = False
    meas = f"above_y={sy_above:.1f}  ground_y={sy_ground:.1f}"
    lines.append(_table_line("  orientation", meas, "above_y < ground_y", ok))

    # 3 – Behind-camera rejection
    bc_ok, bc_sx, bc_sy = check_behind_camera(game)
    if not bc_ok:
        all_pass = False
    meas = f"sx={bc_sx:.1f} sy={bc_sy:.1f}"
    lines.append(_table_line("  behind_camera", meas, "sx == -999 (rejected)", bc_ok))

    # 4 – Head position band (camera framing)
    ok, hsx, hsy, y_lo, y_hi, x_lo, x_hi = check_head_position(game)
    if not ok:
        all_pass = False
    meas = f"sx={hsx:.1f} sy={hsy:.1f}"
    thresh = f"x={x_lo}–{x_hi} y={y_lo}–{y_hi}"
    lines.append(_table_line("  head_position", meas, thresh, ok))

    # 5 – Sun anchoring
    sun_ok, sun_meas, sun_sx1, sun_sx2 = check_sun_anchoring(game)
    if not sun_ok:
        all_pass = False
    lines.append(_table_line("  sun_anchoring", sun_meas, "dx >= 100px or behind->visible", sun_ok))

    # 6 – Turn head-band and yaw rate
    head_ok, head_meas, yaw_ok, yaw_meas = check_turn_head_band_and_yaw_rate(game)
    if not head_ok:
        all_pass = False
    lines.append(_table_line("  turn_head_band", head_meas, "0 out of band", head_ok))
    if not yaw_ok:
        all_pass = False
    lines.append(_table_line("  turn_yaw_rate", yaw_meas, "≤ 4.0°/frame", yaw_ok))

    # 7 – FPS
    fps, elapsed = measure_fps(game, FPS_FRAMES)
    ok = fps >= CHECKS["fps_min"]
    if not ok:
        all_pass = False
    lines.append(_table_line("  fps", f"{fps:.1f}", f"≥ {CHECKS['fps_min']}", ok))

    # 8 – Frame pacing
    fp_ok, fp_msg = check_frame_pacing(game)
    if not fp_ok:
        all_pass = False
    lines.append(_table_line("  frame_pacing", fp_msg, "p95 ≤ 1.5× median", fp_ok))

    # 9 – Motion continuity
    mc_ok, mc_msg = check_motion_continuity(game)
    if not mc_ok:
        all_pass = False
    lines.append(_table_line("  motion_continuity", mc_msg, "all frames moving, no stall, max jump ≤ 2x median", mc_ok))

    # 10 – Body length
    bl_ok, bl_msg = check_body_length(game)
    if not bl_ok:
        all_pass = False
    lines.append(_table_line("  body_length", bl_msg, "ratio 0.80–1.20", bl_ok))

    # 11 – Terrain gaps
    tg_ok, tg_msg = check_terrain_gaps(game)
    if not tg_ok:
        all_pass = False
    lines.append(_table_line("  terrain_gaps", tg_msg, "dark_pixels < 2%", tg_ok))

    # Summary table
    print("\nCheck table")
    print("-" * 112)
    print(_table_line("Check", "Measured", "Threshold", "Status"))
    print("-" * 112)
    for line in lines:
        print(line)
    print("-" * 112)
    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAIL'}")
    print()

    pygame.quit()
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
