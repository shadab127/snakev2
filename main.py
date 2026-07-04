import pygame
import math
import random
import sys
import time
import struct
from collections import deque
try:
    import numpy as np
except ImportError:
    np = None
from config import *
from game_state import GameState
from utils import (perlin_noise, catmull_rom, hex_side_normal, hex_to_pixel,
                   hex_corners, all_hexes, in_bounds, lerp_color,
                   mul_color, add_color, screen_shake_offset, compute_tile_ao,
                   dot3, tile_noise, generate_soft_shadow, _perlin_cache,
                   wrap_coords, compute_sun_light, compute_lighting, compute_sky_color,
                   sample_spline_path)
from particle import Particle, ParticlePool
from resources import ResourceManager
from gl_renderer import GLRenderer
from camera import Camera
from ui import draw_ui, draw_pause_menu, draw_game_over, draw_title_screen, draw_settings_screen, draw_minimap
from audio import AudioManager
from persistence import PersistenceManager
from __version__ import __version__
from resources import generate_app_icon

_CLI_ARGS = {}


def _parse_cli_args():
    global _CLI_ARGS
    _CLI_ARGS = {'fullscreen': False, 'no_gl': False}
    for arg in sys.argv[1:]:
        if arg == '--version':
            print(f'SnakeV2 v{__version__}')
            sys.exit(0)
        elif arg == '--fullscreen':
            _CLI_ARGS['fullscreen'] = True
        elif arg == '--windowed':
            _CLI_ARGS['fullscreen'] = False
        elif arg == '--no-gl':
            _CLI_ARGS['no_gl'] = True
        elif arg in ('-h', '--help'):
            print('Usage: snakev2 [--windowed] [--fullscreen] [--no-gl] [--version]')
            sys.exit(0)


