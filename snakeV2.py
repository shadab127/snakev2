#!/usr/bin/env python3
"""
SnakeV2 - 3D Hex Grid Snake Game
Enhanced edition with physically inspired 3D lighting, per-vertex normals,
advanced materials, smooth body interpolation, and high-performance caching.
"""

import pygame
import math
import random
import sys
import time
import struct
from enum import Enum

try:
    import moderngl
    _GL_AVAILABLE = True
except ImportError:
    _GL_AVAILABLE = False

GL_FRAGMENT_SHADER_SRC = '''
#version 330

in vec3 v_base_color;
in vec3 v_normal;
in float v_ao;
in float v_dist_factor;
in float v_fog_depth;
in float v_tex_var;
in float v_q;
in float v_r;

out vec4 f_color;

uniform float u_time_float;
uniform int u_game_over;
uniform float u_eat_flash;

const vec3 LIGHT_DIR = vec3(0.436, -0.524, 0.699);
const float AMBIENT_LIGHT_VAL = 0.25;
const float SUN_ANGLE_SPEED = 0.03;
const vec3 FOG_COLOR = vec3(0.110, 0.157, 0.275);
const vec3 GAME_OVER_TOP = vec3(0.039, 0.098, 0.078);
const vec3 GAME_OVER_SIDE = vec3(0.024, 0.055, 0.047);
const vec3 TILE_GLOW = vec3(0.314, 0.863, 0.588);

void main() {
    vec3 base_c = v_base_color;
    if (u_game_over == 1) {
        if (v_normal.z > 0.5) {
            base_c = GAME_OVER_TOP;
        } else {
            base_c = GAME_OVER_SIDE;
        }
    } else if (u_eat_flash > 0.0) {
        float flash = min(1.0, u_eat_flash / 12.0);
        vec3 flash_c = TILE_GLOW * 0.3;
        base_c = mix(base_c, flash_c, flash * 0.5);
    }

    float sun_factor = 0.85 + 0.15 * sin(u_time_float * SUN_ANGLE_SPEED + v_q * 0.5 + v_r * 0.3);
    float diff = max(0.0, dot(v_normal, LIGHT_DIR));
    float light = (AMBIENT_LIGHT_VAL + (1.0 - AMBIENT_LIGHT_VAL) * diff) * sun_factor * v_dist_factor * v_ao;

    vec3 color = base_c * light;

    float fog_t = clamp((v_fog_depth - 320.0) / 500.0, 0.0, 1.0);
    color = mix(color, FOG_COLOR, fog_t * 0.35);
    color *= v_tex_var;

    f_color = vec4(color, 1.0);
}
'''

GL_VERTEX_SHADER_SRC = '''
#version 330

in vec2 in_position;
in vec3 in_base_color;
in vec3 in_normal;
in float in_ao;
in float in_dist_factor;
in float in_fog_depth;
in float in_tex_var;
in float in_q;
in float in_r;

out vec3 v_base_color;
out vec3 v_normal;
out float v_ao;
out float v_dist_factor;
out float v_fog_depth;
out float v_tex_var;
out float v_q;
out float v_r;

uniform vec2 u_screen_size;

void main() {
    gl_Position = vec4(
        (in_position.x / u_screen_size.x) * 2.0 - 1.0,
        -((in_position.y / u_screen_size.y) * 2.0 - 1.0),
        0.0,
        1.0
    );
    v_base_color = in_base_color;
    v_normal = in_normal;
    v_ao = in_ao;
    v_dist_factor = in_dist_factor;
    v_fog_depth = in_fog_depth;
    v_tex_var = in_tex_var;
    v_q = in_q;
    v_r = in_r;
}
'''

GL_FULLSCREEN_VS = '''
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_pos, 0.0, 1.0);
    v_uv = in_uv;
}
'''

GL_TEXTURE_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
void main() {
    f_color = texture(u_tex, v_uv);
}
'''

GL_TEXTURE_ADD_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
void main() {
    vec4 c = texture(u_tex, v_uv);
    f_color = vec4(c.rgb * c.a, c.a);
}
'''

GL_BLOOM_DOWN_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
uniform vec2 u_texel_size;
const vec3 LUMA = vec3(0.299, 0.587, 0.114);
void main() {
    vec2 ts = u_texel_size;
    vec4 color = vec4(0.0);
    color += texture(u_tex, v_uv + vec2(-ts.x, -ts.y));
    color += texture(u_tex, v_uv + vec2( ts.x, -ts.y));
    color += texture(u_tex, v_uv + vec2(-ts.x,  ts.y));
    color += texture(u_tex, v_uv + vec2( ts.x,  ts.y));
    color *= 0.25;
    float luma = dot(color.rgb, LUMA);
    float bright = max(0.0, luma - 0.25);
    f_color = vec4(color.rgb * bright, 1.0);
}
'''

GL_BLOOM_BLUR_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
uniform vec2 u_texel_size;
uniform vec2 u_direction;
void main() {
    vec4 color = texture(u_tex, v_uv) * 0.227027;
    vec2 ts = u_texel_size * u_direction;
    color += texture(u_tex, v_uv + ts) * 0.1945946;
    color += texture(u_tex, v_uv - ts) * 0.1945946;
    color += texture(u_tex, v_uv + ts * 2.0) * 0.1216216;
    color += texture(u_tex, v_uv - ts * 2.0) * 0.1216216;
    color += texture(u_tex, v_uv + ts * 3.0) * 0.054054;
    color += texture(u_tex, v_uv - ts * 3.0) * 0.054054;
    color += texture(u_tex, v_uv + ts * 4.0) * 0.016216;
    color += texture(u_tex, v_uv - ts * 4.0) * 0.016216;
    f_color = vec4(color.rgb, 1.0);
}
'''

GL_BLOOM_UP_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_bloom;
uniform sampler2D u_scene;
void main() {
    vec3 bloom = texture(u_bloom, v_uv).rgb;
    vec3 scene = texture(u_scene, v_uv).rgb;
    f_color = vec4(scene + bloom * 0.8, 1.0);
}
'''

GL_GOD_RAYS_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform vec2 u_sun_pos;
uniform float u_time;
void main() {
    vec2 dir = v_uv - u_sun_pos;
    float dist = length(dir);
    if (dist < 0.001) { f_color = vec4(0.0); return; }
    dir = normalize(dir);
    float rays = 0.0;
    for (int i = 0; i < 12; i++) {
        float ang = 0.5236 * float(i) + sin(u_time * 0.15 + float(i)) * 0.12;
        vec2 rd = vec2(cos(ang + u_time * 0.5), sin(ang + u_time * 0.5));
        float d = abs(dot(dir, rd));
        rays += pow(d, 8.0) * max(0.0, 1.0 - dist * 0.5);
    }
    rays *= max(0.0, 1.0 - dist * 0.8);
    f_color = vec4(vec3(0.78, 0.86, 1.0) * rays * 0.35, rays * 0.3);
}
'''

