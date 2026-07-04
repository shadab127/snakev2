import math
import random
import pygame
from config import *
from utils import all_hexes, hex_to_pixel, hex_corners, compute_tile_ao, lerp_color, perlin_noise, generate_soft_shadow, tile_noise, compute_sky_color


class ResourceManager:
    def __init__(self):
        self._init_fonts()
        self._init_atmospherics()
        self._init_sprites()
        self._init_caches()
        self._init_working_surfaces()
        self._init_scene_data()

    def _init_fonts(self):
        self.font_large = pygame.font.Font(FONT_NAME, 52)
        self.font_med = pygame.font.Font(FONT_NAME, 34)
        self.font_small = pygame.font.Font(FONT_NAME, 22)
        self.font_score = pygame.font.Font(FONT_NAME, 30)
        self.font_micro = pygame.font.Font(FONT_NAME, 16)

    def _init_atmospherics(self):
        self.bg_surf = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            t = y / HEIGHT
            if t < 0.5:
                local_t = t / 0.5
                r = int(SKY_TOP[0] + (SKY_MID[0] - SKY_TOP[0]) * local_t)
                g = int(SKY_TOP[1] + (SKY_MID[1] - SKY_TOP[1]) * local_t)
                b = int(SKY_TOP[2] + (SKY_MID[2] - SKY_TOP[2]) * local_t)
            else:
                local_t = (t - 0.5) / 0.5
                r = int(SKY_MID[0] + (SKY_HORIZON[0] - SKY_MID[0]) * local_t)
                g = int(SKY_MID[1] + (SKY_HORIZON[1] - SKY_MID[1]) * local_t)
                b = int(SKY_MID[2] + (SKY_HORIZON[2] - SKY_MID[2]) * local_t)
            pygame.draw.line(self.bg_surf, (r, g, b), (0, y), (WIDTH, y))

        self.star_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for _ in range(200):
            x = random.randint(0, WIDTH)
            y = random.randint(0, int(HEIGHT * 0.35))
            rs = random.randint(1, 2)
            a = random.randint(30, 200)
            c = (255, 255, 255, a)
            pygame.draw.circle(self.star_surf, c, (x, y), rs)
            if rs > 1 and random.random() < 0.3:
                pygame.draw.circle(self.star_surf, (200, 220, 255, a // 3), (x, y), rs + 2)

        sr = 62
        self.sun_disc_surf = pygame.Surface((sr * 2, sr * 2), pygame.SRCALPHA)
        for si in range(sr, 0, -1):
            if si > 22:
                a = int(15 * (1 - (si - 22) / 40))
                sc = (*SUN_GLOW_COLOR, a)
            else:
                t_norm = si / 22
                c_r = int(SUN_COLOR[0] * (0.7 + 0.3 * t_norm))
                c_g = int(SUN_COLOR[1] * (0.7 + 0.3 * t_norm))
                c_b = int(SUN_COLOR[2] * (0.7 + 0.3 * t_norm))
                a = int(200 + 55 * t_norm)
                sc = (c_r, c_g, c_b, a)
            pygame.draw.circle(self.sun_disc_surf, sc, (sr, sr), si)

        sr = 42
        self._start_sun_surf = pygame.Surface((sr * 2, sr * 2), pygame.SRCALPHA)
        for si in range(sr, 0, -1):
            if si > 22:
                a = int(10 * (1 - (si - 22) / 20))
                sc = (*SUN_GLOW_COLOR, a)
            else:
                t_norm = si / 22
                sc = (int(SUN_COLOR[0] * t_norm), int(SUN_COLOR[1] * t_norm), int(SUN_COLOR[2] * t_norm), int(180 * t_norm))
            pygame.draw.circle(self._start_sun_surf, sc, (sr, sr), si)

        self.vignette_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        max_rv = int(math.hypot(WIDTH, HEIGHT) * 0.6)
        for rv in range(max_rv, 0, -1):
            a = int((1 - rv / max_rv) * 200 * VIGNETTE_STRENGTH)
            if a > 0:
                pygame.draw.circle(self.vignette_surf, (0, 0, 0, min(255, a)), (WIDTH // 2, HEIGHT // 2), rv)

        self.ground_cache = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        self._tile_ao_cache = {}
        for q in range(-GRID_RADIUS, GRID_RADIUS + 1):
            for r in range(-GRID_RADIUS, GRID_RADIUS + 1):
                self._tile_ao_cache[(q, r)] = compute_tile_ao(q, r, set())

    def _init_sprites(self):
        self.master_head_sprite = self.generate_sphere_sprite(48, HEAD_COLOR, (230, 255, 240), shininess=20, scale_pattern=False)
        self.master_body_sprites = [
            self.generate_sphere_sprite(48, color, (200, 255, 210), shininess=25, scale_pattern=True)
            for color in SNAKE_COLORS
        ]
        self.master_apple_sprite = self.generate_apple_sprite(48, APPLE_BASE, APPLE_HIGHLIGHT, APPLE_SPECULAR, APPLE_DEEP)
        self.soft_shadow_sprite = generate_soft_shadow(32)

    def generate_sphere_sprite(self, radius, base_color, specular_color=(255, 255, 255), shininess=25, scale_pattern=False):
        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        lx, ly, lz = LIGHT_DIR
        for y in range(size):
            dy = (y - radius) / radius
            dy_sq = dy * dy
            if dy_sq >= 1.0:
                continue
            for x in range(size):
                dx = (x - radius) / radius
                dist_sq = dx * dx + dy_sq
                if dist_sq <= 1.0:
                    dz = math.sqrt(1.0 - dist_sq)
                    scale_factor = 1.0
                    if scale_pattern:
                        u = math.atan2(dy, dx) / math.pi
                        v = math.asin(dz) / math.pi
                        scale_val = math.sin(u * 14 + v * 10) * math.cos(v * 14 - u * 10)
                        scale_factor = 0.84 + 0.16 * scale_val

                    n_dot_l = dx * lx + dy * ly + dz * lz
                    diff = max(0.0, n_dot_l)
                    diff_intensity = 0.15 + 0.85 * diff

                    microfacet = (dz + 0.4 * (dz * dz)) ** 1.5
                    D = microfacet * 2
                    G = min(1.0, 1.0 / (n_dot_l + 0.1 * dz + 0.001))
                    F = 0.15 + (1.0 - 0.15) * (1.0 - n_dot_l) ** 5
                    spec = D * G * F / (4.0 * n_dot_l + 0.01) if n_dot_l > 0 else 0

                    r = min(255, int(base_color[0] * diff_intensity * scale_factor + specular_color[0] * spec * 0.6))
                    g = min(255, int(base_color[1] * diff_intensity * scale_factor + specular_color[1] * spec * 0.6))
                    b = min(255, int(base_color[2] * diff_intensity * scale_factor + specular_color[2] * spec * 0.6))

                    rim = (1.0 - dz) ** 2.5
                    r = min(255, int(r + 80 * rim * (base_color[0] / 255.0)))
                    g = min(255, int(g + 120 * rim * (base_color[1] / 255.0)))
                    b = min(255, int(b + 90 * rim * (base_color[2] / 255.0)))

                    alpha = 255
                    if dist_sq > 0.94:
                        alpha = int(255 * (1.0 - dist_sq) / 0.06)

                    surf.set_at((x, y), (r, g, b, alpha))
        return surf

    def generate_apple_sprite(self, radius, base_color, highlight_color, specular_color, deep_color):
        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        lx, ly, lz = LIGHT_DIR
        for y in range(size):
            dy = (y - radius) / radius
            dy_sq = dy * dy
            if dy_sq >= 1.0:
                continue
            for x in range(size):
                dx = (x - radius) / radius
                dist_sq = dx * dx + dy_sq
                if dist_sq <= 1.0:
                    dz = math.sqrt(1.0 - dist_sq)
                    diff = max(0.0, dx * lx + dy * ly + dz * lz)
                    diff_intensity = 0.2 + 0.8 * diff

                    hx = lx
                    hy = ly
                    hz = lz + 1.0
                    hl = math.sqrt(hx * hx + hy * hy + hz * hz)
                    if hl > 0:
                        hx /= hl
                        hy /= hl
                        hz /= hl
                    spec = max(0.0, dx * hx + dy * hy + dz * hz) ** 60

                    sss_tip = max(0.0, dz ** 2.5) * 0.3
                    sss_skin = max(0.0, -dx * lx - dy * ly - dz * lz) ** 1.5 * 0.15
                    sss = sss_tip + sss_skin

                    noise_dot = perlin_noise(x * 0.4, y * 0.4, 2.0, 1, 0.5) * 0.04

                    r = int(base_color[0] * diff_intensity + deep_color[0] * sss + specular_color[0] * spec)
                    g = int(base_color[1] * diff_intensity + deep_color[1] * sss + specular_color[1] * spec)
                    b = int(base_color[2] * diff_intensity + deep_color[2] * sss + specular_color[2] * spec)
                    r = int(r + r * noise_dot)
                    g = int(g + g * noise_dot)
                    b = int(b + b * noise_dot)
                    r, g, b = min(255, max(0, r)), min(255, max(0, g)), min(255, max(0, b))

                    rim = (1.0 - dz) ** 3
                    r = min(255, int(r + highlight_color[0] * rim * 0.18))
                    g = min(255, int(g + highlight_color[1] * rim * 0.18))
                    b = min(255, int(b + highlight_color[2] * rim * 0.18))

                    alpha = 255
                    if dist_sq > 0.93:
                        alpha = int(255 * (1.0 - dist_sq) / 0.07)
                    surf.set_at((x, y), (r, g, b, alpha))
        return surf

    def generate_particle_sprite(self, radius, color):
        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for y in range(size):
            dy = (y - radius) / radius
            dy_sq = dy * dy
            if dy_sq >= 1.0:
                continue
            for x in range(size):
                dx = (x - radius) / radius
                dist_sq = dx * dx + dy_sq
                if dist_sq <= 1.0:
                    a = int(255 * (1.0 - dist_sq) ** 1.5)
                    r = color[0] * a // 255
                    g = color[1] * a // 255
                    b = color[2] * a // 255
                    surf.set_at((x, y), (r, g, b, a))
        return surf

    def _init_caches(self):
        self._head_sprites = {}
        self._body_sprites = {}
        self._apple_sprites = {}
        for sz in range(10, 61):
            self._head_sprites[sz] = pygame.transform.smoothscale(self.master_head_sprite, (sz, sz))
            self._apple_sprites[sz] = pygame.transform.smoothscale(self.master_apple_sprite, (sz, sz))
        for ci, sprite in enumerate(self.master_body_sprites):
            self._body_sprites[ci] = {}
            for sz in range(10, 61):
                self._body_sprites[ci][sz] = pygame.transform.smoothscale(sprite, (sz, sz))

        self._head_glow_sprites = {}
        for sz in range(10, 61):
            glow_r = max(1, int(sz * 0.7))
            d = glow_r * 2
            surf = pygame.Surface((d, d), pygame.SRCALPHA)
            for gi in range(glow_r, 0, -1):
                ga = int(50 * (1 - gi / glow_r) * 0.3)
                if ga > 0:
                    pygame.draw.circle(surf, (*HEAD_HIGHLIGHT, ga), (glow_r, glow_r), gi)
            self._head_glow_sprites[sz] = surf

        self._apple_glow_sprites = {}
        for glow_r in range(10, 50):
            d = glow_r * 2
            surf = pygame.Surface((d, d), pygame.SRCALPHA)
            for gi in range(glow_r, 0, -1):
                a = int(35 * (1 - gi / glow_r))
                if a > 0:
                    pygame.draw.circle(surf, (*APPLE_BASE, a), (glow_r, glow_r), gi)
            self._apple_glow_sprites[glow_r] = surf

        self.particle_glows = {}
        for color in PARTICLE_COLORS + [(255, 255, 200), (180, 230, 100), (220, 255, 150), (200, 240, 120), (50, 160, 140), (70, 190, 155), (90, 210, 170), (40, 140, 130)]:
            self.particle_glows[color] = self.generate_particle_sprite(16, color)

        self._particle_glow_scaled = {}
        sizes = list(range(4, 41))
        for color, sprite in self.particle_glows.items():
            for sz in sizes:
                self._particle_glow_scaled[(color, sz)] = pygame.transform.smoothscale(sprite, (sz, sz))

    def _init_working_surfaces(self):
        _lr_x = max(2, int(HEX_SIZE * 0.10))
        _lr_y = max(1, int(HEX_SIZE * 0.05))
        self._leaf_surf = pygame.Surface((_lr_x * 3, _lr_y * 3), pygame.SRCALPHA)
        self._water_reflect_surf = pygame.Surface((100, int(HEIGHT * 0.2)), pygame.SRCALPHA)
        self._rays_surf_cache = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    def _init_scene_data(self):
        self.clouds = []
        for _ in range(12):
            self.clouds.append({
                'x': random.uniform(0, WIDTH),
                'y': random.uniform(0, HEIGHT * 0.28),
                'w': random.uniform(80, 200),
                'h': random.uniform(18, 45),
                'speed': random.uniform(0.04, 0.18),
                'alpha': random.randint(20, 55),
            })
        self.sunray_angles = [math.radians(i * 30 + random.uniform(-4, 4)) for i in range(12)]

        all_hex_list = list(all_hexes())
        self._all_hexes_cache = all_hex_list

        self._tile_static_cache = {}
        self._ground_static_cache = {}

        for q, r in all_hex_list:
            cx, cy = hex_to_pixel(q, r)
            corners_world = hex_corners(cx, cy)
            noise = tile_noise(q, r)
            noise_val = noise['detail'] * 0.15

            dist_from_center = (q * q + r * r + q * r) ** 0.5 / GRID_RADIUS
            dist_factor = max(0, 1 - dist_from_center * 0.3)
            tex_variation = 1.0 + 0.06 * noise['tex']

            mat_noise = noise['base']
            if mat_noise > 0.4:
                base_top_color = list(TILE_DIRT)
                base_side_color = list(TILE_SIDE_DARK)
            elif mat_noise < -0.3:
                base_top_color = [130, 220, 165]
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

            grass_seed = noise['grass']
            grass_blades = []
            if grass_seed > 0.1:
                blade_count = int((grass_seed - 0.1) * 7)
                for bi in range(blade_count):
                    a = grass_seed * 6.28 + bi * 1.7 + q * 0.3
                    d = 0.25 + (hash((q, r, bi)) % 100) / 250.0
                    bx = cx + math.cos(a) * d * HEX_SIZE
                    by = cy + math.sin(a) * d * HEX_SIZE
                    blade_h = 3 + (hash((q, r, bi + 100)) % 30) / 15.0
                    blade_w = max(1, int(1 + (hash((q, r, bi + 200)) % 3)))
                    gc = lerp_color((35, 115, 50), (55, 160, 70), 0.3 + (hash((q, r, bi + 300)) % 100) / 200.0)
                    has_flower = hash((q, r, bi + 400)) % 5 == 0
                    flower_color = None
                    if has_flower:
                        flower_color = [(255, 200, 80), (240, 130, 150), (200, 140, 255)][hash((q, r, bi + 500)) % 3]
                    grass_blades.append({
                        'bx': bx, 'by': by,
                        'blade_h': blade_h, 'blade_w': blade_w,
                        'gc': gc, 'has_flower': has_flower,
                        'flower_color': flower_color,
                    })

            self._tile_static_cache[(q, r)] = {
                'corners_world': corners_world,
                'center_world': (cx, cy),
                'base_top_color': tuple(base_top_color),
                'base_side_color': tuple(base_side_color),
                'tex_variation': tex_variation,
                'dist_from_center': dist_from_center,
                'dist_factor': dist_factor,
                'grass_seed': grass_seed,
                'grass_blades': grass_blades,
                'noise': noise,
            }

            ground_dist = dist_from_center
            ground_c = lerp_color(GROUND_LOW, GROUND_DEEP, ground_dist)
            self._ground_static_cache[(q, r)] = {
                'bot_world': [(c_x, c_y, -TILE_HEIGHT - 4) for c_x, c_y in corners_world],
                'color': ground_c,
            }

    def _update_sky(self, time_float, day_cycle):
        sky_top, sky_mid, sky_hor = compute_sky_color(time_float)
        self.bg_surf = pygame.Surface((WIDTH, HEIGHT))
        for y in range(0, HEIGHT, 2):
            t = y / HEIGHT
            if t < 0.5:
                local_t = t / 0.5
                c = lerp_color(sky_top, sky_mid, local_t)
            else:
                local_t = (t - 0.5) / 0.5
                c = lerp_color(sky_mid, sky_hor, local_t)
            self.bg_surf.fill(c, rect=(0, y, WIDTH, 2))

    def cleanup(self):
        pass


def generate_app_icon(size=32):
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    r = size // 2 - 2
    pygame.draw.circle(surf, (60, 180, 80), (cx, cy), r)
    pygame.draw.circle(surf, (80, 220, 100), (cx - 1, cy - 1), r - 1)
    eye_r = max(2, r // 5)
    eye_y = cy - r // 3
    for side in [-1, 1]:
        ex = cx + side * r // 3
        pygame.draw.circle(surf, (255, 255, 255), (ex, eye_y), eye_r)
        pygame.draw.circle(surf, (5, 5, 25), (ex, eye_y), max(1, eye_r // 2))
    pupil_x = cx - 1
    for side in [-1, 1]:
        ex = cx + side * r // 3
        pygame.draw.circle(surf, (255, 255, 255, 180), (ex - 1, eye_y - 1), max(1, eye_r // 3))
    tongue_start = cy + r // 3
    pygame.draw.line(surf, (210, 60, 60), (cx, tongue_start), (cx, tongue_start + 4), 2)
    fork_x = 1
    pygame.draw.line(surf, (210, 60, 60), (cx, tongue_start + 4), (cx - fork_x, tongue_start + 6), 1)
    pygame.draw.line(surf, (210, 60, 60), (cx, tongue_start + 4), (cx + fork_x, tongue_start + 6), 1)
    return surf
