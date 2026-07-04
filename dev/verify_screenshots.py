"""Visual verification harness for SnakeV2 recovery track.

Captures screenshots at each game state, measures FPS with per-stage
timings, and records projection probe points so orientation bugs are
visible in numbers.

Usage:
    python dev/verify_screenshots.py [--frames N] [--steps N]

Output goes to dev/screenshots/:
    start_screen.png
    gameplay.png
    start_screen.png
    gameplay.png
    paused.png
    game_over.png
    fps_report.txt
    probe_points.txt
"""

import os, sys, time, math, random, argparse

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from game_state import GameState
from config import (WIDTH, HEIGHT, RENDER_FPS, FIXED_DT, DIR_VECTORS,
                     BASE_MOVE_INTERVAL, MIN_MOVE_INTERVAL, SPEED_DECAY_PER_POINT)


OUT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)


def _drain_events():
    pygame.event.clear()


def capture_start_screen(game):
    """Render and save the title screen."""
    game.state = GameState.START
    game._menu_count = 3
    game.menu_selection = 0
    _drain_events()
    for _ in range(10):
        game.update(FIXED_DT)
    game.render()
    path = os.path.join(OUT_DIR, "start_screen.png")
    pygame.image.save(game.screen, path)
    print(f"  Saved {path}")
    return path


def _force_apple_in_front(game):
    """Place an apple on the tile directly in front of the snake head."""
    from utils import wrap_coords
    hq, hr = game.snake[0]
    dq, dr = DIR_VECTORS[game.direction]
    target = wrap_coords(hq + dq, hr + dr)
    if target not in game.snake:
        game.apple = target


def _play_random_turns(game, rng, steps):
    """Advance the game with random turns for a number of simulation steps."""
    turn_seq = [rng.choice(['L', 'R']) for _ in range(10000)]
    tidx = 0
    total = 0
    while total < steps and game.state == GameState.PLAYING:
        if turn_seq[tidx % len(turn_seq)] == 'L':
            game.turn_left()
        else:
            game.turn_right()
        tidx += 1
        interval = max(0.035, 0.15 - game.score * 0.0008)
        steps_needed = max(1, int(interval / FIXED_DT)) + 1
        for _ in range(steps_needed):
            if game.state == GameState.PLAYING:
                game.update(FIXED_DT)
        total += steps_needed
    return total


def capture_gameplay(game, steps=2500):
    """Play the game for N steps, then render and save."""
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain_events()

    rng = random.Random(42)

    for feed_attempt in range(3):
        _force_apple_in_front(game)
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - game.score * SPEED_DECAY_PER_POINT)
        steps_needed = int(interval / FIXED_DT) + 2
        for _ in range(steps_needed):
            if game.state == GameState.PLAYING:
                game.update(FIXED_DT)
            else:
                break
        if game.score > 0 or game.state != GameState.PLAYING:
            break

    _play_random_turns(game, rng, steps)

    game.render()
    path = os.path.join(OUT_DIR, "gameplay.png")
    pygame.image.save(game.screen, path)
    print(f"  Saved {path}  (score={game.score}, sim_steps={steps})")
    return path


def capture_paused(game):
    """Render and save the paused screen."""
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain_events()
    for _ in range(20):
        game.update(FIXED_DT)
    game.state = GameState.PAUSED
    game.menu_selection = 0
    game._menu_count = 3
    _drain_events()
    for _ in range(5):
        game.render()
    path = os.path.join(OUT_DIR, "paused.png")
    pygame.image.save(game.screen, path)
    print(f"  Saved {path}")
    return path


def capture_game_over(game):
    """Force game-over state and render the screen."""
    game.state = GameState.GAME_OVER
    score = max(game.score, 50)
    game.score = score
    game.high_score = max(game.high_score, score)
    game.score_count_up = game.score
    game.score_count_up_timer = 0
    game._countup_started = True
    game._menu_count = 3
    game.menu_selection = 0
    game.death_anim = {'timer': 0.0, 'phase': 'none'}
    game.grade_death_darken = 0.0
    game.fade_alpha = 0
    game.fade_target = 0
    game._transitioning = False
    _drain_events()
    for _ in range(5):
        game.render()
    path = os.path.join(OUT_DIR, "game_over.png")
    pygame.image.save(game.screen, path)
    print(f"  Saved {path}  (score={game.score})")
    return path


def _record_stage_timings(game):
    """Snapshot the _perf_timings dict from the last render."""
    timings = {}
    for k, v in game._perf_timings.items():
        timings[k] = v
    return timings


def measure_fps(game, num_frames=100):
    """Measure render-only FPS with post-processing toggled, plus per-stage timings."""
    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain_events()

    for _ in range(30):
        game.update(FIXED_DT)

    results = {}
    stage_results = {}

    configs = [
        ("post_on", None),
        ("post_off", {"bloom": False, "tone_map": False, "god_rays": False,
                      "vignette": False, "film_grain": False}),
    ]

    for label, settings_override in configs:
        if settings_override:
            game.settings.update(settings_override)
        else:
            game.settings.update({
                "bloom": True, "tone_map": True, "god_rays": True,
                "vignette": True, "film_grain": True,
            })

        for _ in range(5):
            game.render()
        start = time.perf_counter()
        for _ in range(num_frames):
            game.render()
        elapsed = time.perf_counter() - start
        fps = num_frames / elapsed if elapsed > 0 else 0
        results[label] = (fps, elapsed)
        stage_results[label] = _record_stage_timings(game)

    return results, stage_results


