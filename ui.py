import pygame
import math
from config import *
from game_state import GameState
from utils import hex_to_pixel, all_hexes


def _draw_text_with_shadow(surf, font, text, color, rect, shadow_alpha=0, shadow_offset=1):
    txt = font.render(text, True, color)
    if shadow_alpha > 0:
        shadow = font.render(text, True, (0, 0, 0))
        shadow.set_alpha(shadow_alpha)
        surf.blit(shadow, (rect.x + shadow_offset, rect.y + shadow_offset))
    surf.blit(txt, rect)


def _draw_panel(surf, x, y, w, h, alpha=200, r=8, g=12, b=30, border_color=(60, 140, 100), border_alpha=100):
    pane = pygame.Surface((w, h), pygame.SRCALPHA)
    for py in range(h):
        t = py / h
        a = int(alpha * (1 - abs(t - 0.5) * 0.4))
        c = (r, g, b, a)
        pygame.draw.line(pane, c, (0, py), (w, py))
    surf.blit(pane, (x, y))
    pygame.draw.rect(surf, (*border_color, border_alpha), (x, y, w, h), 1, border_radius=8)
    pygame.draw.rect(surf, (*border_color, 40), (x + 2, y + 2, w - 4, h - 4), 1, border_radius=7)


def _draw_menu_items(surf, items, selection, x, y, game, spacing=42, align_center=True, return_rects=False, shadow_alpha=0):
    rects = []
    for i, (label, sub_label) in enumerate(items):
        is_selected = i == selection
        font = game.font_small if not is_selected else game.font_med
        color = TEXT_GLOW if is_selected else TEXT_DIM
        txt = font.render(label, True, color)
        iy = y + i * spacing
        r = txt.get_rect(center=(x, iy)) if align_center else txt.get_rect(midleft=(x, iy))
        if shadow_alpha > 0 and not is_selected:
            shadow = font.render(label, True, (0, 0, 0))
            shadow.set_alpha(shadow_alpha)
            surf.blit(shadow, (r.x + 1, r.y + 1))
        if is_selected:
            glow = game.font_med.render(label, True, (40, 180, 120, 60))
            glow_r = txt.get_rect(center=(x, iy))
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)]:
                surf.blit(glow, (glow_r.x + dx, glow_r.y + dy))
            indicator = game.font_micro.render(">", True, TEXT_GLOW)
            if align_center:
                surf.blit(indicator, (r.left - 22, r.y + 2))
            else:
                surf.blit(indicator, (x - 22, r.y + 2))
        surf.blit(txt, r)
        if sub_label:
            sub = game.font_micro.render(sub_label, True, TEXT_DIM)
            sr = sub.get_rect(midleft=(r.right + 12, r.centery))
            surf.blit(sub, sr)
        rects.append(r.inflate(24, 6))
    if return_rects:
        return rects


def draw_ui(surf, shake_x, shake_y, game):
    panel_w, panel_h = 200, 72
    px = 20 + shake_x
    py = 18 + shake_y
    _draw_panel(surf, px, py, panel_w, panel_h, alpha=160)

    # Score with pop animation
    score_text = f"{game.score}"
    pop_scale = 1.0
    if game.score_pop_timer > 0:
        t = game.score_pop_timer / SCORE_POP_DURATION
        pop_scale = 1.0 + 0.35 * math.sin(t * math.pi)
        pop_scale = max(1.0, pop_scale)
    score_sz = int(30 * pop_scale)
    score_font = pygame.font.Font(FONT_NAME, score_sz)
    text_surf = score_font.render(score_text, True, TEXT_WHITE)
    score_glow = score_font.render(score_text, True, (40, 180, 120, 60))
    off = int(2 * pop_scale)
    for dx, dy in [(-off, 0), (off, 0), (0, -off), (0, off)]:
        surf.blit(score_glow, (36 + shake_x + dx, 26 + shake_y + dy))
    surf.blit(text_surf, (36 + shake_x, 26 + shake_y))

    # Points dot
    pygame.draw.circle(surf, TEXT_GLOW, (32 + shake_x, 36 + shake_y), 3)
    pygame.draw.circle(surf, (100, 255, 180, 100), (32 + shake_x, 36 + shake_y), 5, 1)

    # High score
    if game.high_score > 0:
        hs_text = f"BEST: {game.high_score}"
        hs_surf = game.font_micro.render(hs_text, True, TEXT_DIM)
        surf.blit(hs_surf, (36 + shake_x, 54 + shake_y))

    # Speed indicator
    speed = game._speed_ratio
    dots = SPEED_INDICATOR_DOTS
    filled = int(speed * dots)
    dot_x = 36 + shake_x
    dot_y = 68 + shake_y
    for d in range(dots):
        c = TEXT_GLOW if d < filled else (40, 60, 50, 120)
        pygame.draw.circle(surf, c, (dot_x + d * 7, dot_y), 2)
        if d < filled:
            pygame.draw.circle(surf, (100, 255, 180, 80), (dot_x + d * 7, dot_y), 3, 1)