class SnakeGame:
    def __init__(self):
        try:
            pygame.init()
        except pygame.error as e:
            print("FATAL: Failed to initialize pygame.")
            print(f"       {e}")
            print("       Ensure a display is available or use SDL_VIDEODRIVER=dummy.")
            sys.exit(1)

        self.clock = pygame.time.Clock()
        self.start_time = time.time()
        flags = pygame.SCALED | pygame.RESIZABLE
        if _CLI_ARGS.get('fullscreen'):
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        except pygame.error as e:
            print("FATAL: Could not create display window.")
            print(f"       {e}")
            sys.exit(1)
        pygame.display.set_caption(f'SnakeV2 v{__version__}')
        pygame.display.set_icon(generate_app_icon(32))

        self.resources = ResourceManager()
        self.audio = AudioManager()
        self.persistence = PersistenceManager()
        self.persistence.load()

        self.render_time = 0.0
        self.move_timer = 0
        self.move_lerp = 0.0
        self.prev_snake_positions = {}
        self.smooth_positions = {}
        self.particles = ParticlePool(MAX_PARTICLES)
        self.path_history = deque(maxlen=MAX_PATH_LENGTH)
        self.eat_anim = {'timer': 0, 'bulge_idx': -1, 'bulge_progress': 0}
        self.death_anim = {'timer': 0, 'phase': 'none'}
        self.apple_anim = {'spawn_timer': 0, 'was_spawned': False}
        self.blink_timer = random.uniform(2, 5)
        self.eat_flash = 0
        self.screen_shake = 0
        self.ambient_time = 0
        self.bloom_layer = pygame.Surface((WIDTH // 2, HEIGHT // 2), pygame.SRCALPHA)

        self._dirty_rects = []
        self._prev_dirty_rects = []
        self._full_redraw_requested = True
        self._debug_overlay = False
        self._perf_timings = {}

        self.water_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._tile_cache = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._tile_cache_valid = False
        self.gl_renderer = GLRenderer()
        if _CLI_ARGS.get('no_gl'):
            self.gl_renderer.available = False
        self.camera = Camera()
        self.draw_cache = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        self.cloud_surf_cache = pygame.Surface((WIDTH, HEIGHT // 2), pygame.SRCALPHA)

        self._warned_no_numpy = False
        self._wrap_frame = False

        self._last_camera_px = 0.0
        self._last_camera_py = 0.0
        self._last_tile_camera_px = 0.0
        self._last_tile_camera_py = 0.0
        self._camera_moved_threshold = 3.5
        self._ground_cache_valid = False

        self.grade_warm_flash = 0.0
        self.grade_cool_shift = 0.0
        self.grade_death_darken = 0.0
        self.grade_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        self.birds = []
        for _ in range(AMBIENT_BIRD_COUNT):
            self._spawn_bird()

        for q, r in all_hexes():
            tile_noise(q, r)
        _perlin_cache.clear()

        self.high_score = self.persistence.get_high_score()
        self._game_start_time = time.time()
        self._apples_eaten_this_game = 0
        self._max_snake_len_this_game = 3
        self._game_recorded = False
        self._show_stats = False
        self.reset()
        self.state = GameState.START

        # Phase 12 — Menus, Settings & HUD
        self.menu_selection = 0
        self._menu_count = 0
        self.fade_alpha = 0
        self.fade_target = 0
        self._transition_target = None
        self._transition_reset = False
        self._transitioning = False
        self.score_pop_timer = 0
        self._prev_score = 0
        self.score_count_up = 0
        self.score_count_up_timer = 0
        self.new_record_bounce_timer = 0
        self._settings_previous_state = None
        self._countup_started = False
        self._last_mouse_pos = (0, 0)
        self.settings = {
            'music_volume': MUSIC_VOLUME,
            'sfx_volume': SFX_VOLUME,
            'ambience_volume': AMBIENCE_VOLUME,
            'bloom': POST_BLOOM_ENABLED,
            'tone_map': POST_TONE_MAP_ENABLED,
            'god_rays': POST_GOD_RAYS_ENABLED,
            'vignette': POST_VIGNETTE_ENABLED,
            'show_fps': False,
        }
        saved_settings = self.persistence.get_settings()
        if saved_settings:
            for k, v in saved_settings.items():
                if k in self.settings:
                    self.settings[k] = v
            self.audio.music_volume = self.settings['music_volume']
            self.audio.sfx_volume = self.settings['sfx_volume']
            self.audio.ambience_volume = self.settings['ambience_volume']

    def __getattr__(self, name):
        try:
            return getattr(self.resources, name)
        except AttributeError:
            raise AttributeError(f"'SnakeGame' object has no attribute '{name}'")

    def _add_dirty_rect(self, x, y, w, h):
        r = pygame.Rect(x, y, w, h)
        r.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
        self._dirty_rects.append(r)

    def _request_full_redraw(self):
        self._full_redraw_requested = True

    def _merge_rects(self, rects):
        if not rects:
            return []
        merged = []
        for r in sorted(rects, key=lambda x: (x.x, x.y)):
            if not merged:
                merged.append(r.copy())
            else:
                last = merged[-1]
                if last.colliderect(r) or last.inflate(10, 10).colliderect(r):
                    last.union_ip(r)
                else:
                    merged.append(r.copy())
        return merged

    def _compute_dirty_rects(self, time_float, shake_x, shake_y):
        rects = []
        water_top = int(HEIGHT * 0.45)
        rects.append(pygame.Rect(0, water_top, WIDTH, HEIGHT - water_top))
        if self.apple:
            q, r = self.apple
            ax, ay = hex_to_pixel(q, r)
            sx, sy, _ = self.camera.project(ax, ay, 0.5)
            ar = int(HEX_SIZE * 1.2)
            rects.append(pygame.Rect(sx + shake_x - ar, sy + shake_y - ar, ar * 2, ar * 2))
        positions = getattr(self, '_spline_positions', None)
        if positions and len(positions) == len(self.snake):
            for px, py, _, _ in positions:
                sx, sy, _ = self.camera.project(px, py, 0)
                sr = int(HEX_SIZE * 0.6)
                rects.append(pygame.Rect(sx + shake_x - sr, sy + shake_y - sr, sr * 2, sr * 2))
        else:
            for idx in range(len(self.snake)):
                q, r = self.snake[idx]
                cx, cy = hex_to_pixel(q, r)
                sx, sy, _ = self.camera.project(cx, cy, 0)
                sr = int(HEX_SIZE * 0.6)
                rects.append(pygame.Rect(sx + shake_x - sr, sy + shake_y - sr, sr * 2, sr * 2))
        for p in self.particles.alive:
            sx, sy, _ = self.camera.project(p.x, p.y, p.z)
            ps = int(p.current_size) + 8
            rects.append(pygame.Rect(sx + shake_x - ps, sy + shake_y - ps, ps * 2, ps * 2))
        rects.append(pygame.Rect(0, 0, WIDTH, int(HEIGHT * 0.35)))
        rects.append(pygame.Rect(20 + shake_x, 18 + shake_y, 200, 72))
        return rects

    def _build_ground(self):
        if self._ground_cache_valid:
            cx, cy = self.camera.eye[0], self.camera.eye[1]
            dx = cx - self._last_camera_px
            dy = cy - self._last_camera_py
            moved = math.hypot(dx, dy) >= self._camera_moved_threshold
            if not moved:
                return
        self._last_camera_px, self._last_camera_py = self.camera.eye[0], self.camera.eye[1]
        self.ground_cache.fill((0, 0, 0, 0))
        ground_cache = self._ground_static_cache
        for q, r in self._all_hexes_cache:
            gs = ground_cache[(q, r)]
            bot_pts = []
            for c_x, c_y, c_z in gs['bot_world']:
                sx_b, sy_b, _ = self.camera.project(c_x, c_y, c_z)
                bot_pts.append((sx_b, sy_b))
            pygame.draw.polygon(self.ground_cache, gs['color'], bot_pts)
        self._ground_cache_valid = True

    def _build_tile_cache(self):
        if self._tile_cache_valid and not self._full_redraw_requested:
            return
        if self.gl_renderer.available:
            self._tile_cache.fill((0, 0, 0, 0))
            self.gl_renderer.render_tiles_to_fbo(self, self.gl_renderer.fbo_tile)
            raw = self.gl_renderer.fbo_tile.read(components=4, alignment=1, dtype='f4')
            arr = bytearray(WIDTH * HEIGHT * 4)
            stride = 16
            pixel_count = WIDTH * HEIGHT
            for i in range(pixel_count):
                off = i * stride
                r = max(0.0, min(1.0, struct.unpack_from('<f', raw, off)[0]))
                g = max(0.0, min(1.0, struct.unpack_from('<f', raw, off + 4)[0]))
                b = max(0.0, min(1.0, struct.unpack_from('<f', raw, off + 8)[0]))
                a = max(0.0, min(1.0, struct.unpack_from('<f', raw, off + 12)[0]))
                pi = i * 4
                arr[pi] = int(r * 255.0)
                arr[pi + 1] = int(g * 255.0)
                arr[pi + 2] = int(b * 255.0)
                arr[pi + 3] = int(a * 255.0)
            surf = pygame.image.frombuffer(bytes(arr), (WIDTH, HEIGHT), 'RGBA')
            self._tile_cache.blit(surf, (0, 0))
            time_float = self.render_time
            tile_cache = self._tile_static_cache
            for q, r in self._all_hexes_cache:
                cx, cy = tile_cache[(q, r)]['center_world']
                sx, sy, depth = self.camera.project(cx, cy, 0)
                if sx < -TILE_CLIP_MARGIN or sx > WIDTH + TILE_CLIP_MARGIN:
                    continue
                if sy < -TILE_CLIP_MARGIN or sy > HEIGHT + TILE_CLIP_MARGIN:
                    continue
                self._draw_tile_decorations(self._tile_cache, q, r, time_float)
            self._tile_cache_valid = True
            self._full_redraw_requested = False
            return

        if self._tile_cache_valid:
            cx, cy = self.camera.eye[0], self.camera.eye[1]
            dx = cx - self._last_tile_camera_px
            dy = cy - self._last_tile_camera_py
            camera_moved = math.hypot(dx, dy) >= self._camera_moved_threshold
            if not camera_moved:
                return

        self._last_tile_camera_px, self._last_tile_camera_py = self.camera.eye[0], self.camera.eye[1]
        self._tile_cache.fill((0, 0, 0, 0))
        time_float = self.render_time
        tile_cache = self._tile_static_cache
        all_hex = self._all_hexes_cache
        tile_items = []
        for q, r in all_hex:
            cx_t, cy_t = tile_cache[(q, r)]['center_world']
            sx, sy, depth = self.camera.project(cx_t, cy_t, 0)
            if sx < -TILE_CLIP_MARGIN or sx > WIDTH + TILE_CLIP_MARGIN:
                continue
            if sy < -TILE_CLIP_MARGIN or sy > HEIGHT + TILE_CLIP_MARGIN:
                continue
            tile_items.append((depth, q, r))
        tile_items.sort(key=lambda x: x[0], reverse=True)
        for _, q, r in tile_items:
            self.draw_tile(self._tile_cache, q, r, time_float)
        self._tile_cache_valid = True

    def _draw_tile_decorations(self, surf, q, r, time_float):
        static = self._tile_static_cache[(q, r)]
        corners_world = static['corners_world']
        cx, cy = static['center_world']
        base_top_color_tuple = static['base_top_color']
        tex_variation = static['tex_variation']
        dist_factor = static['dist_factor']
        grass_seed = static['grass_seed']
        grass_blades = static['grass_blades']
        dist_from_center = static['dist_from_center']

        top_pts = []
        for c_x, c_y in corners_world:
            sx_t, sy_t, _ = self.camera.project(c_x, c_y, 0)
            top_pts.append((sx_t, sy_t))
        cx_proj = sum(p[0] for p in top_pts) / 6
        cy_proj = sum(p[1] for p in top_pts) / 6

        sun_factor = 0.85 + 0.15 * math.sin(time_float * SUN_ANGLE_SPEED + q * 0.5 + r * 0.3)
        ao = self._tile_ao_cache.get((q, r), 0.9)
        if (q, r) in self._snake_set:
            ao *= (1.0 - AO_TILE_OCCUPIED)

        edge_color = TILE_EDGE
        emissive_edge = 0
        if self.state == GameState.GAME_OVER:
            edge_color = (30, 15, 18)
        elif self.eat_flash > 0:
            flash = min(1.0, self.eat_flash / 0.2)
            edge_color = lerp_color(TILE_EDGE, TILE_GLOW, flash)
            emissive_edge = flash

        base_top_color = list(base_top_color_tuple)

        if (q, r) in self._snake_set:
            worn = 0.15
            base_top_color = list(lerp_color(tuple(base_top_color), TILE_TOP_LIGHT, worn))

        final_tri_color = tuple(base_top_color)
        _, _, depth = self.camera.project(cx, cy, 0)
        fog_t = max(0, min(1, (depth - FOG_NEAR) / (FOG_FAR - FOG_NEAR)))
        depth_fade = fog_t * DEPTH_FADE_STRENGTH
        if fog_t > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), self._fog_tint, fog_t * 0.35)
        if depth_fade > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), self._sky_hor, depth_fade)
        final_tri_color = mul_color(tuple(final_tri_color), tex_variation)

        pygame.draw.polygon(surf, edge_color, top_pts, max(1, int(1 + sun_factor * 0.5)))

        bevel_n = (0.0, 0.0, 1.0)
        bevel_light = self._ambient + (1.0 - self._ambient) * max(0.0, dot3(bevel_n, self._light_dir))
        bevel_brightness = bevel_light * sun_factor * ao
        inner_hl = mul_color(TILE_EDGE_HIGHLIGHT, 0.2 * bevel_brightness)
        if emissive_edge > 0:
            inner_hl = add_color(inner_hl, mul_color(TILE_EDGE_EMISSIVE, emissive_edge * 0.5))
        for i in range(6):
            j = (i + 1) % 6
            pygame.draw.line(surf, inner_hl, top_pts[i], top_pts[j], 2)

        crack_intensity = abs(static.get('noise', {}).get('crack', 0)) ** 3 * 0.3
        if crack_intensity > 0.05:
            crack_color = mul_color(final_tri_color, 0.7)
            for _ in range(int(crack_intensity * 3)):
                angle = random.uniform(0, math.tau)
                dist = random.uniform(1, HEX_SIZE * 0.4)
                ex = cx_proj + math.cos(angle) * dist
                ey = cy_proj + math.sin(angle) * dist
                pygame.draw.line(surf, crack_color, (int(cx_proj), int(cy_proj)), (int(ex), int(ey)), 1)

        rim_light = mul_color(TILE_EDGE_HIGHLIGHT, 0.25 * sun_factor * dist_factor * ao)
        for i in range(6):
            j = (i + 1) % 6
            edge_center_x = (top_pts[i][0] + top_pts[j][0]) / 2
            edge_center_y = (top_pts[i][1] + top_pts[j][1]) / 2
            edge_nx = top_pts[j][1] - top_pts[i][1]
            edge_ny = top_pts[i][0] - top_pts[j][0]
            el = math.hypot(edge_nx, edge_ny)
            if el > 0:
                edge_nx /= el
                edge_ny /= el
                rim = max(0.0, edge_nx * self._light_dir[0] + edge_ny * self._light_dir[1])
                if rim > 0.3:
                    pygame.draw.line(surf, rim_light, top_pts[i], top_pts[j], 1)

        if grass_seed > 0.1 and self.state != GameState.GAME_OVER:
            for blade in grass_blades:
                bx, by = blade['bx'], blade['by']
                blade_h, blade_w = blade['blade_h'], blade['blade_w']
                gc = blade['gc']
                sway = math.sin(time_float * 1.8 + bx * 0.4 + by * 0.3) * 2
                sx_b, sy_b, _ = self.camera.project(bx, by, 0)
                sx_t, sy_t, _ = self.camera.project(bx + sway, by, blade_h)
                pygame.draw.line(surf, gc, (int(sx_b), int(sy_b)), (int(sx_t), int(sy_t)), blade_w)
                if blade['has_flower']:
                    pygame.draw.circle(surf, blade['flower_color'], (int(sx_t), int(sy_t)), max(1, blade_w + 1))

        if dist_from_center > 0.7:
            rock_noise = static.get('noise', {}).get('detail', 0)
            if abs(rock_noise) > 0.2:
                rock_count = int(abs(rock_noise) * 3)
                for ri in range(rock_count):
                    ra = random.uniform(0, math.tau)
                    rd = random.uniform(0.3, 1.0) * HEX_SIZE
                    rx = cx_proj + math.cos(ra) * rd
                    ry = cy_proj + math.sin(ra) * rd
                    rs = random.randint(1, 3)
                    rc = mul_color(final_tri_color, random.uniform(0.6, 0.9))
                    pygame.draw.circle(surf, rc, (int(rx), int(ry)), rs)

    def reset(self):
        self.snake = [(0, 0), (-1, 0), (-2, 0)]
        self.direction = 0
        self.next_direction = 0
        self.apple = self._find_empty()
        self.score = 0
        self._prev_score = 0
        self.high_score = getattr(self, 'high_score', 0)
        self._game_start_time = time.time()
        self._apples_eaten_this_game = 0
        self._max_snake_len_this_game = len(self.snake)
        self._game_recorded = False
        self._show_stats = False
        self.state = GameState.PLAYING
        self.particles.clear()
        self.eat_flash = 0.0
        self.screen_shake = 0.0
        self.move_timer = 0
        self.move_lerp = 0
        self.smooth_positions = {}
        self.prev_snake_positions = {}
        self.path_history.clear()
        for sq, sr in self.snake:
            self.path_history.append((sq, sr))
        self.eat_anim = {'timer': 0, 'bulge_idx': -1, 'bulge_progress': 0}
        self.death_anim = {'timer': 0, 'phase': 'none'}
        self.apple_anim = {'spawn_timer': 0, 'was_spawned': False}
        self.blink_timer = random.uniform(2, 5)
        self._countup_started = False
        self.score_count_up_timer = 0
        self.score_count_up = 0
        self.new_record_bounce_timer = 0
        self._wrap_frame = False
        self.camera.snap_to(*self.snake[0], self.direction)
        self.audio.resume()

    def _spawn_bird(self):
        side = random.choice(['left', 'right', 'top'])
        if side == 'left':
            x, y = -40, random.uniform(20, HEIGHT * 0.35)
            vx, vy = random.uniform(0.6, 1.8), random.uniform(-0.15, 0.15)
        elif side == 'right':
            x, y = WIDTH + 40, random.uniform(20, HEIGHT * 0.35)
            vx, vy = random.uniform(-1.8, -0.6), random.uniform(-0.15, 0.15)
        else:
            x, y = random.uniform(0, WIDTH), -30
            vx, vy = random.uniform(-0.3, 0.3), random.uniform(0.4, 1.0)
        self.birds.append({
            'x': x, 'y': y, 'vx': vx, 'vy': vy,
            'size': random.uniform(6, 14),
            'phase': random.uniform(0, math.tau * 2),
            'flap_speed': random.uniform(4, 8),
        })

    def _update_birds(self, dt):
        for b in list(self.birds):
            b['x'] += b['vx'] * dt * 60
            b['y'] += b['vy'] * dt * 60
            if (b['x'] < -80 or b['x'] > WIDTH + 80 or b['y'] < -60 or b['y'] > HEIGHT * 0.4 + 60):
                self.birds.remove(b)
        while len(self.birds) < AMBIENT_BIRD_COUNT:
            self._spawn_bird()

    def _draw_birds(self, surf, time_float):
        for b in self.birds:
            wing_angle = math.sin(time_float * b['flap_speed'] + b['phase']) * 0.4
            s = b['size']
            bx, by = b['x'], b['y']
            c = (20, 25, 40, 120)
            pygame.draw.polygon(surf, c, [
                (bx, by),
                (bx - s * 0.5, by + s * 0.4 + wing_angle * s * 0.3),
                (bx - s * 0.15, by + s * 0.1),
            ])
            pygame.draw.polygon(surf, c, [
                (bx, by),
                (bx + s * 0.5, by + s * 0.4 + wing_angle * s * 0.3),
                (bx + s * 0.15, by + s * 0.1),
            ])

    def _find_empty(self):
        empty = [(q, r) for q, r in all_hexes()
                 if in_bounds(q, r) and (q, r) not in self.snake]
        return random.choice(empty) if empty else None

    def head(self):
        return self.snake[0]

    @property
    def _speed_ratio(self):
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - self.score * SPEED_DECAY_PER_POINT)
        return max(0.0, min(1.0, (BASE_MOVE_INTERVAL - interval) / (BASE_MOVE_INTERVAL - MIN_MOVE_INTERVAL)))

    def turn_left(self):
        self.next_direction = (self.direction - 1) % 6
        self.audio.play_slither(self._speed_ratio)

    def turn_right(self):
        self.next_direction = (self.direction + 1) % 6
        self.audio.play_slither(self._speed_ratio)

    def next_head_pos(self):
        q, r = self.snake[0]
        dq, dr = DIR_VECTORS[self.direction]
        return (q + dq, r + dr)

    def move_snake(self):
        old_dir = self.direction
        self.direction = self.next_direction
        q, r = self.next_head_pos()
        wrapped_q, wrapped_r = wrap_coords(q, r)
        wrapped = (q != wrapped_q) or (r != wrapped_r)
        new_head = (wrapped_q, wrapped_r)
        if new_head in self.snake[1:]:
            return False

        self.prev_snake_positions = list(self.snake)
        ate = new_head == self.apple
        if ate:
            old_apple = self.apple

        self.snake.insert(0, new_head)
        if len(self.snake) > self._max_snake_len_this_game:
            self._max_snake_len_this_game = len(self.snake)
        if not wrapped:
            self.path_history.appendleft(new_head)

        # Direction change detection for banking & dust
        dir_changed = old_dir != self.direction
        if dir_changed:
            hx, hy = hex_to_pixel(new_head[0], new_head[1])
            ddx, ddy = DIR_VECTORS[self.direction]
            self.particles.emit_movement_dust(hx, hy, 0.5, -ddx, -ddy)
            turn_dir = 1 if (self.direction - old_dir) % 6 == 1 else -1
            self.camera.on_turn(turn_dir)

        if ate:
            self.score += 10
            self._apples_eaten_this_game += 1
            self.audio.play_eat()
            if self.score % 50 == 0:
                self.audio.play_score_chime()
            self.apple = self._find_empty()
            self._spawn_eat_particles(old_apple)
            self.eat_flash = 0.2
            self.move_timer = 0
            self.eat_anim = {'timer': EAT_BULGE_DURATION, 'bulge_idx': 0, 'bulge_progress': 0}
            self.apple_anim = {'spawn_timer': APPLE_SPAWN_SCALE_TIME, 'was_spawned': True}
            self.camera.eat_punch()
        else:
            self.snake.pop()

        # Rebuild path_history from final snake state after wrap to guarantee
        # it matches the actual snake positions (avoids spline visual glitches).
        if wrapped:
            self._wrap_frame = True
            self.path_history.clear()
            for sq, sr in self.snake:
                self.path_history.append((sq, sr))

        self._request_full_redraw()
        return True

    def initiate_death(self):
        self.death_anim = {'timer': DEATH_ANIM_DURATION, 'phase': 'recoil'}
        self.audio.play_death()
        self.screen_shake = 0.25
        hx, hy = hex_to_pixel(*self.snake[0])
        self.particles.emit_death_burst(hx, hy, 2)
        self.camera.death_pullout()
        self.grade_death_darken = 0.5
        self._tile_cache_valid = False
        self._request_full_redraw()

    def _spawn_eat_particles(self, pos=None):
        if pos is None:
            pos = self.apple or self.snake[0]
        cx, cy = hex_to_pixel(*pos)
        self.particles.emit_apple_burst(cx, cy, 0)

    def _start_transition(self, target_state, reset=False):
        self._transitioning = True
        self.fade_target = 255
        self._transition_target = target_state
        self._transition_reset = reset
        self.menu_selection = 0

    def _handle_menu_mouse(self, pos):
        rects = self._get_menu_rects()
        for i, rect in enumerate(rects):
            if rect.collidepoint(pos):
                self.menu_selection = i
                break

    def _handle_menu_click(self):
        rects = self._get_menu_rects()
        for i, rect in enumerate(rects):
            if rect.collidepoint(self._last_mouse_pos):
                self.menu_selection = i
                self._activate_menu_item()
                break

    def _get_menu_rects(self):
        rects = []
        if self.state == GameState.START:
            for i in range(self._menu_count):
                y = 240 + i * 50
                rects.append(pygame.Rect(WIDTH // 2 - 70, y - 14, 140, 32))
        elif self.state == GameState.PAUSED:
            py = (HEIGHT - 260) // 2
            for i in range(self._menu_count):
                y = py + 100 + i * 40
                rects.append(pygame.Rect(WIDTH // 2 - 70, y - 10, 140, 28))
        elif self.state == GameState.SETTINGS:
            px = (WIDTH - 500) // 2
            py = (HEIGHT - 520) // 2
            for i in range(self._menu_count):
                y = py + 65 + i * 38
                rects.append(pygame.Rect(px + 30, y - 10, 400, 28))
        elif self.state == GameState.GAME_OVER:
            if self.score_count_up >= self.score or self.score == 0:
                py = (HEIGHT - 320) // 2
                for i in range(self._menu_count):
                    y = py + 185 + i * 40
                    rects.append(pygame.Rect(WIDTH // 2 - 70, y - 10, 140, 28))
        return rects

    def _activate_menu_item(self):
        if self.state == GameState.START:
            if self.menu_selection == 0:
                self._start_transition(GameState.PLAYING, reset=True)
            elif self.menu_selection == 1:
                self._settings_previous_state = GameState.START
                self._start_transition(GameState.SETTINGS)
            elif self.menu_selection == 2:
                self.quit()
        elif self.state == GameState.PAUSED:
            if self.menu_selection == 0:
                self.state = GameState.PLAYING
                self.grade_cool_shift = 0
                self.audio.resume()
            elif self.menu_selection == 1:
                self._settings_previous_state = GameState.PAUSED
                self._start_transition(GameState.SETTINGS)
            elif self.menu_selection == 2:
                self._start_transition(GameState.PLAYING, reset=True)
            elif self.menu_selection == 3:
                self._start_transition(GameState.START)
        elif self.state == GameState.GAME_OVER:
            if self.menu_selection == 0:
                self._start_transition(GameState.PLAYING, reset=True)
            elif self.menu_selection == 1:
                self._show_stats = not self._show_stats
            elif self.menu_selection == 2:
                self._start_transition(GameState.START)
        elif self.state == GameState.SETTINGS:
            if self.menu_selection == 9:
                self._settings_back()

    def _adjust_setting(self, direction):
        if self.menu_selection == 0:
            v = self.settings['music_volume'] + direction * 0.1
            self.settings['music_volume'] = max(0.0, min(1.0, round(v, 1)))
            self.audio.music_volume = self.settings['music_volume']
        elif self.menu_selection == 1:
            v = self.settings['sfx_volume'] + direction * 0.1
            self.settings['sfx_volume'] = max(0.0, min(1.0, round(v, 1)))
            self.audio.sfx_volume = self.settings['sfx_volume']
        elif self.menu_selection == 2:
            v = self.settings['ambience_volume'] + direction * 0.1
            self.settings['ambience_volume'] = max(0.0, min(1.0, round(v, 1)))
            self.audio.ambience_volume = self.settings['ambience_volume']
        elif self.menu_selection == 8:
            self._settings_back()
        self.persistence.set_settings(self.settings)
        self.persistence.save()

    def _toggle_setting(self):
        key_map = {
            3: 'bloom', 4: 'tone_map', 5: 'god_rays',
            6: 'vignette', 7: 'show_fps',
        }
        if self.menu_selection in key_map:
            key = key_map[self.menu_selection]
            self.settings[key] = not self.settings[key]
            self.persistence.set_settings(self.settings)
            self.persistence.save()
        elif self.menu_selection == 8:
            self._settings_back()

    def _settings_back(self):
        prev = self._settings_previous_state or GameState.START
        self._start_transition(prev)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and self.state == GameState.START:
                    self.quit()
                elif event.key == pygame.K_ESCAPE and self.state == GameState.GAME_OVER:
                    if self._show_stats:
                        self._show_stats = False
                    elif self.score_count_up >= self.score or self.score == 0:
                        self._start_transition(GameState.START)
                elif event.key == pygame.K_ESCAPE and self.state == GameState.PLAYING:
                    self._start_transition(GameState.START)
                elif event.key == pygame.K_F1:
                    self._debug_overlay = not self._debug_overlay
                elif event.key == pygame.K_F12:
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    pygame.image.save(self.screen, f'screenshot_{ts}.png')
                elif event.key == pygame.K_m:
                    self.audio.toggle_mute()

            if self._transitioning:
                continue

            if event.type == pygame.MOUSEMOTION:
                self._last_mouse_pos = event.pos

            if self.state == GameState.START:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.menu_selection = (self.menu_selection - 1) % max(1, self._menu_count)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.menu_selection = (self.menu_selection + 1) % max(1, self._menu_count)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._activate_menu_item()
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_menu_mouse(event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_menu_click()

            elif self.state == GameState.SETTINGS:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.menu_selection = (self.menu_selection - 1) % max(1, self._menu_count)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.menu_selection = (self.menu_selection + 1) % max(1, self._menu_count)
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        self._adjust_setting(-1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self._adjust_setting(1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._toggle_setting()
                    elif event.key == pygame.K_ESCAPE:
                        self._settings_back()
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_menu_mouse(event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_menu_click()

            elif self.state == GameState.PLAYING:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.state = GameState.PAUSED
                        self.grade_cool_shift = 0.3
                        self.audio.pause()
                        self.menu_selection = 0
                    elif event.key in (pygame.K_a, pygame.K_LEFT):
                        self.turn_left()
                    elif event.key in (pygame.K_d, pygame.K_RIGHT):
                        self.turn_right()
                    elif event.key == pygame.K_ESCAPE:
                        self._start_transition(GameState.START)

            elif self.state == GameState.PAUSED:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.menu_selection = (self.menu_selection - 1) % max(1, self._menu_count)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.menu_selection = (self.menu_selection + 1) % max(1, self._menu_count)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._activate_menu_item()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = GameState.PLAYING
                        self.grade_cool_shift = 0
                        self.audio.resume()
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_menu_mouse(event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_menu_click()

            elif self.state == GameState.GAME_OVER:
                if event.type == pygame.KEYDOWN:
                    if self._show_stats:
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                            self._show_stats = False
                        continue
                    score_done = self.score_count_up >= self.score or self.score == 0
                    if not score_done:
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                            self.score_count_up = self.score
                            self.score_count_up_timer = 0
                    else:
                        if event.key in (pygame.K_UP, pygame.K_w):
                            self.menu_selection = (self.menu_selection - 1) % max(1, self._menu_count)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            self.menu_selection = (self.menu_selection + 1) % max(1, self._menu_count)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                            self._activate_menu_item()
                elif event.type == pygame.MOUSEMOTION:
                    if not self._show_stats:
                        self._handle_menu_mouse(event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._show_stats:
                        self._show_stats = False
                    else:
                        self._handle_menu_click()

    def _update_transition(self, dt):
        if self.fade_alpha != self.fade_target:
            rate = MENU_FADE_SPEED * 255 * dt * 60
            if self.fade_target > self.fade_alpha:
                self.fade_alpha = min(self.fade_target, self.fade_alpha + rate)
            else:
                self.fade_alpha = max(self.fade_target, self.fade_alpha - rate)
            if abs(self.fade_alpha - self.fade_target) < 2:
                self.fade_alpha = self.fade_target
            if self.fade_alpha >= 255 and self._transition_target is not None:
                target = self._transition_target
                do_reset = self._transition_reset
                self._transition_target = None
                self._transition_reset = False
                if do_reset:
                    self.reset()
                else:
                    self.state = target
                    if target == GameState.PLAYING:
                        self.grade_cool_shift = 0
                        self.audio.resume()
                    elif target == GameState.SETTINGS:
                        self.menu_selection = 0
                self.fade_target = 0
            if self.fade_alpha <= 0 and not self._transition_target:
                self._transitioning = False

    def update(self, dt):
        """Fixed-timestep simulation update (dt is always FIXED_DT)."""
        self.ambient_time += dt
        self._update_transition(dt)

        if self.state in (GameState.START, GameState.SETTINGS):
            self._update_birds(dt * 60)
            if self.state == GameState.START:
                self.ambient_time += dt * 0.3
            day_cycle = math.sin(self.ambient_time * SUN_ANGLE_SPEED)
            self.audio.update(day_cycle, 0.0, dt)
            return

        self.update_ambient_particles(dt)

        day_cycle = math.sin(self.ambient_time * SUN_ANGLE_SPEED)

        if self.state == GameState.PLAYING:
            if self._transitioning:
                pass
            elif self.death_anim['phase'] != 'none':
                self.death_anim['timer'] -= dt
                if self.death_anim['timer'] <= 0:
                    if not self._game_recorded:
                        duration = time.time() - self._game_start_time
                        self.persistence.record_game(
                            self.score,
                            self._apples_eaten_this_game,
                            duration,
                            self._max_snake_len_this_game,
                        )
                        self.persistence.save()
                        self._game_recorded = True
                    self.state = GameState.GAME_OVER
            else:
                self.move_timer += dt
                interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - self.score * SPEED_DECAY_PER_POINT)

                while self.move_timer >= interval:
                    self.move_timer -= interval
                    if not self.move_snake():
                        self.initiate_death()
                        break

        # Eat anim: bulge travels down the body
        if self.eat_anim['timer'] > 0:
            self.eat_anim['timer'] -= dt
            progress = 1.0 - max(0, self.eat_anim['timer']) / EAT_BULGE_DURATION
            self.eat_anim['bulge_progress'] = progress
            self.eat_anim['bulge_idx'] = min(len(self.snake) - 1, int(progress * len(self.snake)))

        # Apple spawn anim
        if self.apple_anim['spawn_timer'] > 0:
            self.apple_anim['spawn_timer'] -= dt
            if self.apple_anim['spawn_timer'] < 0:
                self.apple_anim['spawn_timer'] = 0

        # Blink timer
        self.blink_timer -= dt
        if self.blink_timer <= 0:
            self.blink_timer = random.uniform(2, 5)

        self.particles.update_all(dt)
        self.particles.clean()

        if self.eat_flash > 0:
            self.eat_flash -= dt
            self.grade_warm_flash = self.eat_flash
            if self.eat_flash < 0:
                self.eat_flash = 0
                self.grade_warm_flash = 0
            self._tile_cache_valid = False
            self._request_full_redraw()

        if self.screen_shake > 0:
            self.screen_shake -= dt
            if self.screen_shake < 0:
                self.screen_shake = 0

        if self.grade_death_darken > 0:
            self.grade_death_darken = max(0, self.grade_death_darken - dt)

        if self.grade_cool_shift > 0:
            self.grade_cool_shift = max(0, self.grade_cool_shift - dt * 0.5)

        self._update_birds(dt * 60)

        if self.score > self.high_score:
            self.high_score = self.score

        self.audio.update(day_cycle, self._speed_ratio, dt)

        # Score pop tracking
        if self.score != self._prev_score:
            self._prev_score = self.score
            self.score_pop_timer = SCORE_POP_DURATION
        if self.score_pop_timer > 0:
            self.score_pop_timer -= dt
            if self.score_pop_timer < 0:
                self.score_pop_timer = 0

    def _update_game_over_countup(self, dt):
        if self.state == GameState.GAME_OVER:
            if not self._countup_started:
                self.score_count_up_timer = 1.5
                self.score_count_up = 0
                if self.score >= self.high_score and self.score > 0:
                    self.new_record_bounce_timer = 2.0
                else:
                    self.new_record_bounce_timer = 0
                self._countup_started = True
            if self.score_count_up_timer > 0:
                self.score_count_up_timer -= dt
                progress = 1.0 - max(0, self.score_count_up_timer) / 1.5
                self.score_count_up = int(progress * self.score)
            elif self.score_count_up < self.score:
                self.score_count_up = self.score
            if self.new_record_bounce_timer > 0:
                self.new_record_bounce_timer = max(0, self.new_record_bounce_timer - dt)

    def draw_tile(self, surf, q, r, time_float):
        static = self._tile_static_cache[(q, r)]
        corners_world = static['corners_world']
        cx, cy = static['center_world']
        base_top_color_tuple = static['base_top_color']
        base_side_color_tuple = static['base_side_color']
        tex_variation = static['tex_variation']
        dist_factor = static['dist_factor']
        grass_seed = static['grass_seed']
        grass_blades = static['grass_blades']

        top_pts = []
        bot_pts = []
        for c_x, c_y in corners_world:
            sx_t, sy_t, _ = self.camera.project(c_x, c_y, 0)
            sx_b, sy_b, _ = self.camera.project(c_x, c_y, -TILE_HEIGHT)
            top_pts.append((sx_t, sy_t))
            bot_pts.append((sx_b, sy_b))

        cx_proj = sum(p[0] for p in top_pts) / 6
        cy_proj = sum(p[1] for p in top_pts) / 6

        sun_factor = 0.85 + 0.15 * math.sin(time_float * SUN_ANGLE_SPEED + q * 0.5 + r * 0.3)
        ao = self._tile_ao_cache.get((q, r), 0.9)
        if (q, r) in self._snake_set:
            ao *= (1.0 - AO_TILE_OCCUPIED)

        edge_color = TILE_EDGE
        if self.state == GameState.GAME_OVER:
            edge_color = (30, 15, 18)
        elif self.eat_flash > 0:
            flash = min(1.0, self.eat_flash / 0.2)
            edge_color = lerp_color(TILE_EDGE, TILE_GLOW, flash)

        base_top_color = list(base_top_color_tuple)
        base_side_color = list(base_side_color_tuple)

        if (q, r) in self._snake_set:
            worn = 0.15
            base_top_color = list(lerp_color(tuple(base_top_color), TILE_TOP_LIGHT, worn))

        if self.state == GameState.GAME_OVER:
            base_top_color = [10, 25, 20]
            base_side_color = [6, 14, 12]
        elif self.eat_flash > 0:
            flash = min(1.0, self.eat_flash / 0.2)
            base_top_color = list(lerp_color(tuple(base_top_color), mul_color(TILE_GLOW, 0.3), flash * 0.5))

        face_normal = (0.0, 0.0, 1.0)
        diff = max(0.0, dot3(face_normal, self._light_dir))
        light = (self._ambient + (1.0 - self._ambient) * diff) * sun_factor * dist_factor * ao
        final_tri_color = mul_color(tuple(base_top_color), light)
        _, _, depth = self.camera.project(cx, cy, 0)
        fog_t = max(0, min(1, (depth - FOG_NEAR) / (FOG_FAR - FOG_NEAR)))
        depth_fade = fog_t * DEPTH_FADE_STRENGTH
        if fog_t > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), self._fog_tint, fog_t * 0.35)
        if depth_fade > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), self._sky_hor, depth_fade)
        final_tri_color = mul_color(tuple(final_tri_color), tex_variation)

        pygame.draw.polygon(surf, edge_color, top_pts, max(1, int(1 + sun_factor * 0.5)))

        pygame.draw.polygon(surf, final_tri_color, top_pts)

        for i in range(6):
            j = (i + 1) % 6
            quad = [top_pts[i], top_pts[j], bot_pts[j], bot_pts[i]]
            nx_s, ny_s, nz_s = hex_side_normal(i)
            diff_side = max(0.0, nx_s * self._light_dir[0] + ny_s * self._light_dir[1] + nz_s * self._light_dir[2])
            side_light = (self._ambient + (1.0 - self._ambient) * diff_side) * sun_factor * dist_factor * ao

            side_ao = 1.0 - 0.12 * (1.0 - abs(diff_side))
            side_light *= side_ao

            side_noise_val = static.get('noise', {}).get('detail', 0) * 0.08
            side_light = max(0.1, side_light + side_noise_val)

            sc_top = mul_color(tuple(base_side_color), side_light * 1.1)
            if depth_fade > 0:
                sc_top = lerp_color(sc_top, self._sky_hor, depth_fade)
            pygame.draw.polygon(surf, sc_top, quad)

            edge_highlight = mul_color(TILE_EDGE_HIGHLIGHT, 0.3 * max(0.3, side_light))
            pygame.draw.line(surf, edge_highlight, quad[0], quad[1], 1)

        bevel_n = (0.0, 0.0, 1.0)
        bevel_light = self._ambient + (1.0 - self._ambient) * max(0.0, dot3(bevel_n, self._light_dir))
        bevel_brightness = bevel_light * sun_factor * ao
        inner_hl = mul_color(TILE_EDGE_HIGHLIGHT, 0.2 * bevel_brightness)
        for i in range(6):
            j = (i + 1) % 6
            pygame.draw.line(surf, inner_hl, top_pts[i], top_pts[j], 2)

        crack_intensity = abs(static.get('noise', {}).get('crack', 0)) ** 3 * 0.3
        if crack_intensity > 0.05:
            crack_color = mul_color(final_tri_color, 0.7)
            for _ in range(int(crack_intensity * 3)):
                angle = random.uniform(0, math.tau)
                dist = random.uniform(1, HEX_SIZE * 0.4)
                ex = cx_proj + math.cos(angle) * dist
                ey = cy_proj + math.sin(angle) * dist
                pygame.draw.line(surf, crack_color, (int(cx_proj), int(cy_proj)), (int(ex), int(ey)), 1)

        rim_light = mul_color(TILE_EDGE_HIGHLIGHT, 0.25 * sun_factor * dist_factor * ao)
        for i in range(6):
            j = (i + 1) % 6
            edge_center_x = (top_pts[i][0] + top_pts[j][0]) / 2
            edge_center_y = (top_pts[i][1] + top_pts[j][1]) / 2
            edge_nx = top_pts[j][1] - top_pts[i][1]
            edge_ny = top_pts[i][0] - top_pts[j][0]
            el = math.hypot(edge_nx, edge_ny)
            if el > 0:
                edge_nx /= el
                edge_ny /= el
                rim = max(0.0, edge_nx * self._light_dir[0] + edge_ny * self._light_dir[1])
                if rim > 0.3:
                    pygame.draw.line(surf, rim_light, top_pts[i], top_pts[j], 1)

        if grass_seed > 0.1 and self.state != GameState.GAME_OVER:
            for blade in grass_blades:
                bx, by = blade['bx'], blade['by']
                blade_h, blade_w = blade['blade_h'], blade['blade_w']
                gc = blade['gc']
                sway = math.sin(time_float * 1.8 + bx * 0.4 + by * 0.3) * 2
                sx_b, sy_b, _ = self.camera.project(bx, by, 0)
                sx_t, sy_t, _ = self.camera.project(bx + sway, by, blade_h)
                pygame.draw.line(surf, gc, (int(sx_b), int(sy_b)), (int(sx_t), int(sy_t)), blade_w)
                if blade['has_flower']:
                    pygame.draw.circle(surf, blade['flower_color'], (int(sx_t), int(sy_t)), max(1, blade_w + 1))

    def draw_shadow(self, surf, world_x, world_y, height, radius, alpha=None):
        light_dir = self._light_dir
        if light_dir[2] <= 0.001:
            return
        factor = height / light_dir[2]
        shadow_x = world_x + light_dir[0] * factor
        shadow_y = world_y + light_dir[1] * factor
        shadow_scale = 1.0 + max(0, height) * 0.3
        shadow_size = max(2, int(radius * 2 * shadow_scale))
        if alpha is None:
            alpha = SHADOW_ALPHA * max(0.0, min(1.0, 1.0 - height * 0.02))
        sx, sy, _ = self.camera.project(shadow_x, shadow_y, 0)
        scaled = pygame.transform.smoothscale(self.soft_shadow_sprite, (shadow_size, shadow_size))
        scaled.set_alpha(int(alpha))
        surf.blit(scaled, (int(sx - shadow_size // 2), int(sy - shadow_size // 2)))

    def draw_snake_segment(self, surf, idx, q, r, time_float):
        if not hasattr(self, '_spline_positions') or not self._spline_positions:
            return
        if idx >= len(self._spline_positions):
            return

        px, py, tx, ty = self._spline_positions[idx]
        cx, cy = px, py

        t = idx / max(1, len(self.snake) - 1)
        color_idx = min(len(SNAKE_COLORS) - 1, int(t * len(SNAKE_COLORS)))

        thickness_curve = 1.0 - t * 0.25
        thickness_curve *= (1.0 + 0.15 * math.sin(t * math.pi))
        body_pulse = 1.0 + 0.03 * math.sin(time_float * 2 + idx * 0.5)
        sz = int(HEX_SIZE * SNAKE_SEGMENT_SCALE * thickness_curve * body_pulse)

        # Eat bulge animation
        if self.eat_anim['timer'] > 0 and idx == self.eat_anim['bulge_idx']:
            bulge = 1.0 + 0.4 * math.sin(self.eat_anim['bulge_progress'] * math.pi)
            sz = int(sz * bulge)

        # Death collapse
        if self.death_anim['phase'] != 'none':
            death_t = 1.0 - min(1.0, self.death_anim['timer'] / DEATH_ANIM_DURATION)
            head_factor = 1.0 - idx / max(1, len(self.snake))
            collapse = 1.0 - death_t * 0.5 * head_factor
            sz = max(1, int(sz * collapse))

        # Head squash-stretch on eat
        if idx == 0 and self.eat_anim['timer'] > EAT_BULGE_DURATION - EAT_SQUASH_DURATION:
            eat_t = 1.0 - (self.eat_anim['timer'] - (EAT_BULGE_DURATION - EAT_SQUASH_DURATION)) / EAT_SQUASH_DURATION
            if 0 <= eat_t <= 1:
                squash = 1.0 + 0.2 * math.sin(eat_t * math.pi)
                stretch = 1.0 - 0.2 * math.sin(eat_t * math.pi)
            else:
                squash = stretch = 1.0
        else:
            squash = stretch = 1.0

        # Project at tile surface height (z=0) — snake sits on tiles
        sx, sy, depth = self.camera.project(cx, cy, 0)
        self.draw_shadow(surf, cx, cy, 0, int(sz * 0.5))

        # Continuous body strip between consecutive segments
        if idx < len(self.snake) - 1 and idx + 1 < len(self._spline_positions):
            npx, npy, _, _ = self._spline_positions[idx + 1]
            dx_s = npx - cx
            dy_s = npy - cy
            d_len = math.hypot(dx_s, dy_s)
            if d_len > 0.001 and sz > 2:
                perp_x = -dy_s / d_len
                perp_y = dx_s / d_len

                nt = (idx + 1) / max(1, len(self.snake) - 1)
                nthick = 1.0 - nt * 0.25
                nthick *= (1.0 + 0.15 * math.sin(nt * math.pi))
                next_sz = int(HEX_SIZE * SNAKE_SEGMENT_SCALE * nthick * body_pulse)
                if next_sz < 2:
                    next_sz = sz

                half_w = int(sz * 0.45)
                next_half_w = int(next_sz * 0.45)

                strip_pts = [
                    (cx + perp_x * half_w, cy + perp_y * half_w, 0),
                    (npx + perp_x * next_half_w, npy + perp_y * next_half_w, 0),
                    (npx - perp_x * next_half_w, npy - perp_y * next_half_w, 0),
                    (cx - perp_x * half_w, cy - perp_y * half_w, 0),
                ]
                screen_pts = []
                for wx, wy, wz in strip_pts:
                    sx_p, sy_p, _ = self.camera.project(wx, wy, wz)
                    screen_pts.append((int(sx_p), int(sy_p)))

                if len(screen_pts) == 4:
                    base_color = HEAD_COLOR if idx == 0 else SNAKE_COLORS[color_idx]
                    diff = max(0.0, self._light_dir[2])
                    light = self._ambient + (1.0 - self._ambient) * diff
                    c = mul_color(base_color, light)
                    c = add_color(c, mul_color(self._sun_color, light * 0.5))
                    pygame.draw.polygon(surf, c, screen_pts)

        if idx == 0:
            sz = int(sz * HEAD_SCALE)

        if idx == 0:
            sprite_sz = max(int(sz * squash), int(sz * stretch))
            sprite = self._head_sprites.get(sprite_sz)
            if sprite is None:
                sprite = pygame.transform.smoothscale(self.master_head_sprite, (sprite_sz, sprite_sz))
                self._head_sprites[sprite_sz] = sprite
            if squash != 1.0 or stretch != 1.0:
                sprite = pygame.transform.scale(sprite, (int(sz * squash), int(sz * stretch)))
        else:
            sprite = self._body_sprites[color_idx].get(sz)
            if sprite is None:
                sprite = pygame.transform.smoothscale(self.master_body_sprites[color_idx], (sz, sz))
                self._body_sprites[color_idx][sz] = sprite
        surf.blit(sprite, (int(sx - sz * squash // 2), int(sy - sz * stretch // 2)))

        if idx == 0:
            dir_len = math.hypot(tx, ty)
            if dir_len > 0.001:
                perp_x = -ty / dir_len
                perp_y = tx / dir_len
            else:
                perp_x, perp_y = 0, -1

            head_glow_a = int(30 + 20 * math.sin(time_float * 4))
            glow_r = max(1, int(sz * 0.7))
            glow_surf = self._head_glow_sprites.get(sz)
            if glow_surf is None:
                d = glow_r * 2
                glow_surf = pygame.Surface((d, d), pygame.SRCALPHA)
                for gi in range(glow_r, 0, -1):
                    ga = int(50 * (1 - gi / glow_r) * 0.3)
                    if ga > 0:
                        pygame.draw.circle(glow_surf, (*HEAD_HIGHLIGHT, ga), (glow_r, glow_r), gi)
                self._head_glow_sprites[sz] = glow_surf
            glow_surf.set_alpha(int(head_glow_a * 255 / 50))
            surf.blit(glow_surf, (int(sx - glow_r), int(sy - glow_r)), special_flags=pygame.BLEND_ADD)

            # Eye blink
            is_blinking = self.blink_timer <= 0.1
            if not is_blinking:
                es = max(3, int(sz * 0.12))
                eye_spread = es * 2.0
                for side in [-1, 1]:
                    ex = int(sx + perp_x * eye_spread * side + tx * sz * 0.15)
                    ey = int(sy + perp_y * eye_spread * side + ty * sz * 0.15)
                    es_draw = max(1, es)
                    pygame.draw.circle(surf, EYE_WHITE, (ex, ey), es_draw)
                    iris_r = max(1, es - 1)
                    iris_off_x = int(perp_x * side * es * 0.35)
                    iris_off_y = int(perp_y * side * es * 0.35)
                    pygame.draw.circle(surf, EYE_IRIS, (ex + iris_off_x, ey + iris_off_y), iris_r)
                    pupil_r = max(1, es - 2)
                    pygame.draw.circle(surf, EYE_PUPIL, (ex + int(perp_x * side * es * 0.35), ey + int(perp_y * side * es * 0.35)), pupil_r)
                    if es > 2:
                        ref_x = ex + int(perp_x * side * es * 0.5) - int(tx * sz * 0.02)
                        ref_y = ey + int(perp_y * side * es * 0.5) - int(ty * sz * 0.02)
                        pygame.draw.circle(surf, EYE_REFLECTION, (ref_x, ref_y), max(1, es // 3))

            # Tongue along tangent
            tongue_len = int(HEX_SIZE * 0.16)
            tongue_w = max(1, int(HEX_SIZE * 0.022))
            tongue_flick = math.sin(time_float * 14) * 2
            tx_t = int(sx + tx * (tongue_len + tongue_flick))
            ty_t = int(sy + ty * (tongue_len + tongue_flick))
            pygame.draw.line(surf, (210, 70, 70), (int(sx), int(sy)), (tx_t, ty_t), tongue_w)
            if dir_len > 0.001:
                ppx = -ty / dir_len
                ppy = tx / dir_len
                fork_s = 2
                fork_l = int(HEX_SIZE * 0.04)
                pygame.draw.line(surf, (210, 70, 70),
                    (tx_t, ty_t),
                    (tx_t + int(ppx * fork_s) + int(tx * fork_l),
                     ty_t + int(ppy * fork_s) + int(ty * fork_l)),
                    max(1, tongue_w - 1))
                pygame.draw.line(surf, (210, 70, 70),
                    (tx_t, ty_t),
                    (tx_t - int(ppx * fork_s) + int(tx * fork_l),
                     ty_t - int(ppy * fork_s) + int(ty * fork_l)),
                    max(1, tongue_w - 1))

    def draw_apple(self, surf, time_float):
        if not self.apple:
            return
        q, r = self.apple
        cx, cy = hex_to_pixel(q, r)

        pulse = 1.0 + math.sin(time_float * 2.5) * 0.06
        sz = int(HEX_SIZE * APPLE_SCALE * pulse)

        # Spawn pop-in animation
        spawn_scale = 1.0
        if self.apple_anim['spawn_timer'] > 0:
            spawn_t = 1.0 - self.apple_anim['spawn_timer'] / APPLE_SPAWN_SCALE_TIME
            spawn_scale = max(0.0, min(1.0, spawn_t))

        self.draw_shadow(surf, cx + math.sin(time_float * 0.5) * 1.2, cy, 0.5, int(sz * 0.6))

        bob = math.sin(time_float * 1.2) * 0.3
        sx_p, sy_p, _ = self.camera.project(cx + math.sin(time_float * 0.5) * 1.2, cy, bob)

        display_sz = max(1, int(sz * spawn_scale))
        sprite = self._apple_sprites.get(display_sz)
        if sprite is None:
            sprite = pygame.transform.smoothscale(self.master_apple_sprite, (display_sz, display_sz))
            self._apple_sprites[display_sz] = sprite
        surf.blit(sprite, (int(sx_p - display_sz // 2), int(sy_p - display_sz // 2)))

        sx_top, sy_top, _ = self.camera.project(cx, cy, bob + 2)
        stem_w = max(1, int(HEX_SIZE * 0.035))
        stem_h = int(HEX_SIZE * 0.18)
        wind = math.sin(time_float * 0.7) * 1.2
        stem_curve = 3 + int(wind)
        stem_sway = math.sin(time_float * 1.5) * 1.5
        stem_tip_x = sx_top + stem_curve + stem_sway
        stem_tip_y = sy_top - stem_h
        stem_mid_x = sx_top + stem_curve * 0.6 + stem_sway * 0.5
        stem_mid_y = sy_top - stem_h * 0.5
        pygame.draw.line(surf, APPLE_STEM, (int(sx_top), int(sy_top)), (int(stem_mid_x), int(stem_mid_y)), stem_w)
        pygame.draw.line(surf, mul_color(APPLE_STEM, 1.3), (int(stem_mid_x), int(stem_mid_y)), (int(stem_tip_x), int(stem_tip_y)), max(1, stem_w - 1))
        pygame.draw.line(surf, mul_color(APPLE_STEM, 0.8), (int(sx_top), int(sy_top)), (int(sx_top + stem_curve * 0.3 + stem_sway * 0.3), int(sy_top - stem_h * 0.25)), max(1, stem_w))

        lx = int(stem_tip_x + HEX_SIZE * 0.08)
        ly = int(stem_tip_y + stem_h * 0.1)
        lr_x = max(2, int(HEX_SIZE * 0.10))
        lr_y = max(1, int(HEX_SIZE * 0.05))
        self._leaf_surf.fill((0, 0, 0, 0))
        leaf_angle = math.radians(-20 + math.sin(time_float * 2) * 12 + wind * 5)
        leaf_pts = [
            (0, lr_y),
            (lr_x * 2, 0),
            (lr_x * 3, lr_y),
            (lr_x * 2, lr_y * 2),
        ]
        rot_pts = []
        for pt in leaf_pts:
            rx = pt[0] * math.cos(leaf_angle) - pt[1] * math.sin(leaf_angle)
            ry = pt[0] * math.sin(leaf_angle) + pt[1] * math.cos(leaf_angle)
            rot_pts.append((rx + lr_x * 0.5, ry + lr_y))
        pygame.draw.polygon(self._leaf_surf, APPLE_LEAF, rot_pts)
        vein_pts = [
            (lr_x * 0.5, lr_y * 0.3),
            (lr_x * 1.5, lr_y * 0.5),
            (lr_x * 2.5, lr_y * 0.7),
        ]
        for vi in range(len(vein_pts) - 1):
            vx1 = vein_pts[vi][0] * math.cos(leaf_angle) - vein_pts[vi][1] * math.sin(leaf_angle) + lr_x * 0.5
            vy1 = vein_pts[vi][0] * math.sin(leaf_angle) + vein_pts[vi][1] * math.cos(leaf_angle) + lr_y
            vx2 = vein_pts[vi+1][0] * math.cos(leaf_angle) - vein_pts[vi+1][1] * math.sin(leaf_angle) + lr_x * 0.5
            vy2 = vein_pts[vi+1][0] * math.sin(leaf_angle) + vein_pts[vi+1][1] * math.cos(leaf_angle) + lr_y
            pygame.draw.line(self._leaf_surf, APPLE_LEAF_VEIN, (int(vx1), int(vy1)), (int(vx2), int(vy2)), 1)
        pygame.draw.polygon(self._leaf_surf, APPLE_LEAF_HIGHLIGHT, rot_pts, 1)
        surf.blit(self._leaf_surf, (lx - lr_x * 1.5, ly - lr_y * 1.5))

    def update_ambient_particles(self, dt):
        target_count = 60
        if len(self.particles) < target_count and random.random() < 0.15 * dt * 60:
            q = random.randint(-GRID_RADIUS, GRID_RADIUS)
            r = random.randint(-GRID_RADIUS, GRID_RADIUS)
            cx, cy = hex_to_pixel(q, r)
            cz = random.uniform(0, TILE_HEIGHT * 0.6)
            self.particles.emit_ambient_mote(cx, cy, cz)

    def _build_depth_buckets(self, items, num_buckets=256):
        if not items:
            return []
        min_d = min(item[0] for item in items)
        max_d = max(item[0] for item in items)
        d_range = max_d - min_d
        buckets = {}
        for item in items:
            depth = item[0]
            if d_range > 0.001:
                b = int((depth - min_d) / d_range * (num_buckets - 1))
                b = min(num_buckets - 1, max(0, b))
            else:
                b = 0
            if b not in buckets:
                buckets[b] = []
            buckets[b].append(item)
        result = []
        for b in range(num_buckets - 1, -1, -1):
            if b in buckets:
                result.extend(buckets[b])
        return result

    def render(self):
        _t_frame = time.perf_counter()

        if self.state in (GameState.START, GameState.SETTINGS):
            self._snake_set = set()
            self._spline_positions = None
            self.camera.update_idle(1.0 / max(RENDER_FPS, 1), self.render_time)
        else:
            self._snake_set = set(self.snake)
            self._spline_positions = None
            if len(self.path_history) >= 2:
                self._spline_positions = sample_spline_path(list(self.path_history), len(self.snake))
                self._spline_positions.reverse()
            if self._wrap_frame:
                self._wrap_frame = False
            self.camera.follow_snake(*self.snake[0], self.direction, 1.0 / max(RENDER_FPS, 1), self._speed_ratio)
        surf = self.screen
        time_float = self.render_time

        light_dir, ambient, sun_color = compute_sun_light(time_float)
        self._light_dir = light_dir
        self._ambient = ambient
        self._sun_color = sun_color
        self._day_cycle = math.sin(time_float * SUN_ANGLE_SPEED)
        self._sky_top, self._sky_mid, self._sky_hor = compute_sky_color(time_float)
        self._fog_tint = lerp_color(self._sky_mid, FOG_COLOR, 0.6)

        shake_x, shake_y = 0, 0
        if self.screen_shake > 0:
            intensity = self.screen_shake / 0.25 * 5
            shake_x, shake_y = screen_shake_offset(intensity)

        _t = time.perf_counter()
        self.resources._update_sky(time_float, self._day_cycle)
        surf.blit(self.bg_surf, (shake_x, shake_y))

        star_alpha = 0
        if self._day_cycle < SKY_STAR_FADE_START:
            star_alpha = int(255 * min(1.0, (SKY_STAR_FADE_START - self._day_cycle) / (SKY_STAR_FADE_START - SKY_STAR_FADE_END)))
        self.star_surf.set_alpha(star_alpha)
        surf.blit(self.star_surf, (shake_x, shake_y))

        sun_x_off = int(math.sin(time_float * SUN_ANGLE_SPEED) * 200)
        sun_y = int(HEIGHT * 0.15)
        surf.blit(self.sun_disc_surf, (WIDTH // 2 + sun_x_off - 62, sun_y - 62), special_flags=pygame.BLEND_ADD)

        water_color_base = lerp_color(self._sky_mid, WATER_COLOR_1, 0.4)
        water_highlight = lerp_color(sun_color, WATER_HIGHLIGHT, 0.5)

        self.water_surf.fill((0, 0, 0, 0))
        for wi in range(-12, 12):
            wy = wi * 28
            z_w = -TILE_HEIGHT - 20
            w2 = 1000
            t = (wi + 25) / 50
            sx_center, sy_center, sd = self.camera.project(0, wy, z_w)
            if sx_center < -200 or sx_center > WIDTH + 200:
                continue
            if sy_center < -200 or sy_center > HEIGHT + 200:
                continue
            sx1, sy1, _ = self.camera.project(-w2, wy, z_w)
            sx2, sy2, _ = self.camera.project(w2, wy, z_w)

            combined_wave = (math.sin(wy * 0.04 + time_float * WATER_WAVE_SPEED) * WATER_WAVE_AMP
                    + math.sin(wy * 0.07 + time_float * WATER_WAVE_SPEED * 1.5 + 1) * WATER_WAVE_AMP * 0.6)

            c = lerp_color(water_color_base, WATER_COLOR_2, t)
            fresnel = 0.3 + 0.7 * (1.0 - abs(t - 0.5) * 2) ** 2
            a = int(190 * fresnel)

            pts = [(sx1, sy1 + combined_wave), (sx2, sy2 + combined_wave),
                   (sx2, sy2 + 16 + combined_wave), (sx1, sy1 + 16 + combined_wave)]
            pygame.draw.polygon(self.water_surf, (*c, a), pts)

            if wi % 4 == 0:
                hl_a = int(50 * fresnel * (0.5 + 0.5 * math.sin(time_float * 1.2 + wi * 0.3)))
                if hl_a > 2:
                    pygame.draw.line(self.water_surf, (*water_highlight, hl_a),
                        (sx1, sy1 + combined_wave + 1), (sx2, sy2 + combined_wave + 1), 1)

        sun_ref_x = WIDTH // 2 + sun_x_off
        sun_ref_y_start = HEIGHT * 0.5
        sun_ref_h = HEIGHT * 0.2
        self._water_reflect_surf.fill((0, 0, 0, 0))
        for ry in range(0, int(sun_ref_h), 2):
            alpha = int(40 * (1 - ry / sun_ref_h) * (0.5 + 0.5 * math.sin(time_float * 2 + ry * 0.1)))
            if alpha > 0:
                self._water_reflect_surf.fill((*sun_color, alpha), rect=(0, ry, 100, 2))
        surf.blit(self._water_reflect_surf, (sun_ref_x - 50, sun_ref_y_start), special_flags=pygame.BLEND_ADD)

        if not hasattr(self, '_reflect_cache'):
            self._reflect_cache = pygame.Surface((WIDTH, HEIGHT // 3), pygame.SRCALPHA)
            self._reflect_cache.blit(self.bg_surf, (0, 0), (0, HEIGHT // 2, WIDTH, HEIGHT // 3))
            self._reflect_cache = pygame.transform.flip(self._reflect_cache, False, True)
        reflect_alpha = int(30 + 10 * math.sin(time_float * 0.3))
        self._reflect_cache.set_alpha(reflect_alpha)
        surf.blit(self._reflect_cache, (0, HEIGHT - HEIGHT // 3), special_flags=pygame.BLEND_ADD)

        surf.blit(self.water_surf, (0, 0))

        _t0 = time.perf_counter()
        self._build_ground()
        surf.blit(self.ground_cache, (shake_x, shake_y))
        self._build_tile_cache()
        self._perf_timings['tiles'] = (time.perf_counter() - _t0) * 1000

        self.draw_cache.fill((0, 0, 0, 0))
        self.draw_cache.blit(self._tile_cache, (0, 0))

        _t0 = time.perf_counter()
        draw_items = []
        if self.apple:
            ax, ay = hex_to_pixel(*self.apple)
            _, _, depth = self.camera.project(ax, ay, 0.5)
            draw_items.append((depth, 'apple'))

        for idx, (q, r) in enumerate(self.snake):
            if self._spline_positions and idx < len(self._spline_positions):
                cx, cy = self._spline_positions[idx][0], self._spline_positions[idx][1]
            else:
                cx, cy = hex_to_pixel(q, r)
            _, _, depth = self.camera.project(cx, cy, 0)
            draw_items.append((depth, 'snake', idx, q, r))

        draw_list = self._build_depth_buckets(draw_items)

        for item in draw_list:
            if item[1] == 'apple':
                self.draw_apple(self.draw_cache, time_float)
            elif item[1] == 'snake':
                _, _, idx, q, r = item
                self.draw_snake_segment(self.draw_cache, idx, q, r, time_float)

        surf.blit(self.draw_cache, (shake_x, shake_y))
        self._perf_timings['snake'] = (time.perf_counter() - _t0) * 1000

        _t0 = time.perf_counter()
        if self.gl_renderer.available:
            scene = surf.copy()
            result = self.gl_renderer.post_process(scene, time_float)
            if result:
                surf.blit(result, (0, 0))
        else:
            bloom_enabled = self.settings.get('bloom', POST_BLOOM_ENABLED)
            tone_map_enabled = self.settings.get('tone_map', POST_TONE_MAP_ENABLED)
            god_rays_enabled = self.settings.get('god_rays', POST_GOD_RAYS_ENABLED)
            if bloom_enabled or tone_map_enabled:
                if np is not None:
                    try:
                        bloom_small = pygame.transform.smoothscale(surf, (WIDTH // 4, HEIGHT // 4))
                        barr = pygame.surfarray.pixels3d(bloom_small)
                        if bloom_enabled:
                            luma = 0.299 * barr[:,:,0] + 0.587 * barr[:,:,1] + 0.114 * barr[:,:,2]
                            thresh_f = 255.0 * BLOOM_THRESHOLD
                            dark = luma < thresh_f
                            barr[:,:,0][dark] = 0
                            barr[:,:,1][dark] = 0
                            barr[:,:,2][dark] = 0
                        if tone_map_enabled:
                            r_ch = barr[:,:,0].astype(np.uint16)
                            g_ch = barr[:,:,1].astype(np.uint16)
                            b_ch = barr[:,:,2].astype(np.uint16)
                            barr[:,:,0] = ((r_ch * 255) // (r_ch + 255)).astype(np.uint8)
                            barr[:,:,1] = ((g_ch * 255) // (g_ch + 255)).astype(np.uint8)
                            barr[:,:,2] = ((b_ch * 255) // (b_ch + 255)).astype(np.uint8)
                        del barr
                        blur = pygame.transform.smoothscale(bloom_small, (WIDTH, HEIGHT))
                        if bloom_enabled:
                            blur.set_alpha(int(28 * BLOOM_INTENSITY * 2))
                            surf.blit(blur, (0, 0), special_flags=pygame.BLEND_ADD)
                    except (pygame.error, ValueError):
                        pass
                else:
                    if bloom_enabled or tone_map_enabled:
                        if not hasattr(self, '_warned_no_numpy'):
                            self._warned_no_numpy = True
                            print("WARNING: numpy not available — skipping bloom/tone map (install numpy for post-FX)")
                

            if god_rays_enabled and self._day_cycle > 0.2:
                self._rays_surf_cache.fill((0, 0, 0, 0))
                sun_sx = WIDTH // 2 + sun_x_off
                sun_sy = sun_y
                for ri in range(6):
                    angle = math.radians(ri * 60 + 30 + math.sin(time_float * 0.15 + ri) * 8)
                    ray_len = 180 + int(math.sin(time_float * 0.1 + ri * 1.5) * 60)
                    ex = sun_sx + int(math.cos(angle) * ray_len)
                    ey = sun_sy + int(math.sin(angle) * ray_len)
                    ray_a = 5
                    if ray_a > 0:
                        pygame.draw.line(self._rays_surf_cache, (*sun_color, ray_a), (sun_sx, sun_sy), (ex, ey), 2)
                surf.blit(self._rays_surf_cache, (0, 0), special_flags=pygame.BLEND_ADD)
        self._perf_timings['post'] = (time.perf_counter() - _t0) * 1000

        _t0 = time.perf_counter()
        if self.apple and self.state != GameState.GAME_OVER:
            px, py = hex_to_pixel(*self.apple)
            sx, sy, _ = self.camera.project(px, py, 0.5)
            glow_r = int(HEX_SIZE * 1.0 + math.sin(time_float * 2.5) * 6)
            glow_surf = self._apple_glow_sprites.get(glow_r)
            if glow_surf is None:
                d = glow_r * 2
                glow_surf = pygame.Surface((d, d), pygame.SRCALPHA)
                for i in range(glow_r, 0, -1):
                    a = int(35 * (1 - i / glow_r))
                    if a > 0:
                        pygame.draw.circle(glow_surf, (*APPLE_BASE, a), (glow_r, glow_r), i)
                self._apple_glow_sprites[glow_r] = glow_surf
            glow_surf.set_alpha(int((0.5 + 0.5 * math.sin(time_float * 3)) * 255))
            surf.blit(glow_surf, (int(sx - glow_r + shake_x), int(sy - glow_r + shake_y)), special_flags=pygame.BLEND_ADD)

        self.particles.sort_by_z()
        for p in self.particles:
            p.draw(surf, self)
        self._perf_timings['particles'] = (time.perf_counter() - _t0) * 1000

        if self.settings.get('vignette', POST_VIGNETTE_ENABLED):
            surf.blit(self.vignette_surf, (0, 0))

        _t0 = time.perf_counter()
        if self.state == GameState.START:
            draw_title_screen(surf, self, self.menu_selection, self.render_time)
        elif self.state == GameState.SETTINGS:
            draw_settings_screen(surf, self, self.menu_selection, self.settings,
                                 self.render_time, self._settings_previous_state == GameState.PAUSED)
        else:
            draw_ui(surf, shake_x, shake_y, self)
            draw_minimap(surf, self.snake, self.apple, self)

            if self.state == GameState.PAUSED:
                draw_pause_menu(surf, self, self.menu_selection)

            if self.state == GameState.GAME_OVER:
                draw_game_over(surf, self, self.menu_selection, self.score_count_up,
                               self.new_record_bounce_timer)
                if self._show_stats:
                    from ui import draw_stats_overlay
                    draw_stats_overlay(surf, self)

        # Fade overlay for transitions
        if self.fade_alpha > 0:
            fade_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fade_surf.fill((0, 0, 0, int(self.fade_alpha)))
            surf.blit(fade_surf, (0, 0))

        self.grade_overlay.fill((0, 0, 0, 0))
        if self.grade_warm_flash > 0:
            alpha = int(120 * min(1.0, self.grade_warm_flash / 0.15))
            pygame.draw.rect(self.grade_overlay, (255, 180, 80, alpha), (0, 0, WIDTH, HEIGHT))
        if self.grade_cool_shift > 0:
            alpha = int(60 * min(1.0, self.grade_cool_shift / 0.3))
            pygame.draw.rect(self.grade_overlay, (100, 140, 220, alpha), (0, 0, WIDTH, HEIGHT))
        if self.grade_death_darken > 0:
            t = min(1.0, self.grade_death_darken / 0.5)
            alpha = int(180 * t)
            gray = int(40 * t)
            pygame.draw.rect(self.grade_overlay, (gray, gray, gray, alpha), (0, 0, WIDTH, HEIGHT))
        surf.blit(self.grade_overlay, (0, 0))

        self._draw_birds(surf, time_float)

        if self._debug_overlay:
            from ui import draw_debug_overlay
            draw_debug_overlay(surf, self)

        self._perf_timings['ui'] = (time.perf_counter() - _t0) * 1000
        self._perf_timings['total'] = (time.perf_counter() - _t_frame) * 1000

        needs_full = (self._full_redraw_requested or
                      not self._tile_cache_valid or
                      self.eat_flash > 0 or
                      self.state in (GameState.PAUSED, GameState.GAME_OVER,
                                     GameState.START, GameState.SETTINGS) or
                       self.render_time == 0.0)
        self._full_redraw_requested = False

        if not needs_full:
            current = self._compute_dirty_rects(time_float, shake_x, shake_y)
            all_rects = self._prev_dirty_rects + current
            self._prev_dirty_rects = current
        else:
            self._prev_dirty_rects = []
            all_rects = [pygame.Rect(0, 0, WIDTH, HEIGHT)]

        merged = self._merge_rects(all_rects)
        if len(merged) == 1 and merged[0] == pygame.Rect(0, 0, WIDTH, HEIGHT):
            pygame.display.flip()
        else:
            pygame.display.update(merged)

    def run(self):
        sim_accumulator = 0.0
        particle_accumulator = 0.0
        self.render_time = 0.0

        while self.state != GameState.QUIT:
            raw_dt = self.clock.tick(RENDER_FPS) / 1000.0
            self.handle_events()

            if self.state == GameState.PLAYING:
                sim_accumulator += raw_dt
                while sim_accumulator >= FIXED_DT:
                    self.update(FIXED_DT)
                    sim_accumulator -= FIXED_DT
                    if self.state != GameState.PLAYING:
                        sim_accumulator = 0.0
                        break

                interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - self.score * SPEED_DECAY_PER_POINT)
                self.move_lerp = min(1.0, (self.move_timer + sim_accumulator) / interval)

            elif self.state == GameState.GAME_OVER:
                self._update_game_over_countup(raw_dt)
                self._update_transition(raw_dt)
                particle_accumulator += raw_dt
                while particle_accumulator >= FIXED_DT:
                    self.particles.update_all(FIXED_DT)
                    self.particles.clean()
                    particle_accumulator -= FIXED_DT

                self.ambient_time += raw_dt * 0.3
                day_cycle = math.sin(self.ambient_time * SUN_ANGLE_SPEED)
                self.audio.update(day_cycle, 0.0, raw_dt)

            elif self.state in (GameState.START, GameState.SETTINGS):
                self.ambient_time += raw_dt * 0.3
                day_cycle = math.sin(self.ambient_time * SUN_ANGLE_SPEED)
                self.audio.update(day_cycle, 0.0, raw_dt)
                self._update_transition(raw_dt)
                sim_accumulator = 0.0
                particle_accumulator = 0.0

            elif self.state == GameState.PAUSED:
                self._update_transition(raw_dt)
                sim_accumulator = 0.0
                particle_accumulator = 0.0

            self.render_time += raw_dt
            self.render()

        pygame.quit()
        sys.exit()

    def quit(self):
        self.persistence.save()
        self.state = GameState.QUIT


def main():
    _parse_cli_args()
    SnakeGame().run()


if __name__ == '__main__':
    main()
