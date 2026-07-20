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
from utils import (hex_side_normal, hex_to_pixel,
                   all_hexes, in_bounds, lerp_color,
                   mul_color, add_color, screen_shake_offset,
                   dot3, tile_noise, _perlin_cache,
                   wrap_coords, canonical_cell, compute_sun_light,
                   compute_sky_color, sample_spline_path,
                   hex_corner_height, hex_inner_corners,
                   rgb_to_hsv, hsv_to_rgb, nearest_period_offset)
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
    _CLI_ARGS = {'fullscreen': False, 'no_gl': False, 'quality': None}
    i = 0
    argv = sys.argv[1:]
    while i < len(argv):
        arg = argv[i]
        if arg == '--version':
            print(f'SnakeV2 v{__version__}')
            sys.exit(0)
        elif arg == '--fullscreen':
            _CLI_ARGS['fullscreen'] = True
        elif arg == '--windowed':
            _CLI_ARGS['fullscreen'] = False
        elif arg == '--no-gl':
            _CLI_ARGS['no_gl'] = True
        elif arg == '--quality':
            i += 1
            if i < len(argv) and argv[i] in QUALITY_PRESETS:
                _CLI_ARGS['quality'] = argv[i]
            else:
                print(f"Invalid quality '{argv[i] if i < len(argv) else '?'}'. Use: low, medium, high")
                sys.exit(1)
        elif arg in ('-h', '--help'):
            print('Usage: snakev2 [--windowed] [--fullscreen] [--no-gl] [--quality low|medium|high] [--version]')
            sys.exit(0)
        i += 1


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
        # Exactly one pacing authority should be active: display vsync when it
        # actually engages, otherwise the clock.tick(RENDER_FPS) software cap
        # in run(). set_mode(vsync=1) can silently fail to engage (driver
        # doesn't support it) even when it doesn't raise, so this is a
        # best-effort request flag, not a guarantee — but it's the only signal
        # pygame exposes short of querying the platform swap interval.
        self._vsync_active = False
        try:
            if VSYNC_ENABLED:
                try:
                    self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=1)
                    self._vsync_active = True
                except pygame.error:
                    self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
            else:
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
        self._prev_dirty_rects = []
        self._full_redraw_requested = True
        self._debug_overlay = False
        self._perf_timings = {}
        self._frame_times = deque(maxlen=FRAME_TIME_WINDOW)
        self._frame_count = 0
        self._wall_time = 0.0
        self._frame_timings = {}
        self._frame_stats = {'avg': 0.0, 'min': 0.0, 'max': 0.0, 'p50': 0.0, 'p95': 0.0, 'p99': 0.0}
        self._stats_dirty = True

        self.water_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._tile_cache = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._tile_cache_valid = False
        self.gl_renderer = GLRenderer()
        if _CLI_ARGS.get('no_gl'):
            self.gl_renderer.available = False
        self.camera = Camera()
        self.draw_cache = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        self._warned_no_numpy = False
        self._wrap_frame = False
        self._visual_dq = 0
        self._visual_dr = 0
        self._wrap_transition = {'active': False, 'timer': 0.0, 'duration': 0.0,
                                 'phase': 'none', 'roll_angle': 0.0, 'dive_amount': 0.0}

        self._last_camera_px = 0.0
        self._last_camera_py = 0.0
        self._last_tile_camera_px = 0.0
        self._last_tile_camera_py = 0.0
        self._camera_moved_threshold = 3.5
        self._ground_cache_valid = False
        self._dirty_tiles = set()
        self._height_map_valid = False
        self._height_map = {}
        self._rebuild_height_map()

        self.grade_warm_flash = 0.0
        self.grade_cool_shift = 0.0
        self.grade_death_darken = 0.0
        self.grade_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._fade_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

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
        self.renderer_name = 'opengl' if self.gl_renderer.available else 'software'
        quality_key = _CLI_ARGS.get('quality') or DEFAULT_QUALITY
        quality_preset = QUALITY_PRESETS.get(quality_key, QUALITY_PRESETS['high'])
        self.quality_level = quality_key

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
        self._grass_density = quality_preset.get('grass_density', GRASS_DENSITY_HIGH)
        for k in quality_preset:
            if k in self.settings:
                self.settings[k] = quality_preset[k]
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

    def _request_full_redraw(self):
        self._full_redraw_requested = True

    def _invalidate_tiles_near(self, coords, radius=2):
        for q, r in coords:
            for dq in range(-radius, radius + 1):
                for dr in range(-radius, radius + 1):
                    nq, nr = q + dq, r + dr
                    if in_bounds(nq, nr):
                        self._dirty_tiles.add((nq, nr))
        self._tile_cache_valid = False

    def _invalidate_all_tiles(self):
        self._dirty_tiles = set(all_hexes())
        self._tile_cache_valid = False

    def _rebuild_height_map(self):
        if self._height_map_valid:
            return
        self._height_map = {}
        for (_q, _r), _s in self._tile_static_cache.items():
            if 'height_offset' in _s:
                self._height_map[(_q, _r)] = _s['height_offset']
        self._height_map_valid = True

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

    def _compute_horizon_y(self):
        """Compute the projected horizon line Y in screen space.
        
        Projects a far ground-plane point along the camera's view direction
        to find where z=0 meets the view at infinity."""
        eye = self.camera.eye
        target = self.camera.target
        dx_ground = target[0] - eye[0]
        dy_ground = target[1] - eye[1]
        d_len = math.hypot(dx_ground, dy_ground)
        if d_len < 0.01:
            return HEIGHT * 0.5
        dx = dx_ground / d_len
        dy = dy_ground / d_len
        far_x = eye[0] + dx * 100000.0
        far_y = eye[1] + dy * 100000.0
        _, sy, _ = self.camera.project(far_x, far_y, 0)
        if sy < -999 or sy > HEIGHT * 2:
            return HEIGHT * 0.5
        return sy

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
            # Skip ground bottom during gameplay (side/rim faces cover it, avoids dark artifacts)
            if self.state != GameState.START:
                continue
            bot_pts = []
            valid = True
            for c_x, c_y, c_z in gs['bot_world']:
                sx_b, sy_b, _ = self.camera.project(c_x, c_y, c_z)
                if sx_b == -999:
                    valid = False
                    break
                bot_pts.append((sx_b, sy_b))
            if valid:
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
            eye_x, eye_y = self.camera.eye[0], self.camera.eye[1]
            for q, r in self._all_hexes_cache:
                cx, cy = tile_cache[(q, r)]['center_world']
                offset = nearest_period_offset(cx, cy, eye_x, eye_y)
                sx, sy, depth = self.camera.project(cx + offset[0], cy + offset[1], 0)
                if sx < -TILE_CLIP_MARGIN or sx > WIDTH + TILE_CLIP_MARGIN:
                    continue
                if sy < -TILE_CLIP_MARGIN or sy > HEIGHT + TILE_CLIP_MARGIN:
                    continue
                self._draw_tile_decorations(self._tile_cache, q, r, time_float, offset=offset)
            self._tile_cache_valid = True
            self._full_redraw_requested = False
            return

        cx, cy = self.camera.eye[0], self.camera.eye[1]
        dx = cx - self._last_tile_camera_px
        dy = cy - self._last_tile_camera_py
        camera_moved = math.hypot(dx, dy) >= self._camera_moved_threshold
        has_dirty = len(self._dirty_tiles) > 0
        if self._tile_cache_valid and not camera_moved and not has_dirty:
            return
        rebuild_all = not self._tile_cache_valid or camera_moved

        self._last_tile_camera_px, self._last_tile_camera_py = cx, cy
        time_float = self.render_time
        tile_cache = self._tile_static_cache
        all_hex = self._all_hexes_cache

        if rebuild_all:
            self._tile_cache.fill((0, 0, 0, 0))
            dirty_set = set(all_hex)
            self._dirty_tiles = set()
        else:
            dirty_set = self._dirty_tiles.copy()
            self._dirty_tiles = set()

        tile_items = []
        for q, r in dirty_set:
            cx_t, cy_t = tile_cache[(q, r)]['center_world']
            offset = nearest_period_offset(cx_t, cy_t, cx, cy)
            sx, sy, depth = self.camera.project(cx_t + offset[0], cy_t + offset[1], 0)
            if sx < -TILE_CLIP_MARGIN or sx > WIDTH + TILE_CLIP_MARGIN:
                continue
            if sy < -TILE_CLIP_MARGIN or sy > HEIGHT + TILE_CLIP_MARGIN:
                continue
            tile_items.append((depth, q, r, offset))
        tile_items.sort(key=lambda x: x[0], reverse=True)
        for _, q, r, offset in tile_items:
            self.draw_tile(self._tile_cache, q, r, time_float, offset=offset)
        self._tile_cache_valid = True

    def _draw_tile_decorations(self, surf, q, r, time_float, offset=(0.0, 0.0)):
        static = self._tile_static_cache[(q, r)]
        corners_world = static['corners_world']
        cx, cy = static['center_world']
        off_x, off_y = offset
        cx += off_x
        cy += off_y
        base_top_color_tuple = static['base_top_color']
        tex_variation = static['tex_variation']
        dist_factor = static['dist_factor']
        grass_seed = static['grass_seed']
        grass_blades = static['grass_blades']
        dist_from_center = static['dist_from_center']
        height_offset = static.get('height_offset', 0)

        self._rebuild_height_map()
        height_map = self._height_map
        if (q, r) not in height_map:
            height_map = dict(height_map)
            height_map[(q, r)] = height_offset

        corner_neighbor_map = [
            [DIR_VECTORS[0], DIR_VECTORS[5]],
            [DIR_VECTORS[0], DIR_VECTORS[1]],
            [DIR_VECTORS[1], DIR_VECTORS[2]],
            [DIR_VECTORS[2], DIR_VECTORS[3]],
            [DIR_VECTORS[3], DIR_VECTORS[4]],
            [DIR_VECTORS[4], DIR_VECTORS[5]],
        ]
        corner_heights = []
        for ci in range(6):
            h_total = height_offset
            h_count = 1
            for dq, dr in corner_neighbor_map[ci]:
                nk = (q + dq, r + dr)
                if nk in height_map:
                    h_total += height_map[nk]
                    h_count += 1
            corner_heights.append(h_total / h_count)

        inner_corners = hex_inner_corners(cx, cy, TILE_BEVEL)

        top_pts = []
        inner_top_pts = []
        for i, (c_x, c_y) in enumerate(corners_world):
            z_top = corner_heights[i]
            sx_t, sy_t, _ = self.camera.project(c_x + off_x, c_y + off_y, z_top)
            top_pts.append((sx_t, sy_t))
        for i, (ix, iy) in enumerate(inner_corners):
            z_top = corner_heights[i]
            sx_i, sy_i, _ = self.camera.project(ix, iy, z_top)
            inner_top_pts.append((sx_i, sy_i))

        cx_proj = sum(p[0] for p in inner_top_pts) / 6
        cy_proj = sum(p[1] for p in inner_top_pts) / 6

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
        _, _, depth = self.camera.project(cx, cy, height_offset)
        fog_t = max(0, min(1, (depth - FOG_NEAR) / (FOG_FAR - FOG_NEAR)))
        depth_fade = fog_t * DEPTH_FADE_STRENGTH
        depth_fade = depth_fade * (1.0 + fog_t) * 0.5 if fog_t > 0.3 else depth_fade * fog_t * 0.6
        if fog_t > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), self._fog_tint, fog_t * 0.35)
        if depth_fade > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), self._sky_hor, depth_fade)
        final_tri_color = mul_color(tuple(final_tri_color), tex_variation)

        # Dark crease at tile boundaries
        for i in range(6):
            j = (i + 1) % 6
            nq, nr = q + DIR_VECTORS[i][0], r + DIR_VECTORS[i][1]
            if self.state == GameState.PLAYING and in_bounds(nq, nr):
                continue
            edge_dark = mul_color(tuple(base_top_color), TILE_EDGE_SOFTEN * sun_factor * ao)
            pygame.draw.line(surf, edge_dark, top_pts[i], top_pts[j], 1)

        # Inner bevel highlights
        bevel_light = self._ambient + (1.0 - self._ambient) * max(0.0, dot3((0.0, 0.0, 1.0), self._light_dir))
        bevel_brightness = bevel_light * sun_factor * ao
        inner_hl = mul_color(TILE_EDGE_HIGHLIGHT, 0.15 * bevel_brightness)
        if emissive_edge > 0:
            inner_hl = add_color(inner_hl, mul_color(TILE_EDGE_EMISSIVE, emissive_edge * 0.5))
        for i in range(6):
            j = (i + 1) % 6
            nq, nr = q + DIR_VECTORS[i][0], r + DIR_VECTORS[i][1]
            if self.state == GameState.PLAYING and in_bounds(nq, nr):
                continue
            if i % 2 == 0:
                pygame.draw.line(surf, inner_hl, inner_top_pts[i], inner_top_pts[j], 1)

        crack_intensity = abs(static.get('noise', {}).get('crack', 0)) ** 3 * 0.3
        if crack_intensity > 0.05:
            crack_color = mul_color(final_tri_color, 0.7)
            for _ in range(int(crack_intensity * 3)):
                angle = random.uniform(0, math.tau)
                dist = random.uniform(1, HEX_SIZE * 0.4)
                ex = cx_proj + math.cos(angle) * dist
                ey = cy_proj + math.sin(angle) * dist
                pygame.draw.line(surf, crack_color, (int(cx_proj), int(cy_proj)), (int(ex), int(ey)), 1)

        rim_light = mul_color(TILE_EDGE_HIGHLIGHT, 0.2 * sun_factor * dist_factor * ao)
        for i in range(6):
            j = (i + 1) % 6
            edge_nx = inner_top_pts[j][1] - inner_top_pts[i][1]
            edge_ny = inner_top_pts[i][0] - inner_top_pts[j][0]
            el = math.hypot(edge_nx, edge_ny)
            if el > 0:
                edge_nx /= el
                edge_ny /= el
                rim = max(0.0, edge_nx * self._light_dir[0] + edge_ny * self._light_dir[1])
                if rim > 0.3:
                    pygame.draw.line(surf, rim_light, inner_top_pts[i], inner_top_pts[j], 1)

        grass_thresh = 0.1 / max(self._grass_density, 0.01)
        if grass_seed > grass_thresh and self.state != GameState.GAME_OVER:
            for blade in grass_blades:
                bx, by = blade['bx'], blade['by']
                blade_h, blade_w = blade['blade_h'], blade['blade_w']
                gc = blade['gc']

                compressed = False
                for sq, sr in self.snake:
                    sq_px, sq_py = hex_to_pixel(sq, sr)
                    dx_b = bx - sq_px
                    dy_b = by - sq_py
                    if math.hypot(dx_b, dy_b) < HEX_SIZE * 0.6:
                        compressed = True
                        break
                if compressed:
                    blade_h *= 0.3
                    gc = mul_color(gc, 0.85)

                sway = math.sin(time_float * 1.8 + bx * 0.4 + by * 0.3) * 2
                sx_b, sy_b, _ = self.camera.project(bx + off_x, by + off_y, 0)
                if sx_b == -999:
                    continue
                sx_t, sy_t, _ = self.camera.project(bx + sway + off_x, by + off_y, blade_h)
                if sx_t == -999:
                    continue
                pygame.draw.line(surf, gc, (int(sx_b), int(sy_b)), (int(sx_t), int(sy_t)), blade_w)
                if blade['has_flower']:
                    flower_sz = max(1, blade_w + 1) if not compressed else max(1, blade_w)
                    pygame.draw.circle(surf, blade['flower_color'], (int(sx_t), int(sy_t)), flower_sz)

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
        self._visual_dq = 0
        self._visual_dr = 0
        self._wrap_transition = {'active': False, 'timer': 0.0, 'duration': 0.0,
                                 'phase': 'none', 'roll_angle': 0.0, 'dive_amount': 0.0}
        self.path_history.clear()
        for sq, sr in self.snake:
            self.path_history.append((sq, sr, 0, 0))
        self.eat_anim = {'timer': 0, 'bulge_idx': -1, 'bulge_progress': 0}
        self.death_anim = {'timer': 0, 'phase': 'none'}
        self._death_snake_set = set()
        self._death_snake_timer = 0
        self.apple_anim = {'spawn_timer': 0, 'was_spawned': False}
        self.blink_timer = random.uniform(2, 5)
        self._countup_started = False
        self.score_count_up_timer = 0
        self.score_count_up = 0
        self.new_record_bounce_timer = 0
        self._wrap_frame = False
        self._invalidate_all_tiles()
        self._prev_snake_set = set(self.snake)
        self._height_map_valid = False
        hx, hy = hex_to_pixel(self.snake[0][0], self.snake[0][1])
        self.camera.snap_to(hx, hy, self.direction)
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

    def _next_head_unwrapped(self):
        q, r = self.snake[0]
        dq, dr = DIR_VECTORS[self.direction]
        raw_q, raw_r = q + dq, r + dr
        head_dq = self._visual_dq
        head_dr = self._visual_dr
        return (raw_q + head_dq * (2 * GRID_RADIUS + 1),
                raw_r + head_dr * (2 * GRID_RADIUS + 1))

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

        if wrapped:
            _, _, dq_add, dr_add = canonical_cell(q, r)
            self._visual_dq += dq_add
            self._visual_dr += dr_add
            self._wrap_frame = True
            # A second seam crossing can land inside an already-active transition
            # (e.g. a q-wrap then r-wrap near a corner at high speed — two seam
            # crossings fit easily inside WRAP_TRANSITION_DURATION at max speed).
            # Retriggering a fresh dict here would snap roll_angle/dive_amount
            # back to 0 mid-roll — exactly the hard cut Phase 14 forbids. The
            # in-flight transition already covers "hide the seam", so let it keep
            # running untouched; only start a new one if none is active.
            if not self._wrap_transition['active']:
                self._wrap_transition = {'active': True,
                                         'timer': WRAP_TRANSITION_DURATION,
                                         'duration': WRAP_TRANSITION_DURATION,
                                         'phase': 'dive',
                                         'roll_angle': 0.0,
                                         'dive_amount': 0.0}

        vis_dq = self._visual_dq
        vis_dr = self._visual_dr
        self.path_history.appendleft((wrapped_q, wrapped_r, vis_dq, vis_dr))

        # Direction change detection for banking & dust
        dir_changed = old_dir != self.direction
        if dir_changed:
            hx, hy = hex_to_pixel(new_head[0], new_head[1])
            ddx, ddy = DIR_VECTORS[self.direction]
            self.particles.emit_movement_dust(hx, hy, 0.5, -ddx, -ddy)
            turn_dir = 1 if (self.direction - old_dir) % 6 == 1 else -1
            self.camera.on_turn(turn_dir)

        # Forward movement dust at speed
        if self._speed_ratio > 0.3 and random.random() < self._speed_ratio * 0.4:
            tail = self.snake[-1]
            tpx, tpy = hex_to_pixel(tail[0], tail[1])
            self.particles.emit(
                tpx + random.uniform(-4, 4),
                tpy + random.uniform(-4, 4),
                0,
                random.uniform(-0.3, 0.3),
                random.uniform(-0.3, 0.3),
                random.uniform(0.1, 0.3),
                (160, 190, 150),
                random.uniform(1, 2),
                random.uniform(0.3, 0.6),
            )

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

        changed_tiles = set(self.snake)
        if hasattr(self, '_prev_snake_set'):
            changed_tiles.update(self._prev_snake_set)
        self._prev_snake_set = set(self.snake)
        if self.apple:
            changed_tiles.add(self.apple)
        if ate:
            changed_tiles.add(old_apple)
        self._invalidate_tiles_near(changed_tiles, radius=2)
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
        self._invalidate_all_tiles()
        self._request_full_redraw()
        # Mark tiles under snake for compression effect
        self._death_snake_set = set(self.snake)
        self._death_snake_timer = DEATH_ANIM_DURATION

    def _spawn_eat_particles(self, pos=None):
        if pos is None:
            pos = self.apple or self.snake[0]
        cx, cy = hex_to_pixel(*pos)
        self.particles.emit_apple_burst(cx, cy, 0)
        # Additional green ring burst around the head
        head_q, head_r = self.snake[0]
        hx, hy = hex_to_pixel(head_q, head_r)
        for _ in range(8):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(1, 3)
            self.particles.emit(
                hx + math.cos(angle) * 8,
                hy + math.sin(angle) * 8,
                0.5,
                math.cos(angle) * speed,
                math.sin(angle) * speed,
                random.uniform(0.5, 1.5),
                (100, 255, 150),
                random.uniform(1.5, 3),
                random.uniform(0.2, 0.5),
                'glow'
            )

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
                        self.turn_right()
                    elif event.key in (pygame.K_d, pygame.K_RIGHT):
                        self.turn_left()
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
                if self._death_snake_timer > 0:
                    self._death_snake_timer -= dt
                    # Spawn dissolve particles during death
                    if random.random() < 0.15 * (1.0 - self.death_anim['timer'] / DEATH_ANIM_DURATION):
                        idx = random.randint(0, len(self.snake) - 1)
                        sq, sr = self.snake[idx]
                        scx, scy = hex_to_pixel(sq, sr)
                        self.particles.emit(
                            scx + random.uniform(-8, 8),
                            scy + random.uniform(-8, 8),
                            random.uniform(0, 2),
                            random.uniform(-0.5, 0.5),
                            random.uniform(-0.5, 0.5),
                            random.uniform(0.5, 2),
                            (80, 200, 100),
                            random.uniform(1, 3),
                            random.uniform(0.5, 1.5),
                            'glow'
                        )
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

        # Wrap transition: dive → world roll → emerge
        if self._wrap_transition['active']:
            wt = self._wrap_transition
            wt['timer'] -= dt
            if wt['timer'] <= 0:
                wt['active'] = False
                wt['timer'] = 0
                wt['phase'] = 'none'
                wt['roll_angle'] = 0.0
                wt['dive_amount'] = 0.0
            else:
                progress = 1.0 - wt['timer'] / wt['duration']
                dive_end = WRAP_DIVE_FRAC
                roll_end = dive_end + WRAP_ROLL_FRAC
                if progress <= dive_end:
                    wt['phase'] = 'dive'
                    wt['dive_amount'] = progress / dive_end
                    wt['roll_angle'] = 0.0
                elif progress <= roll_end:
                    wt['phase'] = 'roll'
                    wt['dive_amount'] = 1.0
                    roll_p = (progress - dive_end) / WRAP_ROLL_FRAC
                    wt['roll_angle'] = math.pi * roll_p
                else:
                    wt['phase'] = 'emerge'
                    emerge_p = (progress - roll_end) / (1.0 - roll_end) if progress < 1.0 else 1.0
                    wt['dive_amount'] = 1.0 - emerge_p
                    wt['roll_angle'] = math.pi

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
            self._invalidate_all_tiles()
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

        q_head, r_head = self.snake[0]
        hx, hy = hex_to_pixel(q_head, r_head)
        self.camera.follow_snake(hx, hy, self.direction, dt, self._speed_ratio, build_matrices=False)
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

    def draw_tile(self, surf, q, r, time_float, offset=(0.0, 0.0)):
        static = self._tile_static_cache[(q, r)]
        corners_world = static['corners_world']
        cx, cy = static['center_world']
        off_x, off_y = offset
        cx += off_x
        cy += off_y
        base_top_color_tuple = static['base_top_color']
        base_side_color_tuple = static['base_side_color']
        tex_variation = static['tex_variation']
        dist_factor = static['dist_factor']
        grass_seed = static['grass_seed']
        grass_blades = static['grass_blades']
        height_offset = static.get('height_offset', 0)
        noise = static.get('noise', {})

        self._rebuild_height_map()
        height_map = self._height_map
        if (q, r) not in height_map:
            height_map = dict(height_map)
            height_map[(q, r)] = height_offset

        # Compute per-corner heights (average of up to 3 neighboring tiles)
        corner_heights = []
        corner_neighbor_map = [
            [DIR_VECTORS[0], DIR_VECTORS[5]],
            [DIR_VECTORS[0], DIR_VECTORS[1]],
            [DIR_VECTORS[1], DIR_VECTORS[2]],
            [DIR_VECTORS[2], DIR_VECTORS[3]],
            [DIR_VECTORS[3], DIR_VECTORS[4]],
            [DIR_VECTORS[4], DIR_VECTORS[5]],
        ]
        for ci in range(6):
            h_total = height_offset
            h_count = 1
            for dq, dr in corner_neighbor_map[ci]:
                nk = (q + dq, r + dr)
                if nk in height_map:
                    h_total += height_map[nk]
                    h_count += 1
            corner_heights.append(h_total / h_count)

        # Inner corners for bevel
        inner_corners = hex_inner_corners(cx, cy, TILE_BEVEL)

        top_pts = []
        inner_top_pts = []
        bot_pts = []
        for i, (c_x, c_y) in enumerate(corners_world):
            z_top = corner_heights[i]
            z_bot = corner_heights[i] - TILE_HEIGHT
            sx_t, sy_t, _ = self.camera.project(c_x + off_x, c_y + off_y, z_top)
            sx_b, sy_b, _ = self.camera.project(c_x + off_x, c_y + off_y, z_bot)
            top_pts.append((sx_t, sy_t))
            bot_pts.append((sx_b, sy_b))
        for i, (ix, iy) in enumerate(inner_corners):
            z_top = corner_heights[i]
            sx_i, sy_i, _ = self.camera.project(ix, iy, z_top)
            inner_top_pts.append((sx_i, sy_i))

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
        _, _, depth = self.camera.project(cx, cy, height_offset)
        fog_t = max(0, min(1, (depth - FOG_NEAR) / (FOG_FAR - FOG_NEAR)))
        depth_fade = fog_t * DEPTH_FADE_STRENGTH
        depth_fade = depth_fade * (1.0 + fog_t) * 0.5 if fog_t > 0.3 else depth_fade * fog_t * 0.6
        if fog_t > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), self._fog_tint, fog_t * 0.35)
        if depth_fade > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), self._sky_hor, depth_fade)
        final_tri_color = mul_color(tuple(final_tri_color), tex_variation)

        # Draw bevel ring (between outer and inner hex) with angled normal
        bevel_color = mul_color(tuple(base_top_color), light * 0.85)
        bevel_fade = depth_fade * 0.9
        if bevel_fade > 0:
            bevel_color = lerp_color(bevel_color, self._sky_hor, bevel_fade)
        bevel_color = mul_color(bevel_color, tex_variation)

        for i in range(6):
            j = (i + 1) % 6
            bevel_quad = [top_pts[i], top_pts[j], inner_top_pts[j], inner_top_pts[i]]

            # Bevel normal: 45-degree blend between top and side normal
            ns_x, ns_y, ns_z = hex_side_normal(i)
            bevel_n = (ns_x * 0.5, ns_y * 0.5, 0.7071)
            bn_len = math.sqrt(bevel_n[0]**2 + bevel_n[1]**2 + bevel_n[2]**2)
            bevel_n = (bevel_n[0]/bn_len, bevel_n[1]/bn_len, bevel_n[2]/bn_len)
            bevel_diff = max(0.0, dot3(bevel_n, self._light_dir))
            bevel_light = (self._ambient + (1.0 - self._ambient) * bevel_diff) * sun_factor * dist_factor * ao
            bevel_shade = mul_color(tuple(base_top_color), bevel_light * 0.9)
            if depth_fade > 0:
                bevel_shade = lerp_color(bevel_shade, self._sky_hor, depth_fade)
            bevel_shade = mul_color(bevel_shade, tex_variation)

            pygame.draw.polygon(surf, bevel_shade, bevel_quad)

            # Bevel edge highlights
            nq, nr = q + DIR_VECTORS[i][0], r + DIR_VECTORS[i][1]
            if self.state == GameState.PLAYING and in_bounds(nq, nr):
                continue

            # Subtle seam at tile boundary
            edge_dark = mul_color(bevel_shade, TILE_EDGE_SOFTEN)
            pygame.draw.line(surf, edge_dark, top_pts[i], top_pts[j], 1)

            # Bright highlight on inner bevel edge
            if i % 2 == 0:
                hl_light = mul_color(TILE_EDGE_HIGHLIGHT, 0.15 * sun_factor * ao)
                pygame.draw.line(surf, hl_light, inner_top_pts[i], inner_top_pts[j], 1)

        # Draw top face (inner hexagon)
        pygame.draw.polygon(surf, final_tri_color, inner_top_pts)

        # Edge definition between adjacent tiles: thin dark lines
        for i in range(6):
            j = (i + 1) % 6
            nq, nr = q + DIR_VECTORS[i][0], r + DIR_VECTORS[i][1]
            if self.state == GameState.PLAYING and in_bounds(nq, nr):
                seam_color = mul_color(final_tri_color, TILE_EDGE_SOFTEN)
                pygame.draw.line(surf, seam_color, top_pts[i], top_pts[j], 1)
                # Tiny highlight on one side for bevel definition
                if i % 2 == 0:
                    hl_seam = mul_color(TILE_EDGE_HIGHLIGHT, 0.08 * sun_factor * ao)
                    pygame.draw.line(surf, hl_seam,
                                    ((top_pts[i][0] + inner_top_pts[i][0]) / 2,
                                     (top_pts[i][1] + inner_top_pts[i][1]) / 2),
                                    ((top_pts[j][0] + inner_top_pts[j][0]) / 2,
                                     (top_pts[j][1] + inner_top_pts[j][1]) / 2), 1)

        # Draw side faces
        for i in range(6):
            j = (i + 1) % 6
            nq, nr = q + DIR_VECTORS[i][0], r + DIR_VECTORS[i][1]
            if self.state == GameState.PLAYING and in_bounds(nq, nr):
                continue
            quad = [top_pts[i], top_pts[j], bot_pts[j], bot_pts[i]]
            nx_s, ny_s, nz_s = hex_side_normal(i)
            diff_side = max(0.0, nx_s * self._light_dir[0] + ny_s * self._light_dir[1] + nz_s * self._light_dir[2])
            side_light = (self._ambient + (1.0 - self._ambient) * diff_side) * sun_factor * dist_factor * ao

            side_ao = 1.0 - 0.12 * (1.0 - abs(diff_side))
            side_light *= side_ao

            side_noise_val = noise.get('detail', 0) * 0.08
            # Floor kept high enough that even distant corner rims never read as
            # pure black (which looks like a hole in the board). The parallelogram
            # board's corners are far enough that dist_factor drives side_light
            # very low, so this floor matters at the rim.
            side_light = max(0.18, side_light + side_noise_val)

            sc_top = mul_color(tuple(base_side_color), side_light * 1.1)
            if depth_fade > 0:
                sc_top = lerp_color(sc_top, self._sky_hor, depth_fade)
            pygame.draw.polygon(surf, sc_top, quad)

            # Side face top edge highlight
            edge_highlight = mul_color(TILE_EDGE_HIGHLIGHT, 0.2 * max(0.3, side_light))
            pygame.draw.line(surf, edge_highlight, quad[0], quad[1], 1)

        # Crack effect on inner top face
        crack_intensity = abs(noise.get('crack', 0)) ** 3 * 0.3
        if crack_intensity > 0.05:
            crack_color = mul_color(final_tri_color, 0.7)
            for _ in range(int(crack_intensity * 3)):
                angle = random.uniform(0, math.tau)
                dist = random.uniform(1, HEX_SIZE * 0.4)
                ex = cx_proj + math.cos(angle) * dist
                ey = cy_proj + math.sin(angle) * dist
                pygame.draw.line(surf, crack_color, (int(cx_proj), int(cy_proj)), (int(ex), int(ey)), 1)

        # Rim lighting on top face edges
        rim_light = mul_color(TILE_EDGE_HIGHLIGHT, 0.2 * sun_factor * dist_factor * ao)
        for i in range(6):
            j = (i + 1) % 6
            edge_nx = top_pts[j][1] - top_pts[i][1]
            edge_ny = top_pts[i][0] - top_pts[j][0]
            el = math.hypot(edge_nx, edge_ny)
            if el > 0:
                edge_nx /= el
                edge_ny /= el
                rim = max(0.0, edge_nx * self._light_dir[0] + edge_ny * self._light_dir[1])
                if rim > 0.3:
                    pygame.draw.line(surf, rim_light, inner_top_pts[i], inner_top_pts[j], 1)

        grass_thresh = 0.1 / max(self._grass_density, 0.01)
        if grass_seed > grass_thresh and self.state != GameState.GAME_OVER:
            for blade in grass_blades:
                bx, by = blade['bx'], blade['by']
                blade_h, blade_w = blade['blade_h'], blade['blade_w']
                gc = blade['gc']
                sway = math.sin(time_float * 1.8 + bx * 0.4 + by * 0.3) * 2

                # Check if snake compresses this blade
                compressed = False
                for sq, sr in self.snake:
                    sq_px, sq_py = hex_to_pixel(sq, sr)
                    dx_b = bx - sq_px
                    dy_b = by - sq_py
                    if math.hypot(dx_b, dy_b) < HEX_SIZE * 0.6:
                        compressed = True
                        break
                if compressed:
                    blade_h *= 0.3
                    gc = mul_color(gc, 0.85)

                sx_b, sy_b, _ = self.camera.project(bx + off_x, by + off_y, 0)
                if sx_b == -999:
                    continue
                sx_t, sy_t, _ = self.camera.project(bx + sway + off_x, by + off_y, blade_h)
                if sx_t == -999:
                    continue
                pygame.draw.line(surf, gc, (int(sx_b), int(sy_b)), (int(sx_t), int(sy_t)), blade_w)
                if blade['has_flower']:
                    flower_sz = max(1, blade_w + 1) if not compressed else max(1, blade_w)
                    pygame.draw.circle(surf, blade['flower_color'], (int(sx_t), int(sy_t)), flower_sz)

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
        if sx == -999:
            return
        scaled = pygame.transform.smoothscale(self.soft_shadow_sprite, (shadow_size, shadow_size))
        scaled.set_alpha(int(alpha))
        surf.blit(scaled, (int(sx - shadow_size // 2), int(sy - shadow_size // 2)))

    def _subsample_spline_positions(self, lerp_t):
        """Subsample the low-res spline to produce high-res body positions.
        
        Uses the already-computed _spline_positions (one sample per cell,
        already interpolated with lerp_t) to generate n_high evenly-spaced
        samples by linear interpolation between adjacent low-res samples.
        This avoids the discontinuity caused by computing two independent
        Catmull-Rom splines that diverge at the move-step boundary.
        """
        sp = self._spline_positions
        if not sp or len(sp) < 2:
            return sp if sp else None
        n_high = min(len(self.snake) * 10, MAX_RENDER_SPLINE_SAMPLES)
        result_high = []
        for k in range(n_high):
            f = k / (n_high - 1) if n_high > 1 else 0.0
            seg_idx = f * (len(sp) - 1)
            i = int(seg_idx)
            t = seg_idx - i
            if i + 1 < len(sp):
                px0, py0, tx0, ty0 = sp[i]
                px1, py1, _, _ = sp[i + 1]
                px = px0 + (px1 - px0) * t
                py = py0 + (py1 - py0) * t
                result_high.append((px, py, tx0, ty0))
            else:
                result_high.append(sp[-1])
        return result_high

    def _compute_body_segments(self, time_float):
        """Compute body tube segments.

        Returns (segments, submerged_start) where segments is a list of
        (depth, sx, sy, r, c) in head-to-tail order (unchanged shape — the
        checker reads this via _body_segments_raw), and submerged_start is
        the index in that list from which segments are "submerged" — past
        the wrap-transition seam and meant to be physically occluded by
        terrain rather than just tinted. submerged_start == len(segments)
        when no transition is active (nothing submerged)."""
        if not hasattr(self, '_render_spline_positions') or not self._render_spline_positions:
            return [], 0

        positions = self._render_spline_positions
        n_pts = len(positions)

        body_pulse = 1.0 + 0.03 * math.sin(time_float * 2)
        idle_sway = 0
        if self.state == GameState.PLAYING and self.move_timer < 0.05:
            idle_sway = math.sin(time_float * 1.5) * 0.3

        segments = []
        submerged_start = None
        consecutive_offscreen = 0
        margin = SNAKE_RENDER_CULL_MARGIN
        for i in range(n_pts):
            cx, cy, tx, ty = positions[i]

            # Viewport culling: roughly estimate screen position before full projection
            # Quick 2D check: skip segments clearly outside viewport bounds
            # Full projection happens later for segments that pass the quick check
            t = i / max(1, n_pts - 1)
            thickness_factor = 1.0 - (t ** 2.2) * 0.65
            thickness_factor += 0.04 * math.sin(t * math.pi * 1.5)
            if t < 0.12:
                neck_ramp = (0.12 - t) / 0.12
                thickness_factor += 0.15 * neck_ramp
            if t > 0.92:
                tail_pinch = (t - 0.92) / 0.08
                thickness_factor *= 1.0 - 0.5 * tail_pinch

            # Slight overlap: segments slightly larger than their spacing
            overlap_scale = 1.08
            w = (HEX_SIZE * SNAKE_SEGMENT_SCALE * 0.5) * thickness_factor * body_pulse * overlap_scale

            # Eat bulge — map snake segment index to render positions
            eat_glow = 0.0
            if self.eat_anim['timer'] > 0:
                bulge_render_idx = self.eat_anim['bulge_idx'] * 10
                dist = abs(i - bulge_render_idx)
                if dist < 8:
                    bulge_factor = max(0, 1 - dist / 8)
                    bulge = 1.0 + 0.4 * math.sin(self.eat_anim['bulge_progress'] * math.pi) * bulge_factor
                    w *= bulge
                    # Warm glow pulse that travels with the bulge
                    eat_glow = 0.3 * bulge_factor * math.sin(self.eat_anim['bulge_progress'] * math.pi)

            # Death collapse
            if self.death_anim['phase'] != 'none':
                death_t = 1.0 - min(1.0, self.death_anim['timer'] / DEATH_ANIM_DURATION)
                head_factor = 1.0 - t
                collapse = 1.0 - death_t * 0.5 * head_factor
                w *= max(0.05, collapse)

            # Slither wave (skip head, ramp in over first segment)
            if SLITHER_AMPLITUDE > 0 and i > 5:
                t_len = math.hypot(tx, ty)
                if t_len > 0.001:
                    perp_x = -ty / t_len
                    perp_y = tx / t_len
                    wave_offset = SLITHER_AMPLITUDE * math.sin(
                        (i / 10.0) / max(0.5, SLITHER_WAVELENGTH) * math.tau
                        + time_float * 6
                    )
                    head_ramp = min(1.0, (i - 5) / 10.0)
                    wave_offset *= head_ramp
                    cx += perp_x * (wave_offset + idle_sway * 0.5)
                    cy += perp_y * (wave_offset + idle_sway * 0.5)

            # Squash/stretch during movement
            move_pulse = 1.0
            if self.state == GameState.PLAYING and self.move_lerp > 0:
                move_pulse = 1.0 + 0.05 * math.sin(self.move_lerp * math.pi * 2)

            # Project to screen
            sx, sy, depth = self.camera.project(cx, cy, 0)
            if sx == -999:
                consecutive_offscreen += 1
                if consecutive_offscreen > MAX_CONSECUTIVE_OFFSCREEN:
                    break
                continue

            on_screen = (-margin <= sx <= WIDTH + margin and -margin <= sy <= HEIGHT + margin)
            if not on_screen:
                consecutive_offscreen += 1
                if consecutive_offscreen > MAX_CONSECUTIVE_OFFSCREEN and len(segments) > 0:
                    break
                continue
            consecutive_offscreen = 0

            # Smooth color interpolation along the snake length
            color_t = t * (len(SNAKE_COLORS) - 1)
            c_idx1 = int(color_t)
            c_idx2 = min(c_idx1 + 1, len(SNAKE_COLORS) - 1)
            local_t = color_t - c_idx1
            base_color = lerp_color(SNAKE_COLORS[c_idx1], SNAKE_COLORS[c_idx2], local_t)

            # Smooth transition from HEAD_COLOR at the very front
            if t < 0.1:
                head_blend = t / 0.1
                base_color = lerp_color(HEAD_COLOR, base_color, head_blend)

            # Lighting with rim/Fresnel enhancement
            light_diff = max(0.0, self._light_dir[2])
            light = self._ambient + (1.0 - self._ambient) * light_diff
            c = mul_color(base_color, light)
            c = add_color(c, mul_color(self._sun_color, light * 0.2))

            # Fresnel rim glow (stronger on sides)
            rim_intensity = (1.0 - abs(dot3((tx, ty, 0), self._light_dir))) ** 2 * 0.3
            c = add_color(c, mul_color(HEAD_HIGHLIGHT, rim_intensity))

            # Eat glow pulse
            if eat_glow > 0:
                warm_glow = (255, 200, 100)
                c = add_color(c, mul_color(warm_glow, eat_glow))

            # Wrap transition: body past the seam is "submerged" — presented
            # as behind terrain (drawn in the under-seam pass, before the
            # terrain occluder) rather than merely tinted. Still apply a
            # fade for the segments right at the boundary so the seam edge
            # isn't a hard cut even though the terrain occluder now does the
            # actual hiding.
            is_submerged = False
            if self._wrap_transition['active']:
                wt = self._wrap_transition
                seam_t = 0.95 - 0.2 * wt['dive_amount']
                if t > seam_t:
                    is_submerged = True
                    seam_fade = 1.0 - min(1.0, (t - seam_t) / 0.1)
                    c = mul_color(c, max(0.3, seam_fade))

            # Death fade and dissolve
            if self.death_anim['phase'] != 'none':
                death_t = 1.0 - min(1.0, self.death_anim['timer'] / DEATH_ANIM_DURATION)
                fade = 1.0 - death_t * 0.7
                # Late-stage dissolve: segments near tail disappear first
                if death_t > 0.5:
                    dissolve_threshold = (death_t - 0.5) * 2.0
                    if t < dissolve_threshold:
                        fade = 0
                    else:
                        fade *= 1.0 - (death_t - 0.5)
                c = mul_color(c, fade)

            r = max(1, int(w * move_pulse))
            if is_submerged and submerged_start is None:
                submerged_start = len(segments)
            segments.append((depth, int(sx), int(sy), r, c))

        if submerged_start is None:
            submerged_start = len(segments)
        return segments, submerged_start

    def _draw_body_strip(self, surf, body_segments, draw_head_cap=True, draw_tail_cap=True):
        """Draw body as a continuous filled polygon strip (tube, not spheres).

        draw_head_cap/draw_tail_cap control the neck/tail end caps — set to
        False when body_segments is a partial slice (e.g. the emerged half
        of a wrap-transition split) whose cut boundary isn't the snake's
        real head or tail, so no cap belongs there."""
        if len(body_segments) < 2:
            return
        squash = BODY_SQUASH

        # Main body quads
        for i in range(len(body_segments) - 1):
            _, sx0, sy0, r0, c = body_segments[i]
            _, sx1, sy1, r1, _ = body_segments[i + 1]
            dx = sx1 - sx0
            dy = sy1 - sy0
            dist = math.hypot(dx, dy)
            if dist < 0.5:
                continue
            perp_x = -dy / dist
            perp_y = dx / dist
            l0_x = int(sx0 + perp_x * r0)
            l0_y = int(sy0 + perp_y * (r0 * squash))
            r0_x = int(sx0 - perp_x * r0)
            r0_y = int(sy0 - perp_y * (r0 * squash))
            l1_x = int(sx1 + perp_x * r1)
            l1_y = int(sy1 + perp_y * (r1 * squash))
            r1_x = int(sx1 - perp_x * r1)
            r1_y = int(sy1 - perp_y * (r1 * squash))
            poly = [(l0_x, l0_y), (l1_x, l1_y), (r1_x, r1_y), (r0_x, r0_y)]
            pygame.draw.polygon(surf, c, poly)

        # Dorsal highlight strip — offset by light direction, not fixed angle
        hl_width_frac = 0.30
        hl_offset_frac = 0.30
        light_screen_dx = self._light_dir[0]
        light_screen_dy = self._light_dir[1]
        light_screen_len = math.hypot(light_screen_dx, light_screen_dy)
        if light_screen_len > 0.001:
            light_screen_dx /= light_screen_len
            light_screen_dy /= light_screen_len
        else:
            light_screen_dx, light_screen_dy = 0.0, -1.0
        for i in range(len(body_segments) - 1):
            _, sx0, sy0, r0, c = body_segments[i]
            _, sx1, sy1, r1, _ = body_segments[i + 1]
            dx = sx1 - sx0
            dy = sy1 - sy0
            dist = math.hypot(dx, dy)
            if dist < 0.5:
                continue
            perp_x = -dy / dist
            perp_y = dx / dist
            hl_dir_x = perp_x * light_screen_dx + perp_y * light_screen_dy
            hl_dir_y = perp_y * light_screen_dx - perp_x * light_screen_dy
            hl_dir_sign = 1.0 if hl_dir_x > 0 else -1.0
            hl_r0 = r0 * hl_width_frac
            hl_r1 = r1 * hl_width_frac
            off_x = perp_x * (r0 * hl_offset_frac * hl_dir_sign)
            off_y = perp_y * (r0 * squash * hl_offset_frac * hl_dir_sign)
            off_x1 = perp_x * (r1 * hl_offset_frac * hl_dir_sign)
            off_y1 = perp_y * (r1 * squash * hl_offset_frac * hl_dir_sign)
            hl_l0_x = int(sx0 + off_x + perp_x * hl_r0 * hl_dir_sign)
            hl_l0_y = int(sy0 + off_y + perp_y * hl_r0 * squash * hl_dir_sign)
            hl_r0_x = int(sx0 + off_x - perp_x * hl_r0 * hl_dir_sign)
            hl_r0_y = int(sy0 + off_y - perp_y * hl_r0 * squash * hl_dir_sign)
            hl_l1_x = int(sx1 + off_x1 + perp_x * hl_r1 * hl_dir_sign)
            hl_l1_y = int(sy1 + off_y1 + perp_y * hl_r1 * squash * hl_dir_sign)
            hl_r1_x = int(sx1 + off_x1 - perp_x * hl_r1 * hl_dir_sign)
            hl_r1_y = int(sy1 + off_y1 - perp_y * hl_r1 * squash * hl_dir_sign)
            hl_c = add_color(c, (30, 30, 30))
            hl_poly = [(hl_l0_x, hl_l0_y), (hl_l1_x, hl_l1_y),
                        (hl_r1_x, hl_r1_y), (hl_r0_x, hl_r0_y)]
            pygame.draw.polygon(surf, hl_c, hl_poly)

        # Darker underside opposite the highlight side
        us_dark = 0.78
        us_frac = 0.40
        for i in range(len(body_segments) - 1):
            _, sx0, sy0, r0, c = body_segments[i]
            _, sx1, sy1, r1, _ = body_segments[i + 1]
            dx = sx1 - sx0
            dy = sy1 - sy0
            dist = math.hypot(dx, dy)
            if dist < 0.5:
                continue
            perp_x = -dy / dist
            perp_y = dx / dist
            hl_dir_x = perp_x * light_screen_dx + perp_y * light_screen_dy
            us_sign = -1.0 if hl_dir_x > 0 else 1.0
            pt_l0 = (int(sx0 + perp_x * r0), int(sy0 + perp_y * r0 * squash))
            pt_r0 = (int(sx0 - perp_x * r0), int(sy0 - perp_y * r0 * squash))
            pt_l1 = (int(sx1 + perp_x * r1), int(sy1 + perp_y * r1 * squash))
            pt_r1 = (int(sx1 - perp_x * r1), int(sy1 - perp_y * r1 * squash))
            mid0_x = sx0 + perp_x * r0 * us_sign * (1.0 - us_frac)
            mid0_y = sy0 + perp_y * r0 * squash * us_sign * (1.0 - us_frac)
            mid1_x = sx1 + perp_x * r1 * us_sign * (1.0 - us_frac)
            mid1_y = sy1 + perp_y * r1 * squash * us_sign * (1.0 - us_frac)
            edge0 = pt_r0 if us_sign < 0 else pt_l0
            edge1 = pt_r1 if us_sign < 0 else pt_l1
            us_c = mul_color(c, us_dark)
            pygame.draw.polygon(surf, us_c,
                [(int(mid0_x), int(mid0_y)),
                 edge0, edge1, (int(mid1_x), int(mid1_y))])

        # End caps: neck circle (under head) and tapered tail tip
        if draw_head_cap and len(body_segments) >= 2:
            _, sx0, sy0, r0, c0 = body_segments[0]
            _, sx1, sy1, r1, _ = body_segments[1]
            dx_n = sx0 - sx1
            dy_n = sy0 - sy1
            dn = math.hypot(dx_n, dy_n)
            if dn > 0.5:
                dx_n /= dn; dy_n /= dn
            pygame.draw.ellipse(surf, c0,
                                (int(sx0 - r0), int(sy0 - r0 * squash),
                                 int(r0 * 2), int(r0 * squash * 2)))
        if draw_tail_cap and len(body_segments) >= 2:
            _, sxn, syn, rn, cn = body_segments[-1]
            _, sxp, syp, rp, _ = body_segments[-2]
            dx_t = sxn - sxp
            dy_t = syn - syp
            dt = math.hypot(dx_t, dy_t)
            if dt > 0.5:
                dx_t /= dt; dy_t /= dt
            tip_x = int(sxn + dx_t * rn * 0.8)
            tip_y = int(syn + dy_t * rn * squash * 0.8)
            lx = int(sxn - dy_t * rn)
            ly = int(syn + dx_t * rn * squash)
            rx = int(sxn + dy_t * rn)
            ry = int(syn - dx_t * rn * squash)
            pygame.draw.polygon(surf, cn, [(lx, ly), (rx, ry), (tip_x, tip_y)])

    def _draw_continuous_shadow(self, surf):
        """Draw contact shadow onto a separate transparent surface, blit once.
        This prevents double-darkening where quads overlap."""
        positions = getattr(self, '_render_spline_positions', None)
        if not positions or len(positions) < 2:
            return
        n = len(positions)
        light_dir = self._light_dir
        if light_dir[2] <= 0.001:
            return

        factor = 1.0 / light_dir[2]

        # Wrap transition: match _compute_body_segments' submerged boundary
        # so no orphaned shadow patch is left floating above a body sample
        # that's already been hidden behind the terrain occluder.
        wt_active = self._wrap_transition['active']
        seam_t = 1.0
        if wt_active:
            seam_t = 0.95 - 0.2 * self._wrap_transition['dive_amount']

        proj_left = []
        proj_right = []
        consec_off = 0
        for i, (wx, wy, tx, ty) in enumerate(positions):
            t = i / max(1, n - 1)
            if wt_active and t > seam_t:
                proj_left.append(None)
                proj_right.append(None)
                continue
            thickness = 1.0 - (t ** 1.8) * 0.65
            thickness += 0.04 * math.sin(t * math.pi * 1.5)
            w = (HEX_SIZE * SNAKE_SEGMENT_SCALE * 0.5) * thickness * 1.3

            swx = wx + light_dir[0] * factor * 0.3
            swy = wy + light_dir[1] * factor * 0.3

            t_len = math.hypot(tx, ty)
            if t_len < 0.001:
                proj_left.append(None)
                proj_right.append(None)
                continue
            perp_x = -ty / t_len
            perp_y = tx / t_len

            ex1, ey1, _ = self.camera.project(swx + perp_x * w, swy + perp_y * w, 0)
            ex2, ey2, _ = self.camera.project(swx - perp_x * w, swy - perp_y * w, 0)
            if ex1 == -999 or ex2 == -999:
                proj_left.append(None)
                proj_right.append(None)
                consec_off += 1
                if consec_off > MAX_CONSECUTIVE_OFFSCREEN and len(proj_left) > 5:
                    break
                continue
            consec_off = 0
            proj_left.append((ex1, ey1))
            proj_right.append((ex2, ey2))

        min_x, min_y = 99999, 99999
        max_x, max_y = -99999, -99999
        quads = []
        for i in range(len(proj_left) - 1):
            if proj_left[i] is None or proj_left[i + 1] is None:
                continue
            if proj_right[i] is None or proj_right[i + 1] is None:
                continue
            quad = [proj_left[i], proj_left[i + 1], proj_right[i + 1], proj_right[i]]
            for x, y in quad:
                min_x, min_y = min(min_x, int(x)), min(min_y, int(y))
                max_x, max_y = max(max_x, int(x)), max(max_y, int(y))
            quads.append(quad)

        if not quads:
            return

        pad = 4
        bw = max_x - min_x + pad * 2
        bh = max_y - min_y + pad * 2
        if bw <= 0 or bh <= 0:
            return

        try:
            shadow_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 0))
        except pygame.error:
            return

        offset_x, offset_y = min_x - pad, min_y - pad
        solid_black = (0, 0, 0, 255)
        for quad in quads:
            local_quad = [(int(x - offset_x), int(y - offset_y)) for x, y in quad]
            pygame.draw.polygon(shadow_surf, solid_black, local_quad)

        if SHADOW_SOFT:
            oversample = 8
            small_w, small_h = max(1, bw // oversample), max(1, bh // oversample)
            small = pygame.transform.smoothscale(shadow_surf, (small_w, small_h))
            shadow_surf = pygame.transform.smoothscale(small, (bw, bh))

        shadow_alpha = SHADOW_ALPHA
        if self._wrap_transition['active']:
            shadow_alpha = int(SHADOW_ALPHA * (1.0 - self._wrap_transition['dive_amount'] * 0.6))
        if self.death_anim['phase'] != 'none':
            death_t = 1.0 - min(1.0, self.death_anim['timer'] / DEATH_ANIM_DURATION)
            shadow_alpha = int(SHADOW_ALPHA * (1.0 - death_t))
        shadow_surf.set_alpha(shadow_alpha)
        surf.blit(shadow_surf, (offset_x, offset_y))

    def _head_is_hidden(self):
        """True at the midpoint of an active world roll (roll_angle near
        pi/2, the instant the world is edge-on to the camera). Shared by
        draw_snake_segment's head sprite/eyes AND _draw_body_strip's neck
        cap — both draw a head-colored blob at the same screen position, so
        both must suppress it together or the neck cap alone still reads as
        a visible (eyeless) head floating through the flip."""
        if not self._wrap_transition['active'] or self._wrap_transition['phase'] != 'roll':
            return False
        roll_dist = abs(self._wrap_transition['roll_angle'] - math.pi / 2)
        return roll_dist < WRAP_HEAD_HIDE_WINDOW

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
        head_z = 0
        if idx == 0 and self._wrap_transition['active']:
            head_z -= self._wrap_transition['dive_amount'] * WRAP_DIVE_DEPTH
            # Hide the head at the midpoint of the world roll: that's the
            # instant the world is edge-on to the camera, where the head
            # would otherwise pop from the outgoing side straight to the
            # incoming side with no transition of its own.
            if idx == 0 and self._head_is_hidden():
                return
        if idx == 0 and self.eat_anim['timer'] > EAT_BULGE_DURATION - EAT_SQUASH_DURATION:
            eat_t = 1.0 - (self.eat_anim['timer'] - (EAT_BULGE_DURATION - EAT_SQUASH_DURATION)) / EAT_SQUASH_DURATION
            if 0 <= eat_t <= 1:
                dip = math.sin(eat_t * math.pi) * -EAT_HEAD_DIP
                head_z += dip
        sx, sy, depth = self.camera.project(cx, cy, head_z)
        if sx == -999:
            return

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
            # Body sprites removed in favor of ribbon rendering
            sprite = None

        if sprite:
            surf.blit(sprite, (int(sx - sz * squash // 2), int(sy - sz * stretch // 2)))

        if idx == 0:
            dir_len = math.hypot(tx, ty)
            if dir_len > 0.001:
                perp_x = -ty / dir_len
                perp_y = tx / dir_len
            else:
                perp_x, perp_y = 0, -1

            # Subtle green halo around head (alpha blend, not additive)
            glow_r = max(1, int(sz * 0.5))
            glow_surf = self._head_glow_sprites.get(sz)
            if glow_surf is None:
                d = glow_r * 2
                glow_surf = pygame.Surface((d, d), pygame.SRCALPHA)
                for gi in range(glow_r, 0, -1):
                    ga = max(0, int(12 * (1 - gi / glow_r)))
                    if ga > 0:
                        pygame.draw.circle(glow_surf, (*HEAD_HIGHLIGHT, ga), (glow_r, glow_r), gi)
                self._head_glow_sprites[sz] = glow_surf
            glow_surf.set_alpha(int(30 + 20 * math.sin(time_float * 4)))
            surf.blit(glow_surf, (int(sx - glow_r), int(sy - glow_r)))

            # Head bob animation
            head_bob = 0
            if self.state == GameState.PLAYING:
                head_bob = math.sin(time_float * 8 + self.move_timer * 4) * 1.5
            bob_sy = sy + int(head_bob)

            # Eye blink
            is_blinking = self.blink_timer <= 0.1 or (self.eat_anim['timer'] > 0 and self.eat_anim['timer'] < EAT_BULGE_DURATION - EAT_SQUASH_DURATION + 0.05)
            if not is_blinking:
                es = max(2, int(sz * 0.085))
                eye_spread = es * 1.8
                for side in [-1, 1]:
                    ex = int(sx + perp_x * eye_spread * side + tx * sz * 0.12)
                    ey = int(bob_sy + perp_y * eye_spread * side + ty * sz * 0.12)
                    es_draw = max(1, es)
                    # Dark outline for contrast
                    pygame.draw.circle(surf, (8, 20, 12), (ex, ey), es_draw + 1)
                    # Sclera
                    pygame.draw.circle(surf, EYE_WHITE, (ex, ey), es_draw)
                    # Iris - slightly toward direction
                    iris_r = max(1, int(es * 0.8))
                    iris_off_x = int(tx * es * 0.2 + perp_x * side * es * 0.25)
                    iris_off_y = int(ty * es * 0.2 + perp_y * side * es * 0.25)
                    pygame.draw.circle(surf, EYE_IRIS, (ex + iris_off_x, ey + iris_off_y), iris_r)
                    # Pupil - larger for readability
                    pupil_r = max(1, int(es * 0.55))
                    pygame.draw.circle(surf, EYE_PUPIL, (ex + iris_off_x, ey + iris_off_y), pupil_r)
                    # Reflection highlight
                    if es > 2:
                        ref_x = ex + int(perp_x * side * es * 0.5) - int(tx * sz * 0.02)
                        ref_y = ey + int(perp_y * side * es * 0.5) - int(ty * sz * 0.02)
                        pygame.draw.circle(surf, EYE_REFLECTION, (ref_x, ref_y), max(1, es // 3))

            # Small mouth - slight smile line
            mouth_w = max(1, int(sz * 0.06))
            mx1 = int(sx + tx * sz * 0.05 - perp_x * sz * 0.1)
            my1 = int(bob_sy + ty * sz * 0.05 - perp_y * sz * 0.1)
            mx2 = int(sx + tx * sz * 0.12 + perp_x * sz * 0.1)
            my2 = int(bob_sy + ty * sz * 0.12 + perp_y * sz * 0.1)
            pygame.draw.line(surf, (20, 50, 30), (mx1, my1), (mx2, my2), mouth_w)

            # Nose highlight
            nose_len = int(sz * 0.08)
            nose_x = int(sx + tx * sz * 0.25)
            nose_y = int(bob_sy + ty * sz * 0.25)
            pygame.draw.circle(surf, HEAD_HIGHLIGHT, (nose_x, nose_y), max(1, nose_len))

            # Tongue along tangent — offset start from head center
            tongue_len = int(HEX_SIZE * 0.16)
            tongue_w = max(1, int(HEX_SIZE * 0.020))
            tongue_flick = math.sin(time_float * 14) * 2
            tx_s = int(sx + tx * sz * 0.20)
            ty_s = int(bob_sy + ty * sz * 0.20)
            tx_t = int(tx_s + tx * (tongue_len + tongue_flick))
            ty_t = int(ty_s + ty * (tongue_len + tongue_flick))
            pygame.draw.line(surf, (180, 60, 60), (tx_s, ty_s), (tx_t, ty_t), tongue_w)
            if dir_len > 0.001:
                ppx = -ty / dir_len
                ppy = tx / dir_len
                fork_s = 2
                fork_l = int(HEX_SIZE * 0.03)
                pygame.draw.line(surf, (180, 60, 60),
                    (tx_t, ty_t),
                    (tx_t + int(ppx * fork_s) + int(tx * fork_l),
                     ty_t + int(ppy * fork_s) + int(ty * fork_l)),
                    max(1, tongue_w - 1))
                pygame.draw.line(surf, (180, 60, 60),
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
        if sx_p == -999:
            return
        display_sz = max(1, int(sz * spawn_scale))
        sprite = self._apple_sprites.get(display_sz)
        if sprite is None:
            sprite = pygame.transform.smoothscale(self.master_apple_sprite, (display_sz, display_sz))
            self._apple_sprites[display_sz] = sprite
        surf.blit(sprite, (int(sx_p - display_sz // 2), int(sy_p - display_sz // 2)))
        if self._ambient < 1.0:
            tint = pygame.Surface((display_sz, display_sz), pygame.SRCALPHA)
            tint_sun = mul_color(self._sun_color, (1.0 - self._ambient) * 0.15)
            tint.fill((*tint_sun, int((1.0 - self._ambient) * 40)))
            surf.blit(tint, (int(sx_p - display_sz // 2), int(sy_p - display_sz // 2)))

        sx_top, sy_top, _ = self.camera.project(cx, cy, bob + 2)
        if sx_top == -999:
            return
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
            interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - self.score * SPEED_DECAY_PER_POINT)
            lerp_t = min(1.0, self.move_timer / interval) if interval > 0 else 1.0
            if len(self.path_history) >= 2:
                trimmed = list(self.path_history)[:len(self.snake)]
                next_uq, next_ur = self._next_head_unwrapped()
                extended = [(next_uq, next_ur)] + trimmed
                raw = sample_spline_path(extended, len(self.snake) + 1)
                raw.reverse()
                R = GRID_RADIUS
                period = 2 * R + 1
                head_dq = self._visual_dq
                head_dr = self._visual_dr
                off_px, off_py = hex_to_pixel(head_dq * period, head_dr * period)
                result = []
                for i in range(len(self.snake)):
                    # Interpolate from raw[i+1] (head-ward) to raw[i] (tail-ward)
                    # At lerp_t=0: body occupies raw[1..N] (head→tail)
                    # At lerp_t=1: body occupies raw[0..N-1] (lookahead→near-tail)
                    px0, py0, tx0, ty0 = raw[i + 1]
                    px1, py1, _, _ = raw[i]
                    px = px0 + (px1 - px0) * lerp_t - off_px
                    py = py0 + (py1 - py0) * lerp_t - off_py
                    result.append((px, py, tx0, ty0))
                self._spline_positions = result
            if self._wrap_frame:
                self._wrap_frame = False
                self._request_full_redraw()
            if self._spline_positions and len(self._spline_positions) > 0:
                hx_cam, hy_cam = self._spline_positions[0][0], self._spline_positions[0][1]
            else:
                qh, rh = self.snake[0]
                hx_cam, hy_cam = hex_to_pixel(qh, rh)
            self.camera.follow_snake(hx_cam, hy_cam, self.direction, 1.0 / max(RENDER_FPS, 1), self._speed_ratio)

        # Wrap transition world flip: composed into the camera basis (an
        # orthonormal rotation of the projected point around the frame
        # center, equivalent to rotating Camera.up around the view forward
        # axis — see Camera.project()) rather than rotating a captured
        # full-screen surface every animated frame. Sign matches "world
        # rotates clockwise on screen as roll_angle increases", same visual
        # direction the old pygame.transform.rotate(surf, -degrees) produced.
        if self._wrap_transition['active']:
            self.camera.set_world_roll(-self._wrap_transition['roll_angle'])
        elif self.camera.world_roll != 0.0:
            self.camera.set_world_roll(0.0)
        surf = self.screen
        time_float = self.render_time

        _t_setup = time.perf_counter()
        self._horizon_y = self._compute_horizon_y()
        light_dir, ambient, sun_color = compute_sun_light(time_float)
        self._light_dir = light_dir
        self._ambient = ambient
        self._sun_color = sun_color
        self._day_cycle = math.sin(time_float * SUN_ANGLE_SPEED)
        self._sky_top, self._sky_mid, self._sky_hor = compute_sky_color(time_float)
        self._fog_tint = lerp_color(self._sky_mid, FOG_COLOR, 0.6)

        # World-space sun direction (matches compute_sun_light rotation)
        sun_angle = time_float * SUN_ANGLE_SPEED
        cos_a = math.cos(sun_angle)
        sin_a = math.sin(sun_angle)
        sun_dist = 10000
        sun_world_x = (LIGHT_DIR[0] * cos_a - LIGHT_DIR[1] * sin_a) * sun_dist
        sun_world_y = (LIGHT_DIR[0] * sin_a + LIGHT_DIR[1] * cos_a) * sun_dist
        sun_world_z = 500
        sun_px, sun_py, _ = self.camera.project(sun_world_x, sun_world_y, sun_world_z)
        sun_visible = (sun_px != -999 and -100 < sun_px < WIDTH + 100
                       and -100 < sun_py < HEIGHT + 100)

        # Camera heading (yaw) for sky parallax
        heading = math.atan2(self.camera.target[1] - self.camera.eye[1],
                             self.camera.target[0] - self.camera.eye[0])

        shake_x, shake_y = 0, 0
        if self.screen_shake > 0:
            intensity = self.screen_shake / 0.25 * 5
            shake_x, shake_y = screen_shake_offset(intensity)
        self._perf_timings['setup'] = (time.perf_counter() - _t_setup) * 1000

        _t_sky = time.perf_counter()
        self.resources._update_sky(time_float, self._day_cycle)
        surf.blit(self.bg_surf, (shake_x, shake_y))

        star_alpha = 0
        if self._day_cycle < SKY_STAR_FADE_START:
            star_alpha = int(255 * min(1.0, (SKY_STAR_FADE_START - self._day_cycle) / (SKY_STAR_FADE_START - SKY_STAR_FADE_END)))
        self.star_surf.set_alpha(star_alpha)
        star_off_x = int(heading * STAR_PARALLAX_FACTOR) % WIDTH
        surf.blit(self.star_surf, (shake_x - star_off_x, shake_y))
        surf.blit(self.star_surf, (shake_x - star_off_x + WIDTH, shake_y))

        if sun_visible:
            sd_w = self.sun_disc_surf.get_width()
            surf.blit(self.sun_disc_surf,
                      (int(sun_px - sd_w // 2), int(sun_py - sd_w // 2)),
                      special_flags=pygame.BLEND_ADD)
        self._perf_timings['sky'] = (time.perf_counter() - _t_sky) * 1000

        _t_water = time.perf_counter()
        water_color_base = lerp_color(self._sky_mid, WATER_COLOR_1, 0.4)
        water_highlight = lerp_color(sun_color, WATER_HIGHLIGHT, 0.5)

        self.water_surf.fill((0, 0, 0, 0))
        HORIZON_Y = max(0, int(self._horizon_y + WATER_HORIZON_MARGIN))
        WATER_SPANS = [(-1000, -500), (-500, 0), (0, 500), (500, 1000)]
        for wi in range(-12, 12):
            wy = wi * 28
            z_w = -TILE_HEIGHT - 20
            t = (wi + 25) / 50
            sx_center, sy_center, sd = self.camera.project(0, wy, z_w)
            if sx_center < -200 or sx_center > WIDTH + 200:
                continue
            if sy_center < -200 or sy_center > HEIGHT + 200:
                continue

            combined_wave = (math.sin(wy * 0.04 + time_float * WATER_WAVE_SPEED) * WATER_WAVE_AMP
                    + math.sin(wy * 0.07 + time_float * WATER_WAVE_SPEED * 1.5 + 1) * WATER_WAVE_AMP * 0.6)

            c = lerp_color(water_color_base, WATER_COLOR_2, t)
            fresnel = 0.3 + 0.7 * (1.0 - abs(t - 0.5) * 2) ** 2
            a = int(190 * fresnel)

            for x1, x2 in WATER_SPANS:
                sx1, sy1, _ = self.camera.project(x1, wy, z_w)
                sx2, sy2, _ = self.camera.project(x2, wy, z_w)
                if sx1 == -999 or sx2 == -999:
                    continue
                y1 = sy1 + combined_wave
                y2 = sy2 + combined_wave
                y1b = sy1 + 16 + combined_wave
                y2b = sy2 + 16 + combined_wave
                if y1 < HORIZON_Y and y2 < HORIZON_Y and y1b < HORIZON_Y and y2b < HORIZON_Y:
                    continue
                y1 = max(y1, HORIZON_Y)
                y2 = max(y2, HORIZON_Y)
                y1b = max(y1b, HORIZON_Y)
                y2b = max(y2b, HORIZON_Y)

                pts = [(sx1, y1), (sx2, y2), (sx2, y2b), (sx1, y1b)]
                pygame.draw.polygon(self.water_surf, (*c, a), pts)

                if wi % 4 == 0:
                    hl_a = int(50 * fresnel * (0.5 + 0.5 * math.sin(time_float * 1.2 + wi * 0.3)))
                    if hl_a > 2 and max(y1, y2) >= HORIZON_Y:
                        hl_y1 = max(sy1 + combined_wave + 1, HORIZON_Y)
                        hl_y2 = max(sy2 + combined_wave + 1, HORIZON_Y)
                        pygame.draw.line(self.water_surf, (*water_highlight, hl_a),
                            (sx1, hl_y1), (sx2, hl_y2), 1)

        if sun_visible:
            sun_ref_x = int(sun_px)
            sun_ref_y_start = max(HORIZON_Y, int(self._horizon_y))
            sun_ref_h = HEIGHT * 0.2
            self._water_reflect_surf.fill((0, 0, 0, 0))
            for ry in range(0, int(sun_ref_h), 2):
                alpha = int(40 * (1 - ry / sun_ref_h) * (0.5 + 0.5 * math.sin(time_float * 2 + ry * 0.1)))
                if alpha > 0:
                    # BLEND_ADD ignores per-pixel alpha, so premultiply the sun
                    # color by the intended intensity — otherwise every lit row
                    # adds full sun_color and saturates to white blocks.
                    a = alpha / 255.0
                    add_c = (int(sun_color[0] * a), int(sun_color[1] * a), int(sun_color[2] * a), 255)
                    self._water_reflect_surf.fill(add_c, rect=(0, ry, 100, 2))
            surf.blit(self._water_reflect_surf, (sun_ref_x - 50, sun_ref_y_start), special_flags=pygame.BLEND_ADD)

        if not hasattr(self, '_reflect_cache'):
            self._reflect_cache = pygame.Surface((WIDTH, HEIGHT // 3), pygame.SRCALPHA)
            self._reflect_cache.blit(self.bg_surf, (0, 0), (0, int(HEIGHT * 0.5), WIDTH, HEIGHT // 3))
            self._reflect_cache = pygame.transform.flip(self._reflect_cache, False, True)
            self._last_sky_snapshot = self._sky_mid
        sky_diff = sum(abs(self._sky_mid[i] - self._last_sky_snapshot[i]) for i in range(3))
        if sky_diff > 8:
            self._reflect_cache.fill((0, 0, 0, 0))
            self._reflect_cache.blit(self.bg_surf, (0, 0), (0, int(HEIGHT * 0.5), WIDTH, HEIGHT // 3))
            self._reflect_cache = pygame.transform.flip(self._reflect_cache, False, True)
            self._last_sky_snapshot = self._sky_mid
        reflect_alpha = int(30 + 10 * math.sin(time_float * 0.3))
        self._reflect_cache.set_alpha(reflect_alpha)
        surf.blit(self._reflect_cache, (0, HEIGHT - HEIGHT // 3))

        surf.blit(self.water_surf, (0, 0))
        self._perf_timings['water'] = (time.perf_counter() - _t_water) * 1000

        # Body positions and segments are needed before the terrain occluder
        # pass now (Phase 15: submerged segments must be drawn UNDER the
        # terrain, not just depth-sorted against it), so compute them here,
        # ahead of _build_tile_cache().
        if len(self.path_history) >= 2:
            interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - self.score * SPEED_DECAY_PER_POINT)
            lerp_t = min(1.0, self.move_timer / interval) if interval > 0 else 1.0
            # Render sampling (high res), from the already-computed low-res
            # self._spline_positions (set earlier in render())
            self._render_spline_positions = self._subsample_spline_positions(lerp_t)
        else:
            self._render_spline_positions = None

        body_segments, submerged_start = self._compute_body_segments(time_float)
        self._body_segments_raw = body_segments
        emerged_segments = body_segments[:submerged_start + 1]
        submerged_segments = body_segments[submerged_start:]

        _t_ground = time.perf_counter()
        self._build_ground()
        surf.blit(self.ground_cache, (shake_x, shake_y))
        self._build_tile_cache()
        self._perf_timings['tiles'] = (time.perf_counter() - _t_ground) * 1000

        _t_composite = time.perf_counter()
        self.draw_cache.fill((0, 0, 0, 0))

        # Under-seam pass: submerged tail segments drawn on a still-empty
        # (transparent) cache, so nothing occludes them yet.
        if len(submerged_segments) >= 2:
            self._draw_body_strip(self.draw_cache, submerged_segments,
                                   draw_head_cap=False, draw_tail_cap=True)

        # Seam / tile occluder pass: the tile cache is built with each tile's
        # nearest periodic copy already re-projected through the real
        # (perspective) camera — see _build_tile_cache(). A flat screen-space
        # blit shift is not valid for a perspective camera (the screen-space
        # delta for a one-period world shift is not constant across the
        # frame), so no further shift is needed here. Blitting it now paints
        # over whatever of the submerged pass falls under opaque terrain —
        # that's the actual occlusion, not a color fade standing in for it.
        self.draw_cache.blit(self._tile_cache, (0, 0))

        # Shadow only covers emerged samples (see _draw_continuous_shadow's
        # seam_t check) so no shadow patch is left orphaned above hidden body.
        self._draw_continuous_shadow(self.draw_cache)
        self._perf_timings['shadow'] = (time.perf_counter() - _t_composite) * 1000

        # Above-world pass: apple, emerged body, and snake heads/eyes on top
        # of the now-opaque terrain, depth-sorted against each other as before.
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

        if emerged_segments:
            med_depth = sorted(s[0] for s in emerged_segments)[len(emerged_segments) // 2]
            draw_items.append((med_depth, 'body_strip', emerged_segments))

        draw_list = self._build_depth_buckets(draw_items)
        head_hidden = self._head_is_hidden()

        for item in draw_list:
            if item[1] == 'apple':
                self.draw_apple(self.draw_cache, time_float)
            elif item[1] == 'body_strip':
                _, _, seg = item
                # Neck cap draws a head-colored blob at the same screen spot
                # as the head sprite — must be suppressed together with it,
                # or a bare (eyeless) cap still reads as a visible head.
                self._draw_body_strip(self.draw_cache, seg,
                                       draw_head_cap=not head_hidden, draw_tail_cap=False)
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
                

            if god_rays_enabled and sun_visible and self._day_cycle > 0.2:
                self._rays_surf_cache.fill((0, 0, 0, 0))
                gsx, gsy = int(sun_px), int(sun_py)
                for ri in range(6):
                    angle = math.radians(ri * 60 + 30 + math.sin(time_float * 0.15 + ri) * 8)
                    ray_len = 180 + int(math.sin(time_float * 0.1 + ri * 1.5) * 60)
                    ex = gsx + int(math.cos(angle) * ray_len)
                    ey = gsy + int(math.sin(angle) * ray_len)
                    ray_a = 5
                    if ray_a > 0:
                        # BLEND_ADD ignores alpha; premultiply so rays stay faint.
                        a = ray_a / 255.0
                        ray_c = (int(sun_color[0] * a), int(sun_color[1] * a), int(sun_color[2] * a))
                        pygame.draw.line(self._rays_surf_cache, ray_c, (gsx, gsy), (ex, ey), 2)
                surf.blit(self._rays_surf_cache, (0, 0), special_flags=pygame.BLEND_ADD)
        self._perf_timings['post'] = (time.perf_counter() - _t0) * 1000

        _t0 = time.perf_counter()
        if self.apple and self.state != GameState.GAME_OVER:
            px, py = hex_to_pixel(*self.apple)
            sx, sy, _ = self.camera.project(px, py, 0.5)
            if sx == -999:
                pass
            else:
                glow_r = int(HEX_SIZE * 1.0 + math.sin(time_float * 2.5) * 6)
                glow_surf = self._apple_glow_sprites.get(glow_r)
                if glow_surf is None:
                    d = glow_r * 2
                    glow_surf = pygame.Surface((d, d), pygame.SRCALPHA)
                    glow_tint = lerp_color(APPLE_BASE, self._sun_color, 0.25)
                    for i in range(glow_r, 0, -1):
                        a = int(35 * (1 - i / glow_r))
                        if a > 0:
                            pygame.draw.circle(glow_surf, (*glow_tint, a), (glow_r, glow_r), i)
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
            self._fade_surf.fill((0, 0, 0, int(self.fade_alpha)))
            surf.blit(self._fade_surf, (0, 0))

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
                      self._wrap_transition['active'] or
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

        _t_display = time.perf_counter()
        merged = self._merge_rects(all_rects)
        if len(merged) == 1 and merged[0] == pygame.Rect(0, 0, WIDTH, HEIGHT):
            pygame.display.flip()
        else:
            pygame.display.update(merged)
        self._perf_timings['display'] = (time.perf_counter() - _t_display) * 1000

    def _compute_frame_stats(self):
        if len(self._frame_times) < 2:
            self._frame_stats = {'avg': 0.0, 'min': 0.0, 'max': 0.0, 'p50': 0.0, 'p95': 0.0, 'p99': 0.0}
            return
        times = sorted(self._frame_times)
        n = len(times)
        self._frame_stats['avg'] = sum(times) / n
        self._frame_stats['min'] = times[0]
        self._frame_stats['max'] = times[-1]
        self._frame_stats['p50'] = times[int(n * 0.50)]
        self._frame_stats['p95'] = times[int(n * 0.95)]
        self._frame_stats['p99'] = times[int(n * 0.99)]

    def run(self):
        sim_accumulator = 0.0
        particle_accumulator = 0.0
        self.render_time = 0.0
        self._wall_time = time.perf_counter()
        self._frame_count = 0
        self._smooth_fps = 0.0
        self._catch_up_overruns = 0

        while self.state != GameState.QUIT:
            _frame_start = time.perf_counter()
            # Exactly one pacing authority: if display vsync engaged, the
            # swap already paces the loop, so just measure elapsed time
            # (Clock.tick() with no argument doesn't sleep/cap). Otherwise
            # fall back to the software cap.
            if self._vsync_active:
                raw_dt = self.clock.tick() / 1000.0
            else:
                raw_dt = self.clock.tick(RENDER_FPS) / 1000.0
            raw_dt = min(raw_dt, MAX_FRAME_DT)

            _t_events_start = time.perf_counter()
            self.handle_events()
            self._perf_timings['events'] = (time.perf_counter() - _t_events_start) * 1000

            _t_sim_start = time.perf_counter()
            if self.state == GameState.PLAYING:
                sim_accumulator += raw_dt
                if sim_accumulator > FIXED_DT * MAX_SIM_STEPS:
                    self._catch_up_overruns += 1
                sim_accumulator = min(sim_accumulator, FIXED_DT * MAX_SIM_STEPS)
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
                particle_accumulator = min(particle_accumulator, FIXED_DT * MAX_SIM_STEPS)
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

            self._perf_timings['simulation'] = (time.perf_counter() - _t_sim_start) * 1000
            self.render_time += raw_dt
            self.render()

            self._perf_timings['frame'] = (time.perf_counter() - _frame_start) * 1000
            self._frame_times.append(self._perf_timings['frame'])
            self._frame_count += 1
            self._wall_time = time.perf_counter()
            self._compute_frame_stats()

            frame_ms = self._perf_timings['frame']
            if self._smooth_fps <= 0:
                self._smooth_fps = 1000.0 / max(frame_ms, 0.001)
            else:
                instant_fps = 1000.0 / max(frame_ms, 0.001)
                self._smooth_fps += (instant_fps - self._smooth_fps) * FPS_SMOOTH_ALPHA

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
