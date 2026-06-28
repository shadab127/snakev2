import pygame
import math
from config import *
from game_state import GameState
from utils import hex_to_pixel, all_hexes


def draw_ui(surf, shake_x, shake_y, game):
    panel_w, panel_h = 200, 72
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    for y in range(panel_h):
        t = y / panel_h
        a = int(160 * (1 - t * 0.3))
        c = (5, 8, 22, a)
        pygame.draw.line(panel, c, (0, y), (panel_w, y))
    surf.blit(panel, (20 + shake_x, 18 + shake_y))

    pygame.draw.rect(surf, (50, 130, 90, 120), (20 + shake_x, 18 + shake_y, panel_w, panel_h), 1, border_radius=6)
    pygame.draw.rect(surf, (80, 180, 130, 30), (22 + shake_x, 20 + shake_y, panel_w - 4, panel_h - 4), 1, border_radius=5)

    score_text = f"{game.score}"
    text_surf = game.font_score.render(score_text, True, TEXT_WHITE)
    score_glow = game.font_score.render(score_text, True, (40, 180, 120, 60))
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        surf.blit(score_glow, (36 + shake_x + dx, 26 + shake_y + dy))
    surf.blit(text_surf, (36 + shake_x, 26 + shake_y))

    pygame.draw.circle(surf, TEXT_GLOW, (32 + shake_x, 36 + shake_y), 3)
    pygame.draw.circle(surf, (100, 255, 180, 100), (32 + shake_x, 36 + shake_y), 5, 1)

    if game.high_score > 0:
        hs_text = f"BEST: {game.high_score}"
        hs_surf = game.font_micro.render(hs_text, True, TEXT_DIM)
        surf.blit(hs_surf, (36 + shake_x, 54 + shake_y))


def draw_pause_overlay(surf, game):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surf.blit(overlay, (0, 0))

    pane_w, pane_h = 320, 180
    pane = pygame.Surface((pane_w, pane_h), pygame.SRCALPHA)
    for y in range(pane_h):
        t = y / pane_h
        a = int(200 * (1 - abs(t - 0.5) * 0.4))
        c = (8, 12, 30, a)
        pygame.draw.line(pane, c, (0, y), (pane_w, y))

    px = (WIDTH - pane_w) // 2
    py = (HEIGHT - pane_h) // 2
    surf.blit(pane, (px, py))
    pygame.draw.rect(surf, (60, 140, 100, 100), (px, py, pane_w, pane_h), 1, border_radius=8)
    pygame.draw.rect(surf, (100, 200, 150, 40), (px + 2, py + 2, pane_w - 4, pane_h - 4), 1, border_radius=7)

    txt = game.font_large.render("PAUSED", True, TEXT_YELLOW)
    glow = game.font_large.render("PAUSED", True, (255, 200, 80, 60))
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        surf.blit(glow, (WIDTH // 2 - txt.get_width() // 2 + dx, HEIGHT // 2 - 55 + dy))
    r = txt.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 55))
    surf.blit(txt, r)

    hint = game.font_small.render("Press SPACE to resume", True, TEXT_WHITE)
    hr = hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 25))
    surf.blit(hint, hr)

    hint2 = game.font_micro.render("ESC to quit", True, TEXT_DIM)
    h2r = hint2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 55))
    surf.blit(hint2, h2r)