def draw_pause_menu(surf, game, menu_selection):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, PAUSE_BLUR_ALPHA))
    surf.blit(overlay, (0, 0))

    pane_w, pane_h = 300, 260
    px = (WIDTH - pane_w) // 2
    py = (HEIGHT - pane_h) // 2
    _draw_panel(surf, px, py, pane_w, pane_h)

    txt = game.font_large.render("PAUSED", True, TEXT_YELLOW)
    glow = game.font_large.render("PAUSED", True, (255, 200, 80, 60))
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)]:
        surf.blit(glow, (WIDTH // 2 - txt.get_width() // 2 + dx, py + 20 + dy))
    r = txt.get_rect(center=(WIDTH // 2, py + 20))
    surf.blit(txt, r)

    # Score display in pause
    score_s = game.font_small.render(f"Score: {game.score}", True, TEXT_WHITE)
    sr = score_s.get_rect(center=(WIDTH // 2, py + 65))
    surf.blit(score_s, sr)

    # Menu items
    items = [
        ("Resume", "SPACE"),
        ("Settings", ""),
        ("Restart", ""),
        ("Quit", "ESC"),
    ]
    selected = min(menu_selection, len(items) - 1) if menu_selection >= 0 else 0
    _draw_menu_items(surf, items, selected, WIDTH // 2, py + 100, game, spacing=40)

    game._menu_count = len(items)
    game._menu_selection = selected


def draw_game_over(surf, game, menu_selection, score_count_up, new_record_bounce_timer):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    surf.blit(overlay, (0, 0))

    pane_w, pane_h = 420, 320
    px = (WIDTH - pane_w) // 2
    py = (HEIGHT - pane_h) // 2
    _draw_panel(surf, px, py, pane_w, pane_h, r=12, g=8, b=25, border_color=(200, 60, 60))

    title = game.font_large.render("GAME OVER", True, (255, 80, 80))
    title_glow = game.font_large.render("GAME OVER", True, (200, 40, 40, 80))
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)]:
        surf.blit(title_glow, (WIDTH // 2 - title.get_width() // 2 + dx, py + 20 + dy))
    tr = title.get_rect(center=(WIDTH // 2, py + 20))
    surf.blit(title, tr)

    # Animated score count-up
    count = game.score if score_count_up >= game.score else score_count_up
    score_text = f"Score: {count}"
    score_surf = game.font_med.render(score_text, True, TEXT_WHITE)
    sr = score_surf.get_rect(center=(WIDTH // 2, py + 80))
    surf.blit(score_surf, sr)

    # NEW RECORD bounce
    if new_record_bounce_timer > 0:
        bounce_t = 1.0 - new_record_bounce_timer / 1.5
        bounce_scale = 1.0 + 0.3 * abs(math.sin(bounce_t * math.pi * 2))
        bounce_sz = int(22 * bounce_scale)
        bounce_font = pygame.font.Font(FONT_NAME, bounce_sz)
        best = bounce_font.render("NEW RECORD!", True, TEXT_YELLOW)
        bg = bounce_font.render("NEW RECORD!", True, (180, 150, 50, 60))
        bx = WIDTH // 2
        by = int(py + 120)
        for dx, dy in [(-1, 0), (1, 0)]:
            surf.blit(bg, (bx - best.get_width() // 2 + dx, by + dy))
        br = best.get_rect(center=(bx, by))
        surf.blit(best, br)

    # High score
    hs = game.font_small.render(f"Best: {game.high_score}", True, TEXT_DIM)
    hs_r = hs.get_rect(center=(WIDTH // 2, py + 155))
    surf.blit(hs, hs_r)

    count_up_done = score_count_up >= game.score or game.score == 0
    if count_up_done:
        items = [
            ("Restart", "R / ENTER"),
            ("View Stats", ""),
            ("Title Screen", "ESC"),
        ]
        selected = min(menu_selection, len(items) - 1) if menu_selection >= 0 else 0
        _draw_menu_items(surf, items, selected, WIDTH // 2, py + 185, game, spacing=40)
        game._menu_count = len(items)
        game._menu_selection = selected
    else:
        game._menu_count = 0
        game._menu_selection = -1


def draw_title_screen(surf, game, menu_selection, time_float):
    items = [
        ("Play", ""),
        ("Settings", ""),
        ("Quit", ""),
    ]

    sa = TEXT_SHADOW_ALPHA

    # Logo — draw once with glow behind it (no redundant overlay)
    logo = game.font_large.render("SNAKE V2", True, TEXT_WHITE)
    glow = game.font_large.render("SNAKE V2", True, TEXT_GLOW)
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0), (-3, 0), (3, 0)]:
        surf.blit(glow, (WIDTH // 2 - logo.get_width() // 2 + dx, 120 + dy))
    lr = logo.get_rect(center=(WIDTH // 2, 120))
    _draw_text_with_shadow(surf, game.font_large, "SNAKE V2", TEXT_WHITE, lr, shadow_alpha=sa)

    subtitle = game.font_small.render("3D Hex Grid - Enhanced Edition", True, TEXT_DIM)
    sr = subtitle.get_rect(center=(WIDTH // 2, 175))
    _draw_text_with_shadow(surf, game.font_small, "3D Hex Grid - Enhanced Edition", TEXT_DIM, sr, shadow_alpha=sa)

    # Stats line
    stats = game.persistence.get_stats()
    hs = game.persistence.get_high_score()
    if hs > 0 or stats['games_played'] > 0:
        st = f"Best: {hs}  |  Games: {stats['games_played']}  |  Longest: {stats['longest_snake']}"
        stats_surf = game.font_micro.render(st, True, TEXT_DIM)
        ssr = stats_surf.get_rect(center=(WIDTH // 2, 200))
        _draw_text_with_shadow(surf, game.font_micro, st, TEXT_DIM, ssr, shadow_alpha=sa)

    menu_y = 260
    selected = min(menu_selection, len(items) - 1) if menu_selection >= 0 else 0
    _draw_menu_items(surf, items, selected, WIDTH // 2, menu_y, game, spacing=50, shadow_alpha=sa)

    # Footer hint
    hint = game.font_micro.render("Arrow keys to navigate, Enter to select", True, TEXT_DIM)
    hr = hint.get_rect(center=(WIDTH // 2, HEIGHT - 40))
    _draw_text_with_shadow(surf, game.font_micro, "Arrow keys to navigate, Enter to select", TEXT_DIM, hr, shadow_alpha=sa)

    game._menu_count = len(items)
    game._menu_selection = selected


def draw_settings_screen(surf, game, menu_selection, settings, time_float, from_pause):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surf.blit(overlay, (0, 0))

    pane_w, pane_h = 500, 520
    px = (WIDTH - pane_w) // 2
    py = (HEIGHT - pane_h) // 2
    _draw_panel(surf, px, py, pane_w, pane_h, alpha=200, border_color=(60, 140, 200))

    title = game.font_large.render("SETTINGS", True, TEXT_GLOW)
    glow = game.font_large.render("SETTINGS", True, (40, 180, 120, 60))
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)]:
        surf.blit(glow, (WIDTH // 2 - title.get_width() // 2 + dx, py + 15 + dy))
    tr = title.get_rect(center=(WIDTH // 2, py + 15))
    surf.blit(title, tr)

    # Build menu items
    vol_suffix = lambda v: f"[{int(v * 100)}%]"
    toggle_suffix = lambda v: "[ON]" if v else "[OFF]"

    items = [
        (f"Music    {vol_suffix(settings['music_volume'])}", "<  >"),
        (f"SFX      {vol_suffix(settings['sfx_volume'])}", "<  >"),
        (f"Ambience {vol_suffix(settings['ambience_volume'])}", "<  >"),
        (f"Bloom    {toggle_suffix(settings['bloom'])}", ""),
        (f"Tone Map {toggle_suffix(settings['tone_map'])}", ""),
        (f"God Rays {toggle_suffix(settings['god_rays'])}", ""),
        (f"Vignette {toggle_suffix(settings['vignette'])}", ""),
        (f"Show FPS {toggle_suffix(settings['show_fps'])}", ""),
        (f"Back", ""),
    ]

    selected = min(menu_selection, len(items) - 1) if menu_selection >= 0 else 0
    _draw_menu_items(surf, items, selected, px + 30, py + 65, game, spacing=38, align_center=False)

    hint = game.font_micro.render("< > adjust values     ENTER toggles     ESC to go back", True, TEXT_DIM)
    hr = hint.get_rect(center=(WIDTH // 2, py + pane_h - 25))
    surf.blit(hint, hr)

    game._menu_count = len(items)
    game._menu_selection = selected


def draw_minimap(surf, snake, apple, game):
    size = MINIMAP_SIZE
    pad = MINIMAP_PADDING
    mx = WIDTH - size - pad
    my = HEIGHT - size - pad
    mini = pygame.Surface((size, size), pygame.SRCALPHA)
    mini.fill((5, 8, 22, MINIMAP_ALPHA))

    hexes = all_hexes()
    if not hexes:
        return

    coords = [hex_to_pixel(q, r) for q, r in hexes]
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    range_x = max_x - min_x
    range_y = max_y - min_y
    if range_x == 0:
        range_x = 1
    if range_y == 0:
        range_y = 1
    margin = 6
    draw_size = size - 2 * margin
    scale = min(draw_size / range_x, draw_size / range_y) * 0.9

    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2

    snake_set = set(snake) if snake else set()

    for q, r in hexes:
        px, py = hex_to_pixel(q, r)
        dx = (px - cx) * scale + size / 2
        dy = (py - cy) * scale + size / 2
        if (q, r) == apple:
            color = (255, 60, 60)
            r_dot = 4
        elif (q, r) in snake_set:
            color = (80, 255, 120)
            r_dot = 3
        else:
            color = (60, 120, 90)
            r_dot = 2
        pygame.draw.circle(mini, color, (int(dx), int(dy)), r_dot)

    surf.blit(mini, (mx, my))
    pygame.draw.rect(surf, (50, 130, 90, 120), (mx, my, size, size), 1, border_radius=4)
    pygame.draw.rect(surf, (80, 180, 130, 30), (mx + 2, my + 2, size - 4, size - 4), 1, border_radius=3)


def draw_stats_overlay(surf, game):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 220))
    surf.blit(overlay, (0, 0))

    pane_w, pane_h = 460, 440
    px = (WIDTH - pane_w) // 2
    py = (HEIGHT - pane_h) // 2
    _draw_panel(surf, px, py, pane_w, pane_h, alpha=200, border_color=(60, 140, 200))

    title = game.font_med.render("STATISTICS", True, TEXT_GLOW)
    tr = title.get_rect(center=(WIDTH // 2, py + 25))
    surf.blit(title, tr)

    stats = game.persistence.get_stats()
    top_scores = game.persistence.get_top_scores()

    lines = [
        f"Games Played:    {stats['games_played']}",
        f"Apples Eaten:    {stats['apples_eaten']}",
        f"Total Play Time: {_fmt_time(stats['total_play_time'])}",
        f"Longest Snake:   {stats['longest_snake']}",
    ]

    y_off = py + 60
    for line in lines:
        ls = game.font_small.render(line, True, TEXT_WHITE)
        surf.blit(ls, (px + 40, y_off))
        y_off += 30

    # Top scores
    y_off += 10
    hdr = game.font_small.render("Best Scores", True, TEXT_YELLOW)
    surf.blit(hdr, (px + 40, y_off))
    y_off += 30
    if top_scores:
        for i, entry in enumerate(top_scores):
            ds = game.font_micro.render(
                f"{i + 1}.  {entry['score']}  ({_fmt_date(entry['date'])})",
                True, TEXT_DIM,
            )
            surf.blit(ds, (px + 50, y_off))
            y_off += 22
    else:
        no = game.font_micro.render("No scores yet", True, TEXT_DIM)
        surf.blit(no, (px + 50, y_off))

    hint = game.font_micro.render("Press ESC or ENTER to go back", True, TEXT_DIM)
    hr = hint.get_rect(center=(WIDTH // 2, py + pane_h - 20))
    surf.blit(hint, hr)


def _fmt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"


def _fmt_date(iso_str):
    try:
        parts = iso_str.split('T')[0].split('-')
        return f"{parts[1]}/{parts[2]}/{parts[0][2:]}"
    except Exception:
        return iso_str[:10]


def draw_debug_overlay(surf, game):
    timings = game._perf_timings
    fps = game.clock.get_fps()

    lines = [
        f"FPS: {fps:.1f}",
        f"Tiles: {timings.get('tiles', 0):.2f}ms",
        f"Snake: {timings.get('snake', 0):.2f}ms",
        f"Particles: {timings.get('particles', 0):.2f}ms",
        f"Post-FX: {timings.get('post', 0):.2f}ms",
        f"UI: {timings.get('ui', 0):.2f}ms",
        f"Total: {timings.get('total', 0):.2f}ms",
    ]

    if hasattr(game, '_frame_times') and len(game._frame_times) > 1:
        times = sorted(game._frame_times)
        n = len(times)
        avg_t = sum(times) / n
        p95 = times[int(n * 0.95)]
        max_t = times[-1]
        lines.append(f"FT avg={avg_t:.1f}ms p95={p95:.1f}ms max={max_t:.1f}ms ({n})")

    panel_w = 220
    panel_h = 20 + len(lines) * 20

    px = WIDTH - panel_w - 10
    py = 10
    _draw_panel(surf, px, py, panel_w, panel_h, alpha=160)

    for i, line in enumerate(lines):
        color = TEXT_WHITE if i == 0 else TEXT_DIM
        if i == 0:
            label_surf = game.font_micro.render(line, True, TEXT_GLOW)
        else:
            label_surf = game.font_micro.render(line, True, color)
        surf.blit(label_surf, (px + 8, py + 8 + i * 20))
