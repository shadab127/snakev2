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
from config import WIDTH, HEIGHT, FIXED_DT, BASE_MOVE_INTERVAL, MIN_MOVE_INTERVAL, SPEED_DECAY_PER_POINT, CAM_3D_DIST

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
        ("title",          WIDTH // 2 - 40, 122,    30,  40),
        ("menu_play",      WIDTH // 2,      260,    30,  40),
        ("footer",         WIDTH // 2 - 80, 760,    30, -25),
    ],
    "gameplay": [
        ("score",          40,              35,     20,  30),
    ],
    "paused": [
        ("paused_title",   620,             285,    30,  40),
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
    while total < steps and game.state == GameState.PLAYING:
        if turn_seq[tidx % len(turn_seq)] == "L":
            game.turn_left()
        else:
            game.turn_right()
        tidx += 1
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - game.score * SPEED_DECAY_PER_POINT)
        steps_needed = max(1, int(interval / FIXED_DT)) + 1
        for _ in range(steps_needed):
            if game.state == GameState.PLAYING:
                game.update(FIXED_DT)
        total += steps_needed

    if _TIME_OVERRIDE is not None:
        game.render_time = _TIME_OVERRIDE
        game.ambient_time = _TIME_OVERRIDE
    else:
        game.render_time = 2.0
    game.render()
    path = os.path.join(OUT_DIR, "gameplay.png")
    pygame.image.save(game.screen, path)
    return path


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
        path = state_fns[state](game)
        surf = pygame.image.load(path)
        meta = analyze_frame(surf, state)
        lines.append(f"\n  [{state}]  {os.path.basename(path)}  ({meta['samples']} samples)")

        for chk_name, pred_fn, meas_fn, thresh_fn in check_fns:
            ok = pred_fn(meta)
            if not ok:
                all_pass = False
            lines.append(_table_line(f"  {state}/{chk_name}", meas_fn(meta), thresh_fn(state), ok))

        # Text contrast check
        c_ok, c_results = check_text_contrast(surf, state)
        if not c_ok:
            all_pass = False
        for name, diff, min_diff, ok in c_results:
            lines.append(_table_line(f"  {state}/text_contrast/{name}", f"{diff:.1f}", f"≥ {min_diff}", ok))

    # 2 – Orientation
    ok, sy_ground, sy_above = check_orientation(game)
    if not ok:
        all_pass = False
    meas = f"above_y={sy_above:.1f}  ground_y={sy_ground:.1f}"
    lines.append(_table_line("  orientation", meas, "above_y < ground_y", ok))

    # 3 – Head position band (camera framing)
    ok, hsx, hsy, y_lo, y_hi, x_lo, x_hi = check_head_position(game)
    if not ok:
        all_pass = False
    meas = f"sx={hsx:.1f} sy={hsy:.1f}"
    thresh = f"x={x_lo}–{x_hi} y={y_lo}–{y_hi}"
    lines.append(_table_line("  head_position", meas, thresh, ok))

    # 4 – FPS
    fps, elapsed = measure_fps(game, FPS_FRAMES)
    ok = fps >= CHECKS["fps_min"]
    if not ok:
        all_pass = False
    lines.append(_table_line("  fps", f"{fps:.1f}", f"≥ {CHECKS['fps_min']}", ok))

    # 4 – Summary table
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