def draw_game_over(surf, game):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    surf.blit(overlay, (0, 0))

    pane_w, pane_h = 400, 260
    px = (WIDTH - pane_w) // 2
    py = (HEIGHT - pane_h) // 2
    pane = pygame.Surface((pane_w, pane_h), pygame.SRCALPHA)
    for y in range(pane_h):
        t = y / pane_h
        a = int(220 * (1 - abs(t - 0.5) * 0.5))
        r = int(12 * (1 - t))
        g = int(8 * (1 - t))
        b_val = int(25 * (1 + t * 0.5))
        c = (r, g, b_val, a)
        pygame.draw.line(pane, c, (0, y), (pane_w, y))
    surf.blit(pane, (px, py))
    pygame.draw.rect(surf, (200, 60, 60, 120), (px, py, pane_w, pane_h), 1, border_radius=10)
    pygame.draw.rect(surf, (255, 100, 80, 40), (px + 2, py + 2, pane_w - 4, pane_h - 4), 1, border_radius=9)

    title = game.font_large.render("GAME OVER", True, (255, 80, 80))
    title_glow = game.font_large.render("GAME OVER", True, (200, 40, 40, 80))
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)]:
        surf.blit(title_glow, (WIDTH // 2 - title.get_width() // 2 + dx, py + 30 + dy))
    tr = title.get_rect(center=(WIDTH // 2, py + 30))
    surf.blit(title, tr)

    score = game.font_med.render(f"Score: {game.score}", True, TEXT_WHITE)
    sr = score.get_rect(center=(WIDTH // 2, py + 90))
    surf.blit(score, sr)

    if game.score >= game.high_score and game.score > 0:
        best = game.font_small.render("NEW BEST!", True, TEXT_YELLOW)
        bg = game.font_small.render("NEW BEST!", True, (180, 150, 50, 60))
        for dx, dy in [(-1, 0), (1, 0)]:
            surf.blit(bg, (WIDTH // 2 - best.get_width() // 2 + dx, py + 125 + dy))
        br = best.get_rect(center=(WIDTH // 2, py + 125))
        surf.blit(best, br)

    hint = game.font_small.render("Press R or ENTER to restart", True, TEXT_WHITE)
    hr = hint.get_rect(center=(WIDTH // 2, py + 180))
    surf.blit(hint, hr)

    hint2 = game.font_micro.render("ESC to quit", True, TEXT_DIM)
    h2r = hint2.get_rect(center=(WIDTH // 2, py + 215))
    surf.blit(hint2, h2r)


def draw_start_screen(game):
    surf = game.screen
    surf.blit(game.bg_surf, (0, 0))
    surf.blit(game.star_surf, (0, 0))

    surf.blit(game._start_sun_surf, (WIDTH // 2 - 42, int(HEIGHT * 0.12 - 42)))

    title = game.font_large.render("SNAKE V2", True, TEXT_WHITE)
    gl = game.font_large.render("SNAKE V2", True, TEXT_GLOW)
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)]:
        surf.blit(gl, (WIDTH // 2 - title.get_width() // 2 + dx, HEIGHT // 2 - 85 + dy))
    tr = title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 85))
    surf.blit(title, tr)

    subtitle = game.font_small.render("3D Hex Grid - Enhanced Edition", True, TEXT_DIM)
    sr = subtitle.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
    surf.blit(subtitle, sr)

    instructions = [
        ("A / LEFT ARROW", "Turn left"),
        ("D / RIGHT ARROW", "Turn right"),
        ("SPACE", "Pause"),
        ("ESC", "Quit"),
    ]
    for i, (key, action) in enumerate(instructions):
        key_surf = game.font_micro.render(key, True, TEXT_GLOW)
        act_surf = game.font_micro.render(action, True, TEXT_DIM)
        kx = WIDTH // 2 - 120
        ax = WIDTH // 2 + 20
        iy = HEIGHT // 2 + 5 + i * 25
        surf.blit(key_surf, (kx, iy))
        surf.blit(act_surf, (ax, iy))

    hint = game.font_small.render("Press any key to start", True, TEXT_YELLOW)
    hr = hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 160))
    pulse = int(abs(math.sin(pygame.time.get_ticks() * 0.003)) * 120)
    hint.set_alpha(130 + pulse)
    surf.blit(hint, hr)


def draw_minimap(surf, snake, apple, game):
    size = MINIMAP_SIZE
    pad = MINIMAP_PADDING
    mini = pygame.Surface((size, size), pygame.SRCALPHA)
    mini.fill((0, 0, 0, MINIMAP_ALPHA))

    hexes = list(all_hexes())
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

    surf.blit(mini, (pad, pad))