def probe_points(game):
    """Project a handful of known world points and print screen coordinates."""
    from utils import hex_to_pixel

    game.state = GameState.PLAYING
    game.reset()
    game.audio._ok = False
    _drain_events()

    for _ in range(10):
        game.update(FIXED_DT)
    game.render()

    camera = game.camera
    points = []

    cx, cy = hex_to_pixel(0, 0)
    sx, sy, sd = camera.project(cx, cy, 0)
    points.append(("grid_center", 0, 0, 0, sx, sy, sd))

    sx, sy, sd = camera.project(cx, cy, 10)
    points.append(("grid_center_above", 0, 0, 10, sx, sy, sd))

    if game.snake:
        hx, hy = hex_to_pixel(*game.snake[0])
        sx, sy, sd = camera.project(hx, hy, 2)
        points.append(("snake_head", game.snake[0][0], game.snake[0][1], 2, sx, sy, sd))

    for _ in range(30):
        game.update(FIXED_DT)

    if game.apple:
        ax, ay = hex_to_pixel(*game.apple)
        sx, sy, sd = camera.project(ax, ay, 0.5)
        points.append(("apple", game.apple[0], game.apple[1], 0.5, sx, sy, sd))

    return points


def format_probe(probes):
    lines = ["World Point          (q,  r,  z)    ->  Screen (x,    y,    depth)"]
    lines.append("-" * 70)
    lines.append("")
    for name, q, r, z, sx, sy, sd in probes:
        sx_str = f"{sx:7.1f}" if sx >= -999 else "  OFFSCR"
        sy_str = f"{sy:7.1f}" if sy >= -999 else "  OFFSCR"
        sd_str = f"{sd:7.1f}" if sd <= 99999 else "  INF   "
        lines.append(f"{name:20s} ({q:2d}, {r:2d}, {z:3.0f})  ->  ({sx_str}, {sy_str}, {sd_str})")
    lines.append("")
    lines.append("INVERTED-Z marker: grid_center_above y > grid_center y means upside-down.")
    return "\n".join(lines)


def write_fps_report(fps_results, stage_results, num_frames):
    lines = [
        "SnakeV2 FPS Report",
        "=" * 50,
        f"Resolution: {WIDTH}x{HEIGHT}",
        f"",
    ]
    for label, (fps, elapsed) in fps_results.items():
        lines.append(f"{label:12s}: {fps:7.1f} FPS  ({elapsed:.2f}s for {num_frames} frames)")
    lines.append("")
    lines.append("Per-stage timings (average ms/frame):")
    lines.append("-" * 40)
    for label in fps_results:
        lines.append(f"  [{label}]")
        stages = stage_results[label]
        if stages:
            total = sum(stages.values())
            for skey in ["tiles", "snake", "particles", "post", "ui", "total"]:
                val = stages.get(skey, 0)
                pct = f"({val/total*100:.0f}%)" if total > 0 else ""
                lines.append(f"    {skey:12s}: {val:7.2f} ms  {pct}")
    path = os.path.join(OUT_DIR, "fps_report.txt")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Saved {path}")
    for line in lines:
        print(f"    {line}")


def write_probe_report(probes):
    text = format_probe(probes)
    path = os.path.join(OUT_DIR, "probe_points.txt")
    with open(path, "w") as f:
        f.write(text + "\n")
    print(f"  Saved {path}")
    print(text)


def main():
    parser = argparse.ArgumentParser(description="SnakeV2 visual verification harness")
    parser.add_argument("--frames", type=int, default=100,
                        help="Number of frames for FPS measurement (default: 100)")
    parser.add_argument("--steps", type=int, default=2500,
                        help="Simulation steps for gameplay screenshot (default: 2500)")
    args = parser.parse_args()

    from main import SnakeGame

    game = SnakeGame()
    game.audio._ok = False
    _drain_events()

    for _ in range(5):
        game.render()

    print("\n=== Capturing start screen ===")
    capture_start_screen(game)

    print("\n=== Capturing gameplay ===")
    capture_gameplay(game, steps=args.steps)

    print("\n=== Capturing paused ===")
    capture_paused(game)

    print("\n=== Capturing game over ===")
    capture_game_over(game)

    print("\n=== Measuring FPS ===")
    fps_results, stage_results = measure_fps(game, num_frames=args.frames)
    write_fps_report(fps_results, stage_results, args.frames)

    print("\n=== Probe points ===")
    probes = probe_points(game)
    write_probe_report(probes)

    print(f"\nAll outputs in {OUT_DIR}/")
    pygame.quit()


if __name__ == "__main__":
    main()
