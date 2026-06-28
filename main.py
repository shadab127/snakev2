import pygame
import math
import random
import sys
import time
import struct
from config import *
from game_state import GameState
from utils import (perlin_noise, catmull_rom, hex_side_normal, hex_to_pixel,
                   hex_corners, all_hexes, lerp_color,
                   mul_color, add_color, screen_shake_offset, compute_tile_ao,
                   dot3, tile_noise, generate_soft_shadow, _perlin_cache,
                   wrap_coords)
from particle import Particle, ParticlePool
from resources import ResourceManager
from gl_renderer import GLRenderer
from camera import Camera
from ui import draw_ui, draw_pause_overlay, draw_game_over, draw_start_screen, draw_minimap


class SnakeGame:
    def __init__(self):
        pygame.init()
        self.clock = pygame.time.Clock()
        self.start_time = time.time()
        flags = pygame.SCALED | pygame.RESIZABLE
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.display.set_caption('SnakeV2 - Enhanced 3D')

        self.resources = ResourceManager()

        self.frame_count = 0
        self.move_timer = 0
        self.move_lerp = 0.0
        self.prev_snake_positions = {}
        self.smooth_positions = {}
        self.particles = ParticlePool(500)
        self.eat_flash = 0
        self.screen_shake = 0
        self.ambient_time = 0
        self.bloom_layer = pygame.Surface((WIDTH // 2, HEIGHT // 2), pygame.SRCALPHA)

        self._dirty_rects = []
        self._prev_dirty_rects = []
        self._full_redraw_counter = 0
        self._full_redraw_requested = True

        self.water_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._tile_cache = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._tile_cache_valid = False
        self.gl_renderer = GLRenderer()
        self.camera = Camera()
        self.draw_cache = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        self.cloud_surf_cache = pygame.Surface((WIDTH, HEIGHT // 2), pygame.SRCALPHA)

        for q, r in all_hexes():
            tile_noise(q, r)
        _perlin_cache.clear()

        self.reset()
        self.state = GameState.START

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
        for idx in range(len(self.snake)):
            q, r = self.snake[idx]
            if self.prev_snake_positions and idx < len(self.prev_snake_positions):
                prev_q, prev_r = self.prev_snake_positions[idx]
                lerp_q = prev_q + (q - prev_q) * self.move_lerp
                lerp_r = prev_r + (r - prev_r) * self.move_lerp
            else:
                lerp_q, lerp_r = q, r
            cx, cy = hex_to_pixel(lerp_q, lerp_r)
            sx, sy, _ = self.camera.project(cx, cy, 2)
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
        self.ground_cache.fill((0, 0, 0, 0))
        for q, r in all_hexes():
            cx, cy = hex_to_pixel(q, r)
            corners = hex_corners(cx, cy)
            bot_pts = []
            for cx_c, cy_c in corners:
                sx_b, sy_b, _ = self.camera.project(cx_c, cy_c, -TILE_HEIGHT - 4)
                bot_pts.append((sx_b, sy_b))
            dist = (q * q + r * r + q * r) ** 0.5 / GRID_RADIUS
            ground_c = lerp_color(GROUND_LOW, GROUND_DEEP, dist)
            pygame.draw.polygon(self.ground_cache, ground_c, bot_pts)

    def _build_tile_cache(self):
        self._build_ground()
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
            time_float = self.frame_count / 60.0
            for q, r in all_hexes():
                cx, cy = hex_to_pixel(q, r)
                sx, sy, depth = self.camera.project(cx, cy, 0)
                if sx < -TILE_CLIP_MARGIN or sx > WIDTH + TILE_CLIP_MARGIN:
                    continue
                if sy < -TILE_CLIP_MARGIN or sy > HEIGHT + TILE_CLIP_MARGIN:
                    continue
                self._draw_tile_decorations(self._tile_cache, q, r, time_float)
            self._tile_cache_valid = True
            return

        self._tile_cache.fill((0, 0, 0, 0))
        time_float = self.frame_count / 60.0
        tile_items = []
        for q, r in all_hexes():
            cx, cy = hex_to_pixel(q, r)
            sx, sy, depth = self.camera.project(cx, cy, 0)
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
        cx, cy = hex_to_pixel(q, r)
        corners = hex_corners(cx, cy)
        top_pts = []
        for corner_x, corner_y in corners:
            sx_t, sy_t, _ = self.camera.project(corner_x, corner_y, 0)
            top_pts.append((sx_t, sy_t))
        cx_proj = sum(p[0] for p in top_pts) / 6
        cy_proj = sum(p[1] for p in top_pts) / 6

        noise = tile_noise(q, r)
        noise_val = noise['detail'] * 0.15
        dist_from_center = (q * q + r * r + q * r) ** 0.5 / GRID_RADIUS
        dist_factor = max(0, 1 - dist_from_center * 0.3)
        sun_factor = 0.85 + 0.15 * math.sin(time_float * SUN_ANGLE_SPEED + q * 0.5 + r * 0.3)
        ao = self._tile_ao_cache.get((q, r), 0.9)

        edge_color = TILE_EDGE
        if self.state == GameState.GAME_OVER:
            edge_color = (30, 15, 18)
        elif self.eat_flash > 0:
            flash = min(1.0, self.eat_flash / 12)
            edge_color = lerp_color(TILE_EDGE, TILE_GLOW, flash)

        mat_noise = noise['base']
        if mat_noise > 0.4:
            base_top_color = list(TILE_DIRT)
        elif mat_noise < -0.3:
            base_top_color = [60, 110, 80]
        else:
            base_top_color = list(TILE_TOP)

        moss_noise = noise['moss']
        if moss_noise > 0.15:
            moss_t = min(1.0, (moss_noise - 0.15) * 3)
            base_top_color = list(lerp_color(tuple(base_top_color), TILE_MOSS, moss_t * 0.35))
        dirt_noise = noise['dirt']
        if dirt_noise > 0.2:
            dirt_t = min(1.0, (dirt_noise - 0.2) * 2.5)
            base_top_color[0] = min(255, int(base_top_color[0] + (TILE_DIRT[0] - base_top_color[0]) * dirt_t * 0.25))
            base_top_color[1] = min(255, int(base_top_color[1] + (TILE_DIRT[1] - base_top_color[1]) * dirt_t * 0.25))
            base_top_color[2] = min(255, int(base_top_color[2] + (TILE_DIRT[2] - base_top_color[2]) * dirt_t * 0.25))
        noise_offset = int(noise_val * 20)
        for i in range(3):
            base_top_color[i] = max(0, min(255, base_top_color[i] + noise_offset))
        if (q, r) in set(self.snake):
            worn = 0.15
            base_top_color = list(lerp_color(tuple(base_top_color), TILE_TOP_LIGHT, worn))

        final_tri_color = tuple(base_top_color)
        dist = math.hypot(cx - self.camera.x, cy - self.camera.y)
        fog_t = max(0, min(1, (dist - FOG_NEAR) / (FOG_FAR - FOG_NEAR)))
        if fog_t > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), FOG_COLOR, fog_t * 0.35)
        tex_variation = 1.0 + 0.06 * noise['tex']
        final_tri_color = mul_color(tuple(final_tri_color), tex_variation)

        pygame.draw.polygon(surf, edge_color, top_pts, max(1, int(1 + sun_factor * 0.5)))

        bevel_n = (0.0, 0.0, 1.0)
        bevel_light = AMBIENT_LIGHT + (1.0 - AMBIENT_LIGHT) * max(0.0, dot3(bevel_n, LIGHT_DIR))
        bevel_brightness = bevel_light * sun_factor * ao
        inner_hl = mul_color(TILE_EDGE_HIGHLIGHT, 0.2 * bevel_brightness)
        for i in range(6):
            j = (i + 1) % 6
            pygame.draw.line(surf, inner_hl, top_pts[i], top_pts[j], 2)

        crack_noise = noise['crack']
        crack_intensity = abs(crack_noise) ** 3 * 0.3
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
                rim = max(0.0, edge_nx * LIGHT_DIR[0] + edge_ny * LIGHT_DIR[1])
                if rim > 0.3:
                    pygame.draw.line(surf, rim_light, top_pts[i], top_pts[j], 1)

        grass_seed = noise['grass']
        if grass_seed > 0.1 and self.state != GameState.GAME_OVER:
            blade_count = int((grass_seed - 0.1) * 7)
            for bi in range(blade_count):
                a = grass_seed * 6.28 + bi * 1.7 + q * 0.3
                d = 0.25 + (hash((q, r, bi)) % 100) / 250.0
                bx = cx + math.cos(a) * d * HEX_SIZE
                by = cy + math.sin(a) * d * HEX_SIZE
                blade_h = 3 + (hash((q, r, bi + 100)) % 30) / 15.0
                blade_w = max(1, int(1 + (hash((q, r, bi + 200)) % 3)))
                sway = math.sin(time_float * 1.8 + bx * 0.4 + by * 0.3) * 2
                sx_b, sy_b, _ = self.camera.project(bx, by, 0)
                sx_t, sy_t, _ = self.camera.project(bx + sway, by, blade_h)
                gc = lerp_color((35, 115, 50), (55, 160, 70), 0.3 + (hash((q, r, bi + 300)) % 100) / 200.0)
                pygame.draw.line(surf, gc, (int(sx_b), int(sy_b)), (int(sx_t), int(sy_t)), blade_w)
                if hash((q, r, bi + 400)) % 5 == 0:
                    fc = [(255, 200, 80), (240, 130, 150), (200, 140, 255)][hash((q, r, bi + 500)) % 3]
                    pygame.draw.circle(surf, fc, (int(sx_t), int(sy_t)), max(1, blade_w + 1))

    def reset(self):
        self.snake = [(0, 0), (-1, 0), (-2, 0)]
        self.direction = 0
        self.next_direction = 0
        self.apple = self._find_empty()
        self.score = 0
        self.high_score = getattr(self, 'high_score', 0)
        self.state = GameState.PLAYING
        self.particles.clear()
        self.eat_flash = 0
        self.screen_shake = 0
        self.move_timer = 0
        self.move_lerp = 0
        self.smooth_positions = {}
        self.prev_snake_positions = {}
        self.camera.snap_to(*self.snake[0], self.direction)

    def _find_empty(self):
        empty = [(q, r) for q, r in all_hexes() if (q, r) not in self.snake]
        return random.choice(empty) if empty else None

    def head(self):
        return self.snake[0]

    def turn_left(self):
        self.next_direction = (self.direction - 1) % 6

    def turn_right(self):
        self.next_direction = (self.direction + 1) % 6

    def next_head_pos(self):
        q, r = self.snake[0]
        dq, dr = DIR_VECTORS[self.direction]
        return (q + dq, r + dr)

    def move_snake(self):
        self.direction = self.next_direction
        new_head = wrap_coords(*self.next_head_pos())
        if new_head in self.snake[1:]:
            return False
        self.prev_snake_positions = list(self.snake)
        ate = new_head == self.apple
        if ate:
            old_apple = self.apple
        self.snake.insert(0, new_head)
        if ate:
            self.score += 10
            self.apple = self._find_empty()
            self._spawn_eat_particles(old_apple)
            self.eat_flash = 12
            self.move_timer = 0
        else:
            self.snake.pop()
        self._tile_cache_valid = False
        self._request_full_redraw()
        return True

    def _spawn_eat_particles(self, pos=None):
        if pos is None:
            pos = self.apple or self.snake[0]
        cx, cy = hex_to_pixel(*pos)
        for _ in range(20):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(2, 6)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed * 0.6
            vz = random.uniform(2, 5)
            color = random.choice(PARTICLE_COLORS)
            size = random.uniform(2, 4)
            lifetime = random.uniform(0.6, 1.8)
            ox = random.uniform(-4, 4)
            oy = random.uniform(-4, 4)
            self.particles.emit(cx + ox, cy + oy, 3, vx, vy, vz, color, size, lifetime, 'glow')
        for _ in range(10):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(4, 8)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed * 0.5
            vz = random.uniform(3, 6)
            self.particles.emit(cx, cy, 3, vx, vy, vz, (255, 255, 200), random.uniform(1, 2), random.uniform(0.3, 0.8), 'spark')

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.quit()
                elif self.state == GameState.PLAYING:
                    if event.key == pygame.K_SPACE:
                        self.state = GameState.PAUSED
                    elif event.key in (pygame.K_a, pygame.K_LEFT):
                        self.turn_left()
                    elif event.key in (pygame.K_d, pygame.K_RIGHT):
                        self.turn_right()
                elif self.state == GameState.PAUSED:
                    if event.key == pygame.K_SPACE:
                        self.state = GameState.PLAYING
                elif self.state == GameState.GAME_OVER:
                    if event.key == pygame.K_r or event.key == pygame.K_RETURN:
                        self.reset()

    def update(self, dt):
        self.frame_count += 1
        self.ambient_time += dt
        self.update_ambient_particles()

        if self.state == GameState.PLAYING:
            self.move_timer += dt
            interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - self.score * SPEED_DECAY_PER_POINT)
            self.move_lerp = min(1.0, self.move_timer / interval)

            while self.move_timer >= interval:
                self.move_timer -= interval
                self.move_lerp = 0
                if not self.move_snake():
                    self.state = GameState.GAME_OVER
                    self.screen_shake = 15
                    self._spawn_eat_particles(self.snake[0])
                    self._tile_cache_valid = False
                    self._request_full_redraw()
                    break

        self.camera.follow_snake(*self.snake[0], self.direction)

        self.particles.update_all(dt)
        self.particles.clean()

        if self.eat_flash > 0:
            self.eat_flash -= dt * 60
            self._tile_cache_valid = False
            self._request_full_redraw()

        if self.screen_shake > 0:
            self.screen_shake -= dt * 60

        if self.score > self.high_score:
            self.high_score = self.score

    def draw_tile(self, surf, q, r, time_float):
        cx, cy = hex_to_pixel(q, r)
        corners = hex_corners(cx, cy)

        top_pts = []
        bot_pts = []
        for corner_x, corner_y in corners:
            sx_t, sy_t, _ = self.camera.project(corner_x, corner_y, 0)
            sx_b, sy_b, _ = self.camera.project(corner_x, corner_y, -TILE_HEIGHT)
            top_pts.append((sx_t, sy_t))
            bot_pts.append((sx_b, sy_b))

        cx_proj = sum(p[0] for p in top_pts) / 6
        cy_proj = sum(p[1] for p in top_pts) / 6

        noise = tile_noise(q, r)
        noise_val = noise['detail'] * 0.15
        dist_from_center = (q * q + r * r + q * r) ** 0.5 / GRID_RADIUS
        dist_factor = max(0, 1 - dist_from_center * 0.3)
        sun_factor = 0.85 + 0.15 * math.sin(time_float * SUN_ANGLE_SPEED + q * 0.5 + r * 0.3)

        ao = self._tile_ao_cache.get((q, r), 0.9)

        edge_color = TILE_EDGE
        if self.state == GameState.GAME_OVER:
            edge_color = (30, 15, 18)
        elif self.eat_flash > 0:
            flash = min(1.0, self.eat_flash / 12)
            edge_color = lerp_color(TILE_EDGE, TILE_GLOW, flash)

        mat_noise = noise['base']
        if mat_noise > 0.4:
            base_top_color = list(TILE_DIRT)
            base_side_color = list(TILE_SIDE_DARK)
        elif mat_noise < -0.3:
            base_top_color = list((60, 110, 80))
            base_side_color = list(TILE_SIDE)
        else:
            base_top_color = list(TILE_TOP)
            base_side_color = list(TILE_SIDE)

        moss_noise = noise['moss']
        if moss_noise > 0.15:
            moss_t = min(1.0, (moss_noise - 0.15) * 3)
            base_top_color = list(lerp_color(tuple(base_top_color), TILE_MOSS, moss_t * 0.35))

        dirt_noise = noise['dirt']
        if dirt_noise > 0.2:
            dirt_t = min(1.0, (dirt_noise - 0.2) * 2.5)
            base_top_color[0] = min(255, int(base_top_color[0] + (TILE_DIRT[0] - base_top_color[0]) * dirt_t * 0.25))
            base_top_color[1] = min(255, int(base_top_color[1] + (TILE_DIRT[1] - base_top_color[1]) * dirt_t * 0.25))
            base_top_color[2] = min(255, int(base_top_color[2] + (TILE_DIRT[2] - base_top_color[2]) * dirt_t * 0.25))

        noise_offset = int(noise_val * 20)
        for i in range(3):
            base_top_color[i] = max(0, min(255, base_top_color[i] + noise_offset))

        if (q, r) in set(self.snake):
            worn = 0.15
            base_top_color = list(lerp_color(tuple(base_top_color), TILE_TOP_LIGHT, worn))

        if self.state == GameState.GAME_OVER:
            base_top_color = [10, 25, 20]
            base_side_color = [6, 14, 12]
        elif self.eat_flash > 0:
            flash = min(1.0, self.eat_flash / 12)
            base_top_color = list(lerp_color(tuple(base_top_color), mul_color(TILE_GLOW, 0.3), flash * 0.5))

        face_normal = (0.0, 0.0, 1.0)
        diff = max(0.0, dot3(face_normal, LIGHT_DIR))
        light = (AMBIENT_LIGHT + (1.0 - AMBIENT_LIGHT) * diff) * sun_factor * dist_factor * ao
        final_tri_color = mul_color(tuple(base_top_color), light)
        dist = math.hypot(cx - self.camera.x, cy - self.camera.y)
        fog_t = max(0, min(1, (dist - FOG_NEAR) / (FOG_FAR - FOG_NEAR)))
        if fog_t > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), FOG_COLOR, fog_t * 0.35)
        tex_variation = 1.0 + 0.06 * noise['tex']
        final_tri_color = mul_color(tuple(final_tri_color), tex_variation)

        pygame.draw.polygon(surf, edge_color, top_pts, max(1, int(1 + sun_factor * 0.5)))

        for i in range(6):
            j = (i + 1) % 6
            quad = [top_pts[i], top_pts[j], bot_pts[j], bot_pts[i]]
            nx_s, ny_s, nz_s = hex_side_normal(i)
            diff_side = max(0.0, nx_s * LIGHT_DIR[0] + ny_s * LIGHT_DIR[1] + nz_s * LIGHT_DIR[2])
            side_light = (AMBIENT_LIGHT + (1.0 - AMBIENT_LIGHT) * diff_side) * sun_factor * dist_factor * ao

            side_ao = 1.0 - 0.12 * (1.0 - abs(diff_side))
            side_light *= side_ao

            side_noise_val = noise['detail'] * 0.08
            side_light = max(0.1, side_light + side_noise_val)

            sc_top = mul_color(tuple(base_side_color), side_light * 1.1)
            pygame.draw.polygon(surf, sc_top, quad)

            edge_highlight = mul_color(TILE_EDGE_HIGHLIGHT, 0.3 * max(0.3, side_light))
            pygame.draw.line(surf, edge_highlight, quad[0], quad[1], 1)

        bevel_n = (0.0, 0.0, 1.0)
        bevel_light = AMBIENT_LIGHT + (1.0 - AMBIENT_LIGHT) * max(0.0, dot3(bevel_n, LIGHT_DIR))
        bevel_brightness = bevel_light * sun_factor * ao
        inner_hl = mul_color(TILE_EDGE_HIGHLIGHT, 0.2 * bevel_brightness)
        for i in range(6):
            j = (i + 1) % 6
            pygame.draw.line(surf, inner_hl, top_pts[i], top_pts[j], 2)

        crack_noise = noise['crack']
        crack_intensity = abs(crack_noise) ** 3 * 0.3
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
                rim = max(0.0, edge_nx * LIGHT_DIR[0] + edge_ny * LIGHT_DIR[1])
                if rim > 0.3:
                    pygame.draw.line(surf, rim_light, top_pts[i], top_pts[j], 1)

        grass_seed = noise['grass']
        if grass_seed > 0.1 and self.state != GameState.GAME_OVER:
            blade_count = int((grass_seed - 0.1) * 7)
            for bi in range(blade_count):
                a = grass_seed * 6.28 + bi * 1.7 + q * 0.3
                d = 0.25 + (hash((q, r, bi)) % 100) / 250.0
                bx = cx + math.cos(a) * d * HEX_SIZE
                by = cy + math.sin(a) * d * HEX_SIZE
                blade_h = 3 + (hash((q, r, bi + 100)) % 30) / 15.0
                blade_w = max(1, int(1 + (hash((q, r, bi + 200)) % 3)))
                sway = math.sin(time_float * 1.8 + bx * 0.4 + by * 0.3) * 2
                sx_b, sy_b, _ = self.camera.project(bx, by, 0)
                sx_t, sy_t, _ = self.camera.project(bx + sway, by, blade_h)
                gc = lerp_color((35, 115, 50), (55, 160, 70), 0.3 + (hash((q, r, bi + 300)) % 100) / 200.0)
                pygame.draw.line(surf, gc, (int(sx_b), int(sy_b)), (int(sx_t), int(sy_t)), blade_w)
                if hash((q, r, bi + 400)) % 5 == 0:
                    fc = [(255, 200, 80), (240, 130, 150), (200, 140, 255)][hash((q, r, bi + 500)) % 3]
                    pygame.draw.circle(surf, fc, (int(sx_t), int(sy_t)), max(1, blade_w + 1))

    def draw_shadow(self, surf, cx, cy, z, r, alpha=60):
        sx, sy, _ = self.camera.project(cx, cy, z)
        shadow_size = max(2, int(r * 2))
        scaled = pygame.transform.smoothscale(self.soft_shadow_sprite, (shadow_size, shadow_size))
        scaled.set_alpha(alpha)
        surf.blit(scaled, (int(sx - shadow_size // 2), int(sy - shadow_size // 2)))

    def draw_snake_segment(self, surf, idx, q, r, time_float):
        if self.prev_snake_positions and idx < len(self.prev_snake_positions):
            prev_q, prev_r = self.prev_snake_positions[idx]
            lerp_q = prev_q + (q - prev_q) * self.move_lerp
            lerp_r = prev_r + (r - prev_r) * self.move_lerp
        else:
            lerp_q, lerp_r = q, r

        if len(self.snake) >= 4:
            snake_pos = []
            for si in range(len(self.snake)):
                sq, sr = self.snake[si]
                if self.prev_snake_positions and si < len(self.prev_snake_positions):
                    psq, psr = self.prev_snake_positions[si]
                    sq = psq + (sq - psq) * self.move_lerp
                    sr = psr + (sr - psr) * self.move_lerp
                snake_pos.append((sq, sr))

            p0 = snake_pos[max(0, idx - 1)]
            p1 = snake_pos[min(len(snake_pos) - 1, idx)]
            p2 = snake_pos[min(len(snake_pos) - 1, idx + 1)]
            p3 = snake_pos[min(len(snake_pos) - 1, idx + 2)]
            interp_q = catmull_rom(p0[0], p1[0], p2[0], p3[0], 0.5)
            interp_r = catmull_rom(p0[1], p1[1], p2[1], p3[1], 0.5)
            lerp_q = lerp_q * 0.5 + interp_q * 0.5
            lerp_r = lerp_r * 0.5 + interp_r * 0.5

        cx, cy = hex_to_pixel(lerp_q, lerp_r)
        t = idx / max(1, len(self.snake) - 1)
        color_idx = min(len(SNAKE_COLORS) - 1, int(t * len(SNAKE_COLORS)))

        thickness_curve = 1.0 - t * 0.25
        thickness_curve *= (1.0 + 0.15 * math.sin(t * math.pi))
        body_pulse = 1.0 + 0.03 * math.sin(time_float * 2 + idx * 0.5)
        sz = int(HEX_SIZE * 0.40 * thickness_curve * body_pulse * 2)

        sx, sy, depth = self.camera.project(cx, cy, 2)

        self.draw_shadow(surf, cx, cy, 0.3, int(sz * 0.5), 50)

        if idx == 0:
            sprite = self._head_sprites.get(sz)
            if sprite is None:
                sprite = pygame.transform.smoothscale(self.master_head_sprite, (sz, sz))
                self._head_sprites[sz] = sprite
        else:
            sprite = self._body_sprites[color_idx].get(sz)
            if sprite is None:
                sprite = pygame.transform.smoothscale(self.master_body_sprites[color_idx], (sz, sz))
                self._body_sprites[color_idx][sz] = sprite
        surf.blit(sprite, (int(sx - sz // 2), int(sy - sz // 2)))

        if idx < len(self.snake) - 1:
            nq, nr = self.snake[idx + 1]
            if self.prev_snake_positions and idx + 1 < len(self.prev_snake_positions):
                npq, npr = self.prev_snake_positions[idx + 1]
                nq = npq + (nq - npq) * self.move_lerp
                nr = npr + (nr - npr) * self.move_lerp
            ncx, ncy = hex_to_pixel(nq, nr)
            for frac in [0.25, 0.5, 0.75]:
                px = cx + (ncx - cx) * frac
                py = cy + (ncy - cy) * frac
                z = 1 + TILE_HEIGHT * 0.35
                sx_j, sy_j, _ = self.camera.project(px, py, z)
                r_conn = max(1.5, sz * 0.35 * (1 - idx * 0.008))
                base_color = HEAD_COLOR if idx == 0 else SNAKE_COLORS[color_idx]
                lx, ly, lz = LIGHT_DIR
                vx, vy, vz = 0.0, 0.0, 1.0
                diff = max(0.0, vx * lx + vy * ly + vz * lz)
                light = 0.25 + 0.75 * diff
                c = mul_color(base_color, light * 0.8)
                pygame.draw.circle(surf, c, (int(sx_j), int(sy_j)), int(r_conn))
                spec = mul_color((255, 255, 255), 0.3 * max(0.0, diff) ** 8)
                pygame.draw.circle(surf, spec, (int(sx_j - 1), int(sy_j - 1)), max(1, int(r_conn * 0.4)))

        if idx == 0:
            dx, dy = DIR_VECTORS[self.direction]
            sx_fwd, sy_fwd, _ = self.camera.project(cx + dx * 6, cy + dy * 6, 2 + TILE_HEIGHT * 0.55)
            es = max(2, int(HEX_SIZE * 0.12))
            dir_x = sx_fwd - sx
            dir_y = sy_fwd - sy
            dir_len = math.hypot(dir_x, dir_y)
            if dir_len > 0:
                perp_x = -dir_y / dir_len
                perp_y = dir_x / dir_len
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

            eye_spread = es * 1.8
            for side in [-1, 1]:
                ex = int(sx + perp_x * eye_spread * side + dir_x * 0.15)
                ey = int(sy + perp_y * eye_spread * side + dir_y * 0.15)
                es_draw = max(1, es)
                pygame.draw.circle(surf, EYE_WHITE, (ex, ey), es_draw)

                iris_r = max(1, es - 1)
                iris_off_x = int(perp_x * side * es * 0.35)
                iris_off_y = int(perp_y * side * es * 0.35)
                pygame.draw.circle(surf, EYE_IRIS, (ex + iris_off_x, ey + iris_off_y), iris_r)

                pupil_r = max(1, es - 2)
                pygame.draw.circle(surf, EYE_PUPIL, (ex + int(perp_x * side * es * 0.35), ey + int(perp_y * side * es * 0.35)), pupil_r)

                if es > 2:
                    ref_x = ex + int(perp_x * side * es * 0.5) - int(dir_x * 0.2)
                    ref_y = ey + int(perp_y * side * es * 0.5) - int(dir_y * 0.2)
                    pygame.draw.circle(surf, EYE_REFLECTION, (ref_x, ref_y), max(1, es // 3))

            tongue_len = int(HEX_SIZE * 0.16)
            tongue_w = max(1, int(HEX_SIZE * 0.022))
            tongue_flick = math.sin(time_float * 14) * 2
            tx = int(sx + dir_x * (tongue_len + tongue_flick))
            ty = int(sy + dir_y * (tongue_len + tongue_flick))
            pygame.draw.line(surf, (210, 70, 70), (int(sx), int(sy)), (tx, ty), tongue_w)
            if dir_len > 0:
                ppx = -dir_y / dir_len
                ppy = dir_x / dir_len
                fork_s = 2
                fork_l = int(HEX_SIZE * 0.04)
                pygame.draw.line(surf, (210, 70, 70),
                    (tx, ty),
                    (tx + int(ppx * fork_s) + int(dir_x * fork_l),
                     ty + int(ppy * fork_s) + int(dir_y * fork_l)),
                    max(1, tongue_w - 1))
                pygame.draw.line(surf, (210, 70, 70),
                    (tx, ty),
                    (tx - int(ppx * fork_s) + int(dir_x * fork_l),
                     ty - int(ppy * fork_s) + int(dir_y * fork_l)),
                    max(1, tongue_w - 1))

    def draw_apple(self, surf, time_float):
        if not self.apple:
            return
        q, r = self.apple
        cx, cy = hex_to_pixel(q, r)

        pulse = 1.0 + math.sin(time_float * 2.5) * 0.06
        sz = int(HEX_SIZE * 0.36 * pulse * 2)
        self.draw_shadow(surf, cx + math.sin(time_float * 0.5) * 1.2, cy, 0.5, int(sz * 0.6), 40)

        bob = math.sin(time_float * 1.2) * 0.8
        sx_p, sy_p, _ = self.camera.project(cx + math.sin(time_float * 0.5) * 1.2, cy, 2 + bob)

        sprite = self._apple_sprites.get(sz)
        if sprite is None:
            sprite = pygame.transform.smoothscale(self.master_apple_sprite, (sz, sz))
            self._apple_sprites[sz] = sprite
        surf.blit(sprite, (int(sx_p - sz // 2), int(sy_p - sz // 2)))

        sx_top, sy_top, _ = self.camera.project(cx, cy, 2 + bob + TILE_HEIGHT * 1.0 + sz * 0.3)
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

    def update_ambient_particles(self):
        target_count = 120
        if len(self.particles) < target_count and random.random() < 0.15:
            q = random.randint(-GRID_RADIUS, GRID_RADIUS)
            r = random.randint(-GRID_RADIUS, GRID_RADIUS)
            cx, cy = hex_to_pixel(q, r)
            cz = random.uniform(0, TILE_HEIGHT * 0.6)
            vx = random.uniform(-0.12, 0.12)
            vy = random.uniform(-0.06, 0.06)
            vz = random.uniform(0.01, 0.06)
            is_firefly = random.random() < 0.3
            if is_firefly:
                c = random.choice([(180, 230, 100), (220, 255, 150), (200, 240, 120)])
                self.particles.emit(cx, cy, cz, vx, vy, vz, c, random.uniform(2, 3.5), random.uniform(4, 8), 'glow')
            else:
                c = random.choice([(50, 160, 140), (70, 190, 155), (90, 210, 170), (40, 140, 130)])
                self.particles.emit(cx, cy, cz, vx, vy, vz, c, random.uniform(1, 2), random.uniform(3, 7))

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
        surf = self.screen
        time_float = self.frame_count / 60.0

        shake_x, shake_y = 0, 0
        if self.screen_shake > 0:
            intensity = self.screen_shake / 15 * 5
            shake_x, shake_y = screen_shake_offset(intensity)

        surf.blit(self.bg_surf, (shake_x, shake_y))
        surf.blit(self.star_surf, (shake_x, shake_y))

        sun_x = WIDTH // 2 + int(math.sin(time_float * SUN_ANGLE_SPEED) * 200)
        sun_y = int(HEIGHT * 0.15)
        surf.blit(self.sun_disc_surf, (sun_x - 62, sun_y - 62), special_flags=pygame.BLEND_ADD)

        self.water_surf.fill((0, 0, 0, 0))
        for wi in range(-25, 25):
            wy = wi * 16
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

            wave = math.sin(wy * 0.04 + time_float * 0.6) * 2
            wave2 = math.sin(wy * 0.07 + time_float * 0.9 + 1) * 1.2
            wave3 = math.sin(wy * 0.02 + time_float * 0.3 + 2.5) * 0.6
            combined_wave = wave + wave2 + wave3

            c = lerp_color(WATER_COLOR_1, WATER_COLOR_2, t)
            fresnel = 0.3 + 0.7 * (1.0 - abs(t - 0.5) * 2) ** 2
            a = int(190 * fresnel)

            pts = [(sx1, sy1 + combined_wave), (sx2, sy2 + combined_wave),
                   (sx2, sy2 + 16 + combined_wave), (sx1, sy1 + 16 + combined_wave)]
            pygame.draw.polygon(self.water_surf, (*c, a), pts)

            if wi % 4 == 0:
                hl_a = int(50 * fresnel * (0.5 + 0.5 * math.sin(time_float * 1.2 + wi * 0.3)))
                if hl_a > 2:
                    pygame.draw.line(self.water_surf, (*WATER_HIGHLIGHT, hl_a),
                        (sx1, sy1 + combined_wave + 1), (sx2, sy2 + combined_wave + 1), 1)

        sun_ref_x = sun_x
        sun_ref_y_start = HEIGHT * 0.5
        sun_ref_h = HEIGHT * 0.2
        self._water_reflect_surf.fill((0, 0, 0, 0))
        for ry in range(int(sun_ref_h)):
            alpha = int(40 * (1 - ry / sun_ref_h) * (0.5 + 0.5 * math.sin(time_float * 2 + ry * 0.1)))
            pygame.draw.line(self._water_reflect_surf, (*SUN_COLOR, alpha), (0, ry), (100, ry), 2)
        surf.blit(self._water_reflect_surf, (sun_ref_x - 50, sun_ref_y_start), special_flags=pygame.BLEND_ADD)

        if not hasattr(self, '_reflect_cache'):
            self._reflect_cache = pygame.Surface((WIDTH, HEIGHT // 3), pygame.SRCALPHA)
            self._reflect_cache.blit(self.bg_surf, (0, 0), (0, HEIGHT // 2, WIDTH, HEIGHT // 3))
            self._reflect_cache = pygame.transform.flip(self._reflect_cache, False, True)
        reflect_alpha = int(30 + 10 * math.sin(time_float * 0.3))
        self._reflect_cache.set_alpha(reflect_alpha)
        surf.blit(self._reflect_cache, (0, HEIGHT - HEIGHT // 3), special_flags=pygame.BLEND_ADD)

        surf.blit(self.water_surf, (0, 0))

        self._build_tile_cache()
        surf.blit(self.ground_cache, (shake_x, shake_y))

        self.draw_cache.fill((0, 0, 0, 0))
        self.draw_cache.blit(self._tile_cache, (0, 0))

        draw_items = []
        if self.apple:
            ax, ay = hex_to_pixel(*self.apple)
            _, _, depth = self.camera.project(ax, ay, 0.5)
            draw_items.append((depth, 'apple'))

        for idx, (q, r) in enumerate(self.snake):
            cx, cy = hex_to_pixel(q, r)
            _, _, depth = self.camera.project(cx, cy, 2)
            draw_items.append((depth, 'snake', idx, q, r))

        draw_list = self._build_depth_buckets(draw_items)

        for item in draw_list:
            if item[1] == 'apple':
                self.draw_apple(self.draw_cache, time_float)
            elif item[1] == 'snake':
                _, _, idx, q, r = item
                self.draw_snake_segment(self.draw_cache, idx, q, r, time_float)

        surf.blit(self.draw_cache, (shake_x, shake_y))

        if self.gl_renderer.available:
            scene = surf.copy()
            result = self.gl_renderer.post_process(scene, time_float, self.fog_surf)
            if result:
                surf.blit(result, (0, 0))
        else:
            bloom_small = pygame.transform.smoothscale(surf, (WIDTH // 4, HEIGHT // 4))
            bloom_blur = pygame.transform.smoothscale(bloom_small, (WIDTH, HEIGHT))
            bloom_blur.set_alpha(28)
            surf.blit(bloom_blur, (0, 0), special_flags=pygame.BLEND_ADD)

            self._rays_surf_cache.fill((0, 0, 0, 0))
            for ri, angle in enumerate(self.sunray_angles):
                ra = angle + math.sin(time_float * 0.15 + ri) * 0.12
                ray_len = 300 + int(math.sin(time_float * 0.1 + ri * 1.5) * 100)
                ex = sun_x + int(math.cos(ra) * ray_len)
                ey = sun_y + int(math.sin(ra) * ray_len)
                ray_a = int(8 + 4 * math.sin(time_float * 0.4 + ri * 1.7))
                ray_w = max(1, 3 - ri // 5)
                pygame.draw.line(self._rays_surf_cache, (200, 220, 255, ray_a), (sun_x, sun_y), (ex, ey), ray_w)
            surf.blit(self._rays_surf_cache, (0, 0), special_flags=pygame.BLEND_ADD)

            surf.blit(self.fog_surf, (0, 0), special_flags=pygame.BLEND_ADD)

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

        draw_ui(surf, shake_x, shake_y, self)

        if self.state == GameState.PAUSED:
            draw_pause_overlay(surf, self)

        if self.state == GameState.GAME_OVER:
            draw_game_over(surf, self)

        draw_minimap(surf, self.snake, self.apple, self)
        surf.blit(self.vignette_surf, (0, 0))

        needs_full = (self._full_redraw_requested or
                      not self._tile_cache_valid or
                      self.eat_flash > 0 or
                      self.state in (GameState.PAUSED, GameState.GAME_OVER) or
                      self.frame_count == 0)
        self._full_redraw_requested = False

        if not needs_full:
            current = self._compute_dirty_rects(time_float, shake_x, shake_y)
            all_rects = self._prev_dirty_rects + current
            self._prev_dirty_rects = current
        else:
            self._prev_dirty_rects = []
            all_rects = [pygame.Rect(0, 0, WIDTH, HEIGHT)]

        self._full_redraw_counter += 1
        if self._full_redraw_counter >= 60:
            all_rects = [pygame.Rect(0, 0, WIDTH, HEIGHT)]
            self._full_redraw_counter = 0

        merged = self._merge_rects(all_rects)
        if len(merged) == 1 and merged[0] == pygame.Rect(0, 0, WIDTH, HEIGHT):
            pygame.display.flip()
        else:
            pygame.display.update(merged)

    def wait_for_key(self):
        while self.state == GameState.START:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.quit()
                        return
                    self.state = GameState.PLAYING
                    return
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.state = GameState.PLAYING
                    return
            draw_start_screen(self)
            pygame.display.flip()
            self.clock.tick(30)

    def run(self):
        self.wait_for_key()
        if self.state == GameState.QUIT:
            pygame.quit()
            sys.exit()
        while self.state != GameState.QUIT:
            self.reset()
            while self.state in (GameState.PLAYING, GameState.PAUSED):
                dt = self.clock.tick(60) / 1000.0
                self.handle_events()
                self.update(dt)
                self.render()
            while self.state == GameState.GAME_OVER:
                dt = self.clock.tick(60) / 1000.0
                self.handle_events()
                self.particles.update_all(dt)
                self.particles.clean()
                self.render()
        pygame.quit()
        sys.exit()

    def quit(self):
        self.state = GameState.QUIT


if __name__ == '__main__':
    SnakeGame().run()