GL_WATER_VS = '''
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
out float v_wave;
uniform float u_time;
uniform float u_amp_scale;
void main() {
    vec2 p = in_pos;
    float wave = sin(p.y * 0.04 + u_time * 0.6) * 2.0
               + sin(p.y * 0.07 + u_time * 0.9 + 1.0) * 1.2
               + sin(p.y * 0.02 + u_time * 0.3 + 2.5) * 0.6;
    p.y += wave * u_amp_scale;
    gl_Position = vec4((p.x / 640.0) - 1.0, -((p.y / 400.0) - 1.0), 0.0, 1.0);
    v_uv = in_uv;
    v_wave = wave;
}
'''

GL_WATER_FS = '''
#version 330
in vec2 v_uv;
in float v_wave;
out vec4 f_color;
uniform float u_time;
const vec3 WC1 = vec3(0.024, 0.078, 0.196);
const vec3 WC2 = vec3(0.047, 0.137, 0.275);
const vec3 WH = vec3(0.196, 0.510, 0.784);
void main() {
    float t = v_uv.y;
    vec3 c = mix(WC1, WC2, t);
    float fresnel = 0.3 + 0.7 * pow(1.0 - abs(t - 0.5) * 2.0, 2.0);
    float a = 190.0 * fresnel / 255.0;
    float hl = 0.0;
    if (int(v_uv.x * 100.0) % 4 == 0) {
        hl = 50.0 * fresnel * (0.5 + 0.5 * sin(u_time * 1.2 + v_uv.y * 50.0));
    }
    c += WH * hl / 255.0;
    f_color = vec4(c, a);
}
'''

WIDTH, HEIGHT = 1280, 800
HEX_SIZE = 32
GRID_RADIUS = 7
TILE_HEIGHT = 18

TILT = math.radians(52)
CAM_DIST = 450
FOV = 420
Y_OFFSET = HEIGHT * 0.58

FPS = 30

DIR_VECTORS = [(1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)]

SKY_TOP = (8, 12, 35)
SKY_MID = (15, 25, 55)
SKY_BOT = (25, 35, 70)
SKY_HORIZON = (40, 60, 95)
SUN_COLOR = (255, 240, 200)
SUN_GLOW_COLOR = (255, 200, 120)

LIGHT_DIR = (0.436, -0.524, 0.699)
AMBIENT_LIGHT = 0.25
SUN_ANGLE_SPEED = 0.03

TILE_BASE = (35, 85, 65)
TILE_TOP = (45, 105, 80)
TILE_TOP_LIGHT = (55, 125, 95)
TILE_SIDE_LIT = (28, 70, 52)
TILE_SIDE = (20, 55, 40)
TILE_SIDE_DARK = (12, 35, 25)
TILE_EDGE = (60, 140, 100)
TILE_EDGE_HIGHLIGHT = (90, 180, 130)
TILE_GLOW = (80, 220, 150)
TILE_MOSS = (30, 90, 50)
TILE_DIRT = (70, 55, 35)

SNAKE_COLORS = [
    (40, 200, 90),
    (35, 185, 85),
    (32, 170, 80),
    (30, 155, 75),
    (28, 140, 70),
    (25, 125, 65),
    (22, 110, 60),
    (20, 95, 55),
]
HEAD_COLOR = (100, 255, 140)
HEAD_HIGHLIGHT = (140, 255, 180)
EYE_WHITE = (245, 255, 248)
EYE_PUPIL = (10, 10, 25)
EYE_REFLECTION = (255, 255, 255)
EYE_IRIS = (30, 180, 80)

APPLE_BASE = (220, 35, 55)
APPLE_HIGHLIGHT = (255, 120, 130)
APPLE_SPECULAR = (255, 200, 200)
APPLE_DEEP = (160, 20, 35)
APPLE_STEM = (55, 35, 18)
APPLE_LEAF = (45, 165, 55)
APPLE_LEAF_HIGHLIGHT = (80, 220, 90)
APPLE_LEAF_VEIN = (35, 130, 42)
APPLE_SPOTS = (180, 25, 40)

PARTICLE_COLORS = [
    (255, 230, 90),
    (255, 190, 60),
    (255, 110, 110),
    (110, 255, 190),
    (255, 255, 160),
    (255, 150, 200),
]

TEXT_WHITE = (230, 245, 235)
TEXT_GLOW = (80, 220, 150)
TEXT_YELLOW = (255, 245, 150)
TEXT_DIM = (100, 140, 120)

GROUND_LOW = (4, 8, 20)
GROUND_DEEP = (2, 4, 12)

WATER_COLOR_1 = (6, 20, 50)
WATER_COLOR_2 = (12, 35, 70)
WATER_HIGHLIGHT = (50, 130, 200)
FOG_COLOR = (28, 40, 70)
VIGNETTE_STRENGTH = 0.5

FONT_NAME = None

NOISE_SEED = random.randint(0, 10000)
_rng = random.Random(NOISE_SEED)
_PERM = list(range(256))
_rng.shuffle(_PERM)
_PERM += _PERM
_perlin_cache = {}

_tile_noise_cache = {}
# _noise_cache_frame removed in Roadmap #6; cache is now permanent


def perlin_noise(x, y, scale=1.0, octaves=3, persistence=0.5):
    key = (int(x * 100), int(y * 100), scale, octaves)
    if key in _perlin_cache:
        return _perlin_cache[key]

    def fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(a, b, t):
        return a + t * (b - a)

    def grad(hash, x, y):
        h = hash & 3
        if h == 0: return x + y
        elif h == 1: return -x + y
        elif h == 2: return x - y
        else: return -x - y

    def noise2d(x, y):
        X = int(math.floor(x)) & 255
        Y = int(math.floor(y)) & 255
        x -= math.floor(x)
        y -= math.floor(y)
        u = fade(x)
        v = fade(y)
        p = _PERM
        A = p[X] + Y
        B = p[X + 1] + Y
        aa = p[A]
        ab = p[A + 1]
        ba = p[B]
        bb = p[B + 1]
        return lerp(lerp(grad(p[aa], x, y), grad(p[ba], x - 1, y), u),
                   lerp(grad(p[ab], x, y - 1), grad(p[bb], x - 1, y - 1), u), v)

    total = 0
    amplitude = 1
    frequency = scale
    max_val = 0
    for _ in range(octaves):
        total += noise2d(x * frequency, y * frequency) * amplitude
        max_val += amplitude
        amplitude *= persistence
        frequency *= 2

    result = total / max_val
    _perlin_cache[key] = result
    return result


