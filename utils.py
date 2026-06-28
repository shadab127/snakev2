import math
import random
import pygame
from config import *


NOISE_SEED = random.randint(0, 10000)
_rng = random.Random(NOISE_SEED)
_PERM = list(range(256))
_rng.shuffle(_PERM)
_PERM += _PERM
_perlin_cache = {}

_tile_noise_cache = {}


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


def wrap_coords(q, r):
    wq = (q + GRID_RADIUS) % GRID_COLS - GRID_RADIUS
    wr = (r + GRID_RADIUS) % GRID_ROWS - GRID_RADIUS
    return wq, wr


def all_hexes():
    cols = GRID_RADIUS * 2 + 1
    rows = GRID_RADIUS * 2 + 1
    for row in range(rows):
        for col in range(cols):
            q = col - (row + (row & 1)) // 2 - GRID_RADIUS
            r = row - GRID_RADIUS
            yield (q, r)


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