def catmull_rom(p0, p1, p2, p3, t):
    t2 = t * t
    t3 = t2 * t
    return 0.5 * ((2.0 * p1) + (-p0 + p2) * t + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3)


def hex_side_normal(face_idx):
    angle = math.radians(60 * face_idx - 30)
    return (math.cos(angle), math.sin(angle), 0.0)


def hex_to_pixel(q, r):
    x = HEX_SIZE * math.sqrt(3) * (q + r / 2)
    y = HEX_SIZE * 1.5 * r
    return x, y


def hex_corners(cx, cy):
    corners = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        corners.append((
            cx + HEX_SIZE * math.cos(angle),
            cy + HEX_SIZE * math.sin(angle)
        ))
    return corners


def in_bounds(q, r):
    return max(abs(q), abs(r), abs(q + r)) <= GRID_RADIUS


def all_hexes():
    for q in range(-GRID_RADIUS, GRID_RADIUS + 1):
        for r in range(-GRID_RADIUS, GRID_RADIUS + 1):
            if in_bounds(q, r):
                yield (q, r)


def project(x, y, z=0):
    y_rot = y * math.cos(TILT) - z * math.sin(TILT)
    depth = -y * math.sin(TILT) - z * math.cos(TILT)
    z_cam = depth + CAM_DIST
    factor = FOV / z_cam if z_cam > 0 else 999
    sx = x * factor + WIDTH / 2
    sy = y_rot * factor + Y_OFFSET
    return sx, sy, z_cam


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def mul_color(c, m):
    return (min(255, max(0, int(c[0] * m))), min(255, max(0, int(c[1] * m))), min(255, max(0, int(c[2] * m))))


def add_color(c1, c2):
    return (min(255, c1[0] + c2[0]), min(255, c1[1] + c2[1]), min(255, c1[2] + c2[2]))


def screen_shake_offset(intensity):
    return (random.randint(-int(intensity), int(intensity)),
            random.randint(-int(intensity), int(intensity)))


def compute_tile_ao(q, r, snake_set):
    neighbor_count = 0
    for dq, dr in DIR_VECTORS:
        nq, nr = q + dq, r + dr
        if not in_bounds(nq, nr):
            neighbor_count += 1
        elif (nq, nr) in snake_set:
            neighbor_count += 1
    edge_dist = (q * q + r * r + q * r) ** 0.5 / GRID_RADIUS
    ao = 1.0 - 0.04 * neighbor_count - 0.12 * edge_dist
    return max(0.55, min(1.0, ao))


def dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def tile_noise(q, r):
    if (q, r) not in _tile_noise_cache:
        _tile_noise_cache[(q, r)] = {
            'base': perlin_noise(q * 0.5 + r * 0.8, r * 0.5 - q * 0.8, 1.0, 2, 0.5),
            'detail': perlin_noise(q * 2.3 + r * 1.7, r * 2.3 - q * 1.7, 1.5, 2, 0.5),
            'moss': perlin_noise(q * 3.7 + r * 2.1, r * 3.7 - q * 2.1, 2.0, 2, 0.4),
            'dirt': perlin_noise(q * 4.1 + r * 3.3 + 100, r * 4.1 - q * 3.3 + 100, 2.5, 2, 0.35),
            'crack': perlin_noise(q * 3.7 + r * 2.1, r * 3.7 - q * 2.1, 2.0, 2, 0.3),
            'grass': perlin_noise(q * 5.1 + r * 3.3, r * 5.1 - q * 3.3, 2.0, 2, 0.4),
            'tex': perlin_noise(q * 8 + r * 5, r * 8 - q * 5, 3.0, 2, 0.4),
        }
    return _tile_noise_cache[(q, r)]


def generate_soft_shadow(radius):
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        dy = (y - radius) / radius
        dy2 = dy * dy
        for x in range(size):
            dx = (x - radius) / radius
            dist2 = dx * dx + dy2
            if dist2 <= 1.0:
                alpha = int(60 * (1.0 - dist2) ** 2)
                if alpha > 0:
                    surf.set_at((x, y), (0, 0, 0, alpha))
    return surf


class Particle:
    def __init__(self, x, y, z, vx, vy, vz, color, size, lifetime, particle_type='normal'):
        self.x = x
        self.y = y
        self.z = z
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.color = color
        self.size = size
        self.lifetime = lifetime
        self.age = 0
        self.particle_type = particle_type
        self.rotation = random.uniform(0, math.tau)
        self.rot_speed = random.uniform(-2, 2)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.vz -= 9.8 * dt * 0.3
        self.vx *= 0.99
        self.vy *= 0.99
        self.age += dt
        self.rotation += self.rot_speed * dt

    @property
    def dead(self):
        return self.age >= self.lifetime

    @property
    def alpha(self):
        t = self.age / self.lifetime
        if t < 0.15:
            return 255
        return int(255 * (1 - (t - 0.15) / 0.85) ** 1.5)

    @property
    def current_size(self):
        t = self.age / self.lifetime
        return self.size * (1 - t * 0.3) * (1 + 0.2 * math.sin(self.age * 10))

    def draw(self, surf, game=None):
        sx, sy, depth = project(self.x, self.y, self.z)
        s = max(1, int(self.current_size))
        a = self.alpha
        if a <= 0:
            return

        r, g, b = self.color

        if self.particle_type == 'spark':
            length = s * 3
            end_x = sx + math.cos(self.rotation) * length
            end_y = sy + math.sin(self.rotation) * length
            sc = (r * a // 255, g * a // 255, b * a // 255)
            pygame.draw.line(surf, sc, (int(sx), int(sy)), (int(end_x), int(end_y)), max(1, s // 2))
            pygame.draw.circle(surf, (min(255, sc[0]+80), min(255, sc[1]+80), min(255, sc[2]+80)), (int(sx), int(sy)), max(1, s))
        elif self.particle_type == 'glow' and game and self.color in game.particle_glows:
            g_size = max(4, int(s * 5))
            scaled_glow = game._particle_glow_scaled.get((self.color, g_size))
            if scaled_glow is None:
                base = game.particle_glows[self.color]
                scaled_glow = pygame.transform.smoothscale(base, (g_size, g_size))
                game._particle_glow_scaled[(self.color, g_size)] = scaled_glow
            scaled_glow.set_alpha(a)
            surf.blit(scaled_glow, (int(sx - g_size / 2), int(sy - g_size / 2)), special_flags=pygame.BLEND_ADD)
        elif self.particle_type == 'glow':
            g_size = max(4, int(s * 6))
            if game and hasattr(game, '_particle_glow_scaled'):
                scaled_glow = game._particle_glow_scaled.get((self.color, g_size))
                if scaled_glow is None:
                    glow_surf = pygame.Surface((g_size, g_size), pygame.SRCALPHA)
                    center = g_size // 2
                    for gi in range(center, 0, -1):
                        ga = int(a * (1 - gi / center) * 0.5)
                        if ga > 0:
                            pygame.draw.circle(glow_surf, (r, g, b, ga), (center, center), gi)
                    game._particle_glow_scaled[(self.color, g_size)] = glow_surf
                    scaled_glow = glow_surf
                else:
                    scaled_glow.set_alpha(a)
                surf.blit(scaled_glow, (int(sx - g_size / 2), int(sy - g_size / 2)), special_flags=pygame.BLEND_ADD)
            else:
                glow_surf = pygame.Surface((g_size, g_size), pygame.SRCALPHA)
                center = g_size // 2
                for gi in range(center, 0, -1):
                    ga = int(a * (1 - gi / center) * 0.5)
                    if ga > 0:
                        pygame.draw.circle(glow_surf, (r, g, b, ga), (center, center), gi)
                surf.blit(glow_surf, (int(sx - g_size / 2), int(sy - g_size / 2)), special_flags=pygame.BLEND_ADD)
        else:
            sc = (r * a // 255, g * a // 255, b * a // 255)
            pygame.draw.circle(surf, sc, (int(sx), int(sy)), s)
            if s > 2:
                hl = (min(255, sc[0] + 100), min(255, sc[1] + 100), min(255, sc[2] + 100))
                pygame.draw.circle(surf, hl, (int(sx - s * 0.25), int(sy - s * 0.25)), max(1, s // 2))
        return depth


class ParticlePool:
    def __init__(self, initial_capacity=500):
        self._alive = []
        self._free = []
        for _ in range(initial_capacity):
            p = Particle(0, 0, 0, 0, 0, 0, (0, 0, 0), 1, 0.1)
            p.age = 99999
            self._free.append(p)

    def emit(self, x, y, z, vx, vy, vz, color, size, lifetime, particle_type='normal'):
        if self._free:
            p = self._free.pop()
        else:
            p = Particle(0, 0, 0, 0, 0, 0, (0, 0, 0), 1, 0.1)
        p.x, p.y, p.z = x, y, z
        p.vx, p.vy, p.vz = vx, vy, vz
        p.color = color
        p.size = size
        p.lifetime = lifetime
        p.age = 0
        p.particle_type = particle_type
        p.rotation = random.uniform(0, math.tau)
        p.rot_speed = random.uniform(-2, 2)
        self._alive.append(p)
        return p

    def update_all(self, dt):
        for p in self._alive:
            p.update(dt)

    def clean(self):
        remaining = []
        for p in self._alive:
            if p.dead:
                self._free.append(p)
            else:
                remaining.append(p)
        self._alive = remaining

    def clear(self):
        self._free.extend(self._alive)
        self._alive = []

    @property
    def alive(self):
        return self._alive

    def __len__(self):
        return len(self._alive)

    def __iter__(self):
        return iter(self._alive)

    def sort_by_z(self):
        self._alive.sort(key=lambda p: p.z)


class GameState(Enum):
    START = 1
    PLAYING = 2
    PAUSED = 3
    GAME_OVER = 4
    QUIT = 5


class GLRenderer:
    def __init__(self):
        self.available = False
        self._quad_vao_cache = {}
        self.tex_cache = {}
        self.vbo = None
        self.vao_tile = None
        self.vertex_count = 0
        if not _GL_AVAILABLE:
            return
        try:
            self.ctx = moderngl.create_context(standalone=True, require=330)
            self.available = True
            self._compile_shaders()
            self._create_fbos()
            self._create_fullscreen_quad()
        except Exception as e:
            print(f"GLRenderer: {e}")
            self.available = False

    def _compile_shaders(self):
        self.prog_tile = self.ctx.program(
            vertex_shader=GL_VERTEX_SHADER_SRC,
            fragment_shader=GL_FRAGMENT_SHADER_SRC)
        self.prog_texture = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_TEXTURE_FS)
        self.prog_texture_add = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_TEXTURE_ADD_FS)
        self.prog_bloom_down = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_BLOOM_DOWN_FS)
        self.prog_bloom_blur = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_BLOOM_BLUR_FS)
        self.prog_bloom_up = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_BLOOM_UP_FS)
        self.prog_god_rays = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_GOD_RAYS_FS)

    def _create_fbos(self):
        self.tex_scene = self.ctx.texture((WIDTH, HEIGHT), 4)
        self.fbo_scene = self.ctx.framebuffer(color_attachments=[self.tex_scene])
        self.tex_main = self.ctx.texture((WIDTH, HEIGHT), 4)
        self.fbo_main = self.ctx.framebuffer(color_attachments=[self.tex_main])
        bw, bh = WIDTH // 4, HEIGHT // 4
        self.tex_bloom1 = self.ctx.texture((bw, bh), 4)
        self.tex_bloom2 = self.ctx.texture((bw, bh), 4)
        self.fbo_bloom1 = self.ctx.framebuffer(color_attachments=[self.tex_bloom1])
        self.fbo_bloom2 = self.ctx.framebuffer(color_attachments=[self.tex_bloom2])
        self.fbo_tile = self.ctx.simple_framebuffer((WIDTH, HEIGHT), dtype='f4')

    def _create_fullscreen_quad(self):
        quad = [-1.0, -1.0, 0.0, 0.0,
                 1.0, -1.0, 1.0, 0.0,
                 1.0,  1.0, 1.0, 1.0,
                -1.0, -1.0, 0.0, 0.0,
                 1.0,  1.0, 1.0, 1.0,
                -1.0,  1.0, 0.0, 1.0]
        buf = bytearray()
        for i in range(0, len(quad), 4):
            buf.extend(struct.pack('<2f2f', quad[i], quad[i+1], quad[i+2], quad[i+3]))
        self.quad_vbo = self.ctx.buffer(bytes(buf))

    def _quad_vao(self, prog):
        if prog not in self._quad_vao_cache:
            self._quad_vao_cache[prog] = self.ctx.vertex_array(
                prog, self.quad_vbo, 'in_pos', 'in_uv')
        return self._quad_vao_cache[prog]

    def _set_fbo(self, fbo, clear=True):
        fbo.use()
        w, h = fbo.size
        self.ctx.viewport = (0, 0, w, h)
        if clear:
            self.ctx.clear(0.0, 0.0, 0.0, 0.0)

    def _set_uniform(self, prog, name, value):
        try:
            prog[name].value = value
        except (KeyError, ValueError):
            pass

    def _render_quad(self, prog, src_tex, target_fbo=None, blend=False, uniforms=None):
        if target_fbo:
            self._set_fbo(target_fbo, clear=False)
        if blend:
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE
        else:
            self.ctx.disable(moderngl.BLEND)
        src_tex.use(0)
        self._set_uniform(prog, 'u_tex', 0)
        if uniforms:
            for k, v in uniforms.items():
                self._set_uniform(prog, k, v)
        self._quad_vao(prog).render(moderngl.TRIANGLES)

    def upload_texture(self, name, surf):
        rgba = pygame.image.tostring(surf, 'RGBA', True)
        w, h = surf.get_size()
        if name in self.tex_cache:
            t = self.tex_cache[name]
            if t.size == (w, h):
                t.write(rgba)
                return t
            t.release()
        t = self.ctx.texture((w, h), 4, data=rgba)
        t.filter = (moderngl.LINEAR, moderngl.LINEAR)
        t.repeat_x = False
        t.repeat_y = False
        self.tex_cache[name] = t
        return t

    def render_tiles_to_fbo(self, game, fbo):
        if not self.available:
            return False
        try:
            snake_set = set(game.snake)
            tile_depths = [(project(hex_to_pixel(q, r)[0], hex_to_pixel(q, r)[1], 0)[2], q, r) for q, r in all_hexes()]
            tile_depths.sort(key=lambda x: x[0], reverse=True)
            all_verts = []
            for _, q, r in tile_depths:
                cx, cy = hex_to_pixel(q, r)
                corners = hex_corners(cx, cy)
                top_pts = [project(c_x, c_y, 0)[:2] for c_x, c_y in corners]
                bot_pts = [project(c_x, c_y, -TILE_HEIGHT)[:2] for c_x, c_y in corners]
                cx_proj = sum(p[0] for p in top_pts) / 6
                cy_proj = sum(p[1] for p in top_pts) / 6
                noise = tile_noise(q, r)
                noise_val = noise['detail'] * 0.15
                dist_from_center = (q * q + r * r + q * r) ** 0.5 / GRID_RADIUS
                dist_factor = max(0, 1 - dist_from_center * 0.3)
                ao_val = compute_tile_ao(q, r, snake_set)
                mat_noise = noise['base']
                if mat_noise > 0.4:
                    base_top_color, base_side_color = list(TILE_DIRT), list(TILE_SIDE_DARK)
                elif mat_noise < -0.3:
                    base_top_color, base_side_color = [60, 110, 80], list(TILE_SIDE)
                else:
                    base_top_color, base_side_color = list(TILE_TOP), list(TILE_SIDE)
                moss_noise = noise['moss']
                if moss_noise > 0.15:
                    moss_t = min(1.0, (moss_noise - 0.15) * 3)
                    base_top_color = list(lerp_color(tuple(base_top_color), TILE_MOSS, moss_t * 0.35))
                dirt_noise = noise['dirt']
                if dirt_noise > 0.2:
                    dirt_t = min(1.0, (dirt_noise - 0.2) * 2.5)
                    for ci in range(3):
                        base_top_color[ci] = min(255, int(base_top_color[ci] + (TILE_DIRT[ci] - base_top_color[ci]) * dirt_t * 0.25))
                noise_offset = int(noise_val * 20)
                for ci in range(3):
                    base_top_color[ci] = max(0, min(255, base_top_color[ci] + noise_offset))
                if (q, r) in snake_set:
                    base_top_color = list(lerp_color(tuple(base_top_color), TILE_TOP_LIGHT, 0.15))
                fog_depth = project(cx, cy, 0)[2]
                tex_variation = 1.0 + 0.06 * noise['tex']
                ftop_norm = tuple(c / 255.0 for c in base_top_color)
                fside_norm = tuple(c / 255.0 for c in base_side_color)
                for i in range(6):
                    j = (i + 1) % 6
                    for px, py in [top_pts[i], top_pts[j], (cx_proj, cy_proj)]:
                        all_verts.append((px, py, ftop_norm[0], ftop_norm[1], ftop_norm[2],
                                          0.0, 0.0, 1.0, ao_val, dist_factor, fog_depth, tex_variation, float(q), float(r)))
                for i in range(6):
                    j = (i + 1) % 6
                    nx_s, ny_s, nz_s = hex_side_normal(i)
                    for px, py in [top_pts[i], top_pts[j], bot_pts[j], top_pts[i], bot_pts[j], bot_pts[i]]:
                        all_verts.append((px, py, fside_norm[0], fside_norm[1], fside_norm[2],
                                          nx_s, ny_s, nz_s, ao_val, dist_factor, fog_depth, tex_variation, float(q), float(r)))
            self.vertex_count = len(all_verts)
            buf = bytearray()
            for v in all_verts:
                buf.extend(struct.pack('<14f', *v))
            if self.vbo is None or len(buf) != self.vbo.size:
                self.vbo = self.ctx.buffer(bytes(buf))
                self.vao_tile = self.ctx.vertex_array(self.prog_tile, self.vbo,
                    'in_position', 'in_base_color', 'in_normal',
                    'in_ao', 'in_dist_factor', 'in_fog_depth',
                    'in_tex_var', 'in_q', 'in_r')
            else:
                self.vbo.write(bytes(buf))
            self._set_fbo(fbo)
            time_float = game.frame_count / 60.0
            self._set_uniform(self.prog_tile, 'u_time_float', time_float)
            self._set_uniform(self.prog_tile, 'u_game_over', 1 if game.state == GameState.GAME_OVER else 0)
            self._set_uniform(self.prog_tile, 'u_eat_flash', game.eat_flash)
            self._set_uniform(self.prog_tile, 'u_screen_size', (float(WIDTH), float(HEIGHT)))
            if self.vao_tile:
                self.vao_tile.render(moderngl.TRIANGLES, vertices=self.vertex_count)
            return True
        except Exception as e:
            print(f"GL tile render error: {e}")
            return False

    def post_process(self, scene_surf, time_float, fog_surf):
        if not self.available:
            return None
        try:
            tex_scene = self.upload_texture('_scene', scene_surf)
            self._set_fbo(self.fbo_main)
            self._render_quad(self.prog_texture, tex_scene)
            bw, bh = WIDTH // 4, HEIGHT // 4
            self._set_fbo(self.fbo_bloom1)
            self._render_quad(self.prog_bloom_down, tex_scene,
                              uniforms={'u_texel_size': (1.0 / WIDTH, 1.0 / HEIGHT)})
            self._set_fbo(self.fbo_bloom2)
            self._render_quad(self.prog_bloom_blur, self.tex_bloom1,
                              uniforms={'u_texel_size': (1.0 / bw, 1.0 / bh), 'u_direction': (1.0, 0.0)})
            self._set_fbo(self.fbo_bloom1)
            self._render_quad(self.prog_bloom_blur, self.tex_bloom2,
                              uniforms={'u_texel_size': (1.0 / bw, 1.0 / bh), 'u_direction': (0.0, 1.0)})
            self.tex_bloom1.use(0)
            tex_scene.use(1)
            self._set_fbo(self.fbo_main, clear=False)
            self._set_uniform(self.prog_bloom_up, 'u_bloom', 0)
            self._set_uniform(self.prog_bloom_up, 'u_scene', 1)
            self._quad_vao(self.prog_bloom_up).render(moderngl.TRIANGLES)
            sun_x = WIDTH // 2 + int(math.sin(time_float * SUN_ANGLE_SPEED) * 200)
            sun_y = int(HEIGHT * 0.15)
            self._set_fbo(self.fbo_main, clear=False)
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE
            self._set_uniform(self.prog_god_rays, 'u_sun_pos', (sun_x / WIDTH, sun_y / HEIGHT))
            self._set_uniform(self.prog_god_rays, 'u_time', time_float)
            self._quad_vao(self.prog_god_rays).render(moderngl.TRIANGLES)
            self.ctx.disable(moderngl.BLEND)
            self._render_quad(self.prog_texture_add, self.upload_texture('_fog', fog_surf),
                              target_fbo=self.fbo_main, blend=True)
            raw = self.fbo_main.read(components=4, alignment=1, dtype='u1')
            return pygame.image.frombuffer(raw, (WIDTH, HEIGHT), 'RGBA')
        except Exception as e:
            print(f"GL post_process error: {e}")
            return None


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

        self.fog_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for fy in range(HEIGHT):
            t = fy / HEIGHT
            a = int(t ** 3 * 45)
            if a > 0:
                pygame.draw.line(self.fog_surf, (*FOG_COLOR, a), (0, fy), (WIDTH, fy))

        self.vignette_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        max_rv = int(math.hypot(WIDTH, HEIGHT) * 0.6)
        for rv in range(max_rv, 0, -1):
            a = int((1 - rv / max_rv) * 200 * VIGNETTE_STRENGTH)
            if a > 0:
                pygame.draw.circle(self.vignette_surf, (0, 0, 0, min(255, a)), (WIDTH // 2, HEIGHT // 2), rv)

        self.ground_cache = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for q, r in all_hexes():
            cx, cy = hex_to_pixel(q, r)
            corners = hex_corners(cx, cy)
            bot_pts = []
            for cx_c, cy_c in corners:
                sx_b, sy_b, _ = project(cx_c, cy_c, -TILE_HEIGHT - 4)
                bot_pts.append((sx_b, sy_b))
            dist = (q * q + r * r + q * r) ** 0.5 / GRID_RADIUS
            ground_c = lerp_color(GROUND_LOW, GROUND_DEEP, dist)
            pygame.draw.polygon(self.ground_cache, ground_c, bot_pts)

        self._tile_ao_cache = {}
        for q in range(-GRID_RADIUS, GRID_RADIUS + 1):
            for r in range(-GRID_RADIUS, GRID_RADIUS + 1):
                if in_bounds(q, r):
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
        for sz in range(10, 41):
            self._head_sprites[sz] = pygame.transform.smoothscale(self.master_head_sprite, (sz, sz))
            self._apple_sprites[sz] = pygame.transform.smoothscale(self.master_apple_sprite, (sz, sz))
        for ci, sprite in enumerate(self.master_body_sprites):
            self._body_sprites[ci] = {}
            for sz in range(10, 41):
                self._body_sprites[ci][sz] = pygame.transform.smoothscale(sprite, (sz, sz))

        self._head_glow_sprites = {}
        for sz in range(10, 41):
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

    def cleanup(self):
        pass


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
            sx, sy, _ = project(ax, ay, 0.5)
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
            sx, sy, _ = project(cx, cy, 2)
            sr = int(HEX_SIZE * 0.6)
            rects.append(pygame.Rect(sx + shake_x - sr, sy + shake_y - sr, sr * 2, sr * 2))
        for p in self.particles.alive:
            sx, sy, _ = project(p.x, p.y, p.z)
            ps = int(p.current_size) + 8
            rects.append(pygame.Rect(sx + shake_x - ps, sy + shake_y - ps, ps * 2, ps * 2))
        rects.append(pygame.Rect(0, 0, WIDTH, int(HEIGHT * 0.35)))
        rects.append(pygame.Rect(20 + shake_x, 18 + shake_y, 200, 72))
        return rects

    def _build_tile_cache(self):
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
                self._draw_tile_decorations(self._tile_cache, q, r, time_float)
            self._tile_cache_valid = True
            return

        self._tile_cache.fill((0, 0, 0, 0))
        time_float = self.frame_count / 60.0
        tile_items = [(project(hex_to_pixel(q, r)[0], hex_to_pixel(q, r)[1], 0)[2], q, r) for q, r in all_hexes()]
        tile_items.sort(key=lambda x: x[0], reverse=True)
        for _, q, r in tile_items:
            self.draw_tile(self._tile_cache, q, r, time_float)
        self._tile_cache_valid = True

    def _draw_tile_decorations(self, surf, q, r, time_float):
        cx, cy = hex_to_pixel(q, r)
        corners = hex_corners(cx, cy)
        top_pts = []
        for corner_x, corner_y in corners:
            sx_t, sy_t, _ = project(corner_x, corner_y, 0)
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
        fog_t = max(0, min(1, (project(cx, cy, 0)[2] - 320) / 500))
        if fog_t > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), FOG_COLOR, fog_t * 0.35)
        tex_variation = 1.0 + 0.06 * noise['tex']
        final_tri_color = mul_color(tuple(final_tri_color), tex_variation)

        # Edge outline
        pygame.draw.polygon(surf, edge_color, top_pts, max(1, int(1 + sun_factor * 0.5)))

        # Bevel highlights
        bevel_n = (0.0, 0.0, 1.0)
        bevel_light = AMBIENT_LIGHT + (1.0 - AMBIENT_LIGHT) * max(0.0, dot3(bevel_n, LIGHT_DIR))
        bevel_brightness = bevel_light * sun_factor * ao
        inner_hl = mul_color(TILE_EDGE_HIGHLIGHT, 0.2 * bevel_brightness)
        for i in range(6):
            j = (i + 1) % 6
            pygame.draw.line(surf, inner_hl, top_pts[i], top_pts[j], 2)

        # Cracks
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

        # Rim light
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

        # Grass blades
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
                sx_b, sy_b, _ = project(bx, by, 0)
                sx_t, sy_t, _ = project(bx + sway, by, blade_h)
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
        self._tile_cache_valid = False
        self._request_full_redraw()

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
        new_head = self.next_head_pos()
        if not in_bounds(*new_head) or new_head in self.snake[1:]:
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
        self.move_timer += dt
        self.update_ambient_particles()

        interval = 1.0 / FPS
        if self.state == GameState.PLAYING:
            self.move_lerp = min(1.0, self.move_timer / interval)

        while self.move_timer >= interval and self.state == GameState.PLAYING:
            self.move_timer -= interval
            self.move_lerp = 0
            if not self.move_snake():
                self.state = GameState.GAME_OVER
                self.screen_shake = 15
                self._spawn_eat_particles()
                self._tile_cache_valid = False
                self._request_full_redraw()

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
            sx_t, sy_t, _ = project(corner_x, corner_y, 0)
            sx_b, sy_b, _ = project(corner_x, corner_y, -TILE_HEIGHT)
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

        # --- Flat-shaded top face ---
        face_normal = (0.0, 0.0, 1.0)
        diff = max(0.0, dot3(face_normal, LIGHT_DIR))
        light = (AMBIENT_LIGHT + (1.0 - AMBIENT_LIGHT) * diff) * sun_factor * dist_factor * ao
        final_tri_color = mul_color(tuple(base_top_color), light)
        fog_t = max(0, min(1, (project(cx, cy, 0)[2] - 320) / 500))
        if fog_t > 0:
            final_tri_color = lerp_color(tuple(final_tri_color), FOG_COLOR, fog_t * 0.35)
        tex_variation = 1.0 + 0.06 * noise['tex']
        final_tri_color = mul_color(tuple(final_tri_color), tex_variation)
        for i in range(6):
            j = (i + 1) % 6
            verts = (top_pts[i], top_pts[j], (cx_proj, cy_proj))
            pygame.draw.polygon(surf, final_tri_color, verts)

        # Edge outline
        pygame.draw.polygon(surf, edge_color, top_pts, max(1, int(1 + sun_factor * 0.5)))

        # --- Side faces ---
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

        # Bevel highlights on top edges
        bevel_n = (0.0, 0.0, 1.0)
        bevel_light = AMBIENT_LIGHT + (1.0 - AMBIENT_LIGHT) * max(0.0, dot3(bevel_n, LIGHT_DIR))
        bevel_brightness = bevel_light * sun_factor * ao
        inner_hl = mul_color(TILE_EDGE_HIGHLIGHT, 0.2 * bevel_brightness)
        for i in range(6):
            j = (i + 1) % 6
            pygame.draw.line(surf, inner_hl, top_pts[i], top_pts[j], 2)

        # Surface cracks
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

        # Rim light on top edges (sun-facing)
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

        # Grass blades
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
                sx_b, sy_b, _ = project(bx, by, 0)
                sx_t, sy_t, _ = project(bx + sway, by, blade_h)
                gc = lerp_color((35, 115, 50), (55, 160, 70), 0.3 + (hash((q, r, bi + 300)) % 100) / 200.0)
                pygame.draw.line(surf, gc, (int(sx_b), int(sy_b)), (int(sx_t), int(sy_t)), blade_w)
                if hash((q, r, bi + 400)) % 5 == 0:
                    fc = [(255, 200, 80), (240, 130, 150), (200, 140, 255)][hash((q, r, bi + 500)) % 3]
                    pygame.draw.circle(surf, fc, (int(sx_t), int(sy_t)), max(1, blade_w + 1))

    def draw_shadow(self, surf, cx, cy, z, r, alpha=60):
        sx, sy, _ = project(cx, cy, z)
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

        sx, sy, depth = project(cx, cy, 2)

        # Soft shadow
        self.draw_shadow(surf, cx, cy, 0.3, int(sz * 0.5), 50)

        # Body sprite (from pre-scaled cache)
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

        # Connection segments between body parts
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
                sx_j, sy_j, _ = project(px, py, z)
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

        # Head details
        if idx == 0:
            dx, dy = DIR_VECTORS[self.direction]
            sx_fwd, sy_fwd, _ = project(cx + dx * 6, cy + dy * 6, 2 + TILE_HEIGHT * 0.55)
            es = max(2, int(HEX_SIZE * 0.12))
            dir_x = sx_fwd - sx
            dir_y = sy_fwd - sy
            dir_len = math.hypot(dir_x, dir_y)
            if dir_len > 0:
                perp_x = -dir_y / dir_len
                perp_y = dir_x / dir_len
            else:
                perp_x, perp_y = 0, -1

            # Head glow
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

        # Soft shadow
        pulse = 1.0 + math.sin(time_float * 2.5) * 0.06
        sz = int(HEX_SIZE * 0.36 * pulse * 2)
        self.draw_shadow(surf, cx + math.sin(time_float * 0.5) * 1.2, cy, 0.5, int(sz * 0.6), 40)

        bob = math.sin(time_float * 1.2) * 0.8
        sx_p, sy_p, _ = project(cx + math.sin(time_float * 0.5) * 1.2, cy, 2 + bob)

        # Body (from pre-scaled cache)
        sprite = self._apple_sprites.get(sz)
        if sprite is None:
            sprite = pygame.transform.smoothscale(self.master_apple_sprite, (sz, sz))
            self._apple_sprites[sz] = sprite
        surf.blit(sprite, (int(sx_p - sz // 2), int(sy_p - sz // 2)))

        # Stem
        sx_top, sy_top, _ = project(cx, cy, 2 + bob + TILE_HEIGHT * 1.0 + sz * 0.3)
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

        # Leaf
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
            if in_bounds(q, r):
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

        # Sun
        sun_x = WIDTH // 2 + int(math.sin(time_float * SUN_ANGLE_SPEED) * 200)
        sun_y = int(HEIGHT * 0.15)
        surf.blit(self.sun_disc_surf, (sun_x - 62, sun_y - 62), special_flags=pygame.BLEND_ADD)

        # Water
        self.water_surf.fill((0, 0, 0, 0))
        for wi in range(-25, 25):
            wy = wi * 16
            z_w = -TILE_HEIGHT - 20
            w2 = 1000
            t = (wi + 25) / 50
            sx1, sy1, _ = project(-w2, wy, z_w)
            sx2, sy2, _ = project(w2, wy, z_w)

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

        # Sun reflection on water
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
        surf.blit(self.ground_cache, (shake_x, shake_y))

        # Tile cache: rebuild if invalid or during global effects
        if not self._tile_cache_valid:
            self._build_tile_cache()

        self.draw_cache.fill((0, 0, 0, 0))
        self.draw_cache.blit(self._tile_cache, (0, 0))

        # Build depth buckets for dynamic objects only (apple + snake)
        draw_items = []
        if self.apple:
            ax, ay = hex_to_pixel(*self.apple)
            _, _, depth = project(ax, ay, 0.5)
            draw_items.append((depth, 'apple'))

        for idx, (q, r) in enumerate(self.snake):
            cx, cy = hex_to_pixel(q, r)
            _, _, depth = project(cx, cy, 2)
            draw_items.append((depth, 'snake', idx, q, r))

        draw_list = self._build_depth_buckets(draw_items)

        for item in draw_list:
            if item[1] == 'apple':
                self.draw_apple(self.draw_cache, time_float)
            elif item[1] == 'snake':
                _, _, idx, q, r = item
                self.draw_snake_segment(self.draw_cache, idx, q, r, time_float)

        surf.blit(self.draw_cache, (shake_x, shake_y))

        # Post-processing (bloom + god rays + fog)
        if self.gl_renderer.available:
            scene = surf.copy()
            result = self.gl_renderer.post_process(scene, time_float, self.fog_surf)
            if result:
                surf.blit(result, (0, 0))
        else:
            # Software bloom
            bloom_small = pygame.transform.smoothscale(surf, (WIDTH // 4, HEIGHT // 4))
            bloom_blur = pygame.transform.smoothscale(bloom_small, (WIDTH, HEIGHT))
            bloom_blur.set_alpha(28)
            surf.blit(bloom_blur, (0, 0), special_flags=pygame.BLEND_ADD)

            # Software god rays
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

            # Software fog
            surf.blit(self.fog_surf, (0, 0), special_flags=pygame.BLEND_ADD)

        # Apple glow (always software, on top of post-processing)
        if self.apple and self.state != GameState.GAME_OVER:
            px, py = hex_to_pixel(*self.apple)
            sx, sy, _ = project(px, py, 0.5)
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

        # Particles (always software)
        self.particles.sort_by_z()
        for p in self.particles:
            p.draw(surf, self)

        self.draw_ui(surf, shake_x, shake_y)

        if self.state == GameState.PAUSED:
            self.draw_pause_overlay(surf)

        if self.state == GameState.GAME_OVER:
            self.draw_game_over(surf)

        # Vignette (always software, on top of everything)
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

    def draw_ui(self, surf, shake_x, shake_y):
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

        score_text = f"{self.score}"
        text_surf = self.font_score.render(score_text, True, TEXT_WHITE)
        score_glow = self.font_score.render(score_text, True, (40, 180, 120, 60))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            surf.blit(score_glow, (36 + shake_x + dx, 26 + shake_y + dy))
        surf.blit(text_surf, (36 + shake_x, 26 + shake_y))

        pygame.draw.circle(surf, TEXT_GLOW, (32 + shake_x, 36 + shake_y), 3)
        pygame.draw.circle(surf, (100, 255, 180, 100), (32 + shake_x, 36 + shake_y), 5, 1)

        if self.high_score > 0:
            hs_text = f"BEST: {self.high_score}"
            hs_surf = self.font_micro.render(hs_text, True, TEXT_DIM)
            surf.blit(hs_surf, (36 + shake_x, 54 + shake_y))

    def draw_pause_overlay(self, surf):
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

        txt = self.font_large.render("PAUSED", True, TEXT_YELLOW)
        glow = self.font_large.render("PAUSED", True, (255, 200, 80, 60))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            surf.blit(glow, (WIDTH // 2 - txt.get_width() // 2 + dx, HEIGHT // 2 - 55 + dy))
        r = txt.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 55))
        surf.blit(txt, r)

        hint = self.font_small.render("Press SPACE to resume", True, TEXT_WHITE)
        hr = hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 25))
        surf.blit(hint, hr)

        hint2 = self.font_micro.render("ESC to quit", True, TEXT_DIM)
        h2r = hint2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 55))
        surf.blit(hint2, h2r)

    def draw_game_over(self, surf):
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

        title = self.font_large.render("GAME OVER", True, (255, 80, 80))
        title_glow = self.font_large.render("GAME OVER", True, (200, 40, 40, 80))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)]:
            surf.blit(title_glow, (WIDTH // 2 - title.get_width() // 2 + dx, py + 30 + dy))
        tr = title.get_rect(center=(WIDTH // 2, py + 30))
        surf.blit(title, tr)

        score = self.font_med.render(f"Score: {self.score}", True, TEXT_WHITE)
        sr = score.get_rect(center=(WIDTH // 2, py + 90))
        surf.blit(score, sr)

        if self.score >= self.high_score and self.score > 0:
            best = self.font_small.render("NEW BEST!", True, TEXT_YELLOW)
            bg = self.font_small.render("NEW BEST!", True, (180, 150, 50, 60))
            for dx, dy in [(-1, 0), (1, 0)]:
                surf.blit(bg, (WIDTH // 2 - best.get_width() // 2 + dx, py + 125 + dy))
            br = best.get_rect(center=(WIDTH // 2, py + 125))
            surf.blit(best, br)

        hint = self.font_small.render("Press R or ENTER to restart", True, TEXT_WHITE)
        hr = hint.get_rect(center=(WIDTH // 2, py + 180))
        surf.blit(hint, hr)

        hint2 = self.font_micro.render("ESC to quit", True, TEXT_DIM)
        h2r = hint2.get_rect(center=(WIDTH // 2, py + 215))
        surf.blit(hint2, h2r)

    def draw_start_screen(self):
        surf = self.screen
        surf.blit(self.bg_surf, (0, 0))
        surf.blit(self.star_surf, (0, 0))

        surf.blit(self._start_sun_surf, (WIDTH // 2 - 42, int(HEIGHT * 0.12 - 42)))

        title = self.font_large.render("SNAKE V2", True, TEXT_WHITE)
        gl = self.font_large.render("SNAKE V2", True, TEXT_GLOW)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0)]:
            surf.blit(gl, (WIDTH // 2 - title.get_width() // 2 + dx, HEIGHT // 2 - 85 + dy))
        tr = title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 85))
        surf.blit(title, tr)

        subtitle = self.font_small.render("3D Hex Grid - Enhanced Edition", True, TEXT_DIM)
        sr = subtitle.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
        surf.blit(subtitle, sr)

        instructions = [
            ("A / LEFT ARROW", "Turn left"),
            ("D / RIGHT ARROW", "Turn right"),
            ("SPACE", "Pause"),
            ("ESC", "Quit"),
        ]
        for i, (key, action) in enumerate(instructions):
            key_surf = self.font_micro.render(key, True, TEXT_GLOW)
            act_surf = self.font_micro.render(action, True, TEXT_DIM)
            kx = WIDTH // 2 - 120
            ax = WIDTH // 2 + 20
            iy = HEIGHT // 2 + 5 + i * 25
            surf.blit(key_surf, (kx, iy))
            surf.blit(act_surf, (ax, iy))

        hint = self.font_small.render("Press any key to start", True, TEXT_YELLOW)
        hr = hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 160))
        pulse = int(abs(math.sin(pygame.time.get_ticks() * 0.003)) * 120)
        hint.set_alpha(130 + pulse)
        surf.blit(hint, hr)

        pygame.display.flip()

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
            self.draw_start_screen()
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
