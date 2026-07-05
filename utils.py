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


def hex_corner_height(q, r, height_map, neighbor_cache=None):
    if neighbor_cache is None:
        neighbor_cache = DIR_VECTORS
    h_self = height_map.get((q, r), 0)
    count = 1
    total = h_self
    for dq, dr in neighbor_cache:
        nk = (q + dq, r + dr)
        if nk in height_map:
            total += height_map[nk]
            count += 1
    return total / count


def hex_inner_corners(cx, cy, inset):
    inner = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        inner.append((
            cx + (HEX_SIZE - inset) * math.cos(angle),
            cy + (HEX_SIZE - inset) * math.sin(angle),
        ))
    return inner


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


_all_hexes_cache = None

def all_hexes():
    global _all_hexes_cache
    if _all_hexes_cache is None:
        cols = GRID_RADIUS * 2 + 1
        rows = GRID_RADIUS * 2 + 1
        _all_hexes_cache = []
        for row in range(rows):
            for col in range(cols):
                q = col - (row + (row & 1)) // 2 - GRID_RADIUS
                r = row - GRID_RADIUS
                _all_hexes_cache.append((q, r))
    return _all_hexes_cache


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
    noise = tile_noise(q, r)
    height_var = abs(noise.get('detail', 0)) * 0.15
    base_ao = 1.0 - 0.04 * neighbor_count - 0.12 * edge_dist - height_var * 0.2
    return max(0.45, min(1.0, base_ao))


def compute_sun_light(time_float):
    angle = time_float * SUN_ANGLE_SPEED
    day_cycle = math.sin(angle)

    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    lx = LIGHT_DIR[0] * cos_a - LIGHT_DIR[1] * sin_a
    ly = LIGHT_DIR[0] * sin_a + LIGHT_DIR[1] * cos_a
    lz = LIGHT_DIR[2]
    ll = math.sqrt(lx * lx + ly * ly + lz * lz)
    light_dir = (lx / ll, ly / ll, lz / ll)

    t = day_cycle * 0.5 + 0.5
    ambient = SUN_AMBIENT_MIN + (SUN_AMBIENT_MAX - SUN_AMBIENT_MIN) * t

    if day_cycle < -0.3:
        dusk_t = (day_cycle + 0.3) / 0.7
        sun_color = lerp_color(SUN_COLOR_NIGHT, SUN_COLOR_DUSK, max(0.0, min(1.0, dusk_t + 1.0)))
    elif day_cycle < 0.3:
        dusk_t = (day_cycle + 0.3) / 0.6
        sun_color = lerp_color(SUN_COLOR_DUSK, SUN_COLOR_DAY, dusk_t)
    else:
        sun_color = SUN_COLOR_DAY

    return light_dir, ambient, sun_color


def compute_sky_color(time_float):
    angle = time_float * SUN_ANGLE_SPEED
    day_cycle = math.sin(angle)
    t = day_cycle * 0.5 + 0.5

    top = lerp_color(SKY_NIGHT_TOP, SKY_TOP, t)
    mid = lerp_color(SKY_NIGHT_MID, SKY_MID, t)
    horizon = lerp_color(SKY_NIGHT_HORIZON, SKY_HORIZON, t)

    if day_cycle < 0.3 and day_cycle > -0.3:
        warm = SUN_COLOR_DUSK
        warm_t = 1.0 - abs(day_cycle) / 0.3
        top = lerp_color(top, (warm[0]//4, warm[1]//6, warm[2]//8), warm_t * 0.4)
        mid = lerp_color(mid, (warm[0]//2, warm[1]//3, warm[2]//4), warm_t * 0.4)
        horizon = lerp_color(horizon, warm, warm_t * 0.5)

    return top, mid, horizon


def dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def rgb_to_hsv(r, g, b):
    rn, gn, bn = r / 255.0, g / 255.0, b / 255.0
    mx = max(rn, gn, bn)
    mn = min(rn, gn, bn)
    d = mx - mn
    h = 0.0
    s = 0.0 if mx == 0 else d / mx
    v = mx
    if d != 0:
        if mx == rn:
            h = 60.0 * (((gn - bn) / d) % 6)
        elif mx == gn:
            h = 60.0 * (((bn - rn) / d) + 2)
        else:
            h = 60.0 * (((rn - gn) / d) + 4)
    return (h / 360.0, s, v)


def hsv_to_rgb(h, s, v):
    hi = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p = v * (1 - s)
    q = v * (1 - f * s)
    tt = v * (1 - (1 - f) * s)
    if hi == 0: rn, gn, bn = v, tt, p
    elif hi == 1: rn, gn, bn = q, v, p
    elif hi == 2: rn, gn, bn = p, v, tt
    elif hi == 3: rn, gn, bn = p, q, v
    elif hi == 4: rn, gn, bn = tt, p, v
    else: rn, gn, bn = v, p, q
    return (int(rn * 255), int(gn * 255), int(bn * 255))


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
            'hue': perlin_noise(q * 1.7 + r * 2.3 + 50, r * 1.7 - q * 2.3 + 50, 1.5, 2, 0.5),
            'brightness': perlin_noise(q * 2.1 + r * 1.3 + 200, r * 2.1 - q * 1.3 + 200, 1.8, 2, 0.5),
            'saturation': perlin_noise(q * 1.9 + r * 2.7 + 300, r * 1.9 - q * 2.7 + 300, 2.0, 2, 0.5),
            'height': perlin_noise(q * 0.8 + r * 1.2 + 400, r * 0.8 - q * 1.2 + 400, 1.2, 3, 0.5),
        }
    return _tile_noise_cache[(q, r)]


def sample_spline_path(path_points, num_segments):
    """Sample evenly-spaced positions along a Catmull-Rom curve
    traced through path_points (list of (q,r) hex coords, head first).

    Returns list of (px, py, tx, ty) where (tx,ty) is the unit tangent.
    """
    if len(path_points) < 2:
        if not path_points:
            return [(0.0, 0.0, 0.0, 0.0)] * max(1, num_segments)
        px, py = hex_to_pixel(*path_points[0])
        return [(px, py, 0.0, 0.0)] * num_segments

    pixels = [hex_to_pixel(q, r) for q, r in path_points]
    n = len(pixels)

    if num_segments <= 1:
        px, py = pixels[0]
        tx = ty = 0.0
        if n >= 2:
            tx = pixels[1][0] - px
            ty = pixels[1][1] - py
            tl = math.hypot(tx, ty)
            if tl > 0.001:
                tx /= tl; ty /= tl
        return [(px, py, tx, ty)]

    segments = []
    lengths = []
    total_len = 0.0
    N_SAMP = 10

    for i in range(n - 1):
        p0 = pixels[max(0, i - 1)]
        p1 = pixels[i]
        p2 = pixels[i + 1]
        p3 = pixels[min(n - 1, i + 2)]
        seg_len = 0.0
        px, py = p1
        for s in range(1, N_SAMP + 1):
            t = s / N_SAMP
            nx = catmull_rom(p0[0], p1[0], p2[0], p3[0], t)
            ny = catmull_rom(p0[1], p1[1], p2[1], p3[1], t)
            seg_len += math.hypot(nx - px, ny - py)
            px, py = nx, ny
        segments.append((p0, p1, p2, p3))
        lengths.append(seg_len)
        total_len += seg_len

    if total_len < 0.001:
        px, py = pixels[0]
        return [(px, py, 0.0, 0.0)] * num_segments

    result = []
    for si in range(num_segments):
        target = total_len * (1.0 - si / max(1, num_segments - 1))
        acc = 0.0
        px, py, tx, ty = pixels[-1][0], pixels[-1][1], 0.0, 0.0
        for i, seg_len in enumerate(lengths):
            if acc + seg_len >= target - 1e-10 or i == len(lengths) - 1:
                lt = max(0.0, min(1.0, (target - acc) / max(0.001, seg_len)))
                p0, p1, p2, p3 = segments[i]
                px = catmull_rom(p0[0], p1[0], p2[0], p3[0], lt)
                py = catmull_rom(p0[1], p1[1], p2[1], p3[1], lt)
                t2 = lt * lt
                tx = 0.5 * ((-p0[0] + p2[0])
                            + 2.0*(2.0*p0[0] - 5.0*p1[0] + 4.0*p2[0] - p3[0])*lt
                            + 3.0*(-p0[0] + 3.0*p1[0] - 3.0*p2[0] + p3[0])*t2)
                ty = 0.5 * ((-p0[1] + p2[1])
                            + 2.0*(2.0*p0[1] - 5.0*p1[1] + 4.0*p2[1] - p3[1])*lt
                            + 3.0*(-p0[1] + 3.0*p1[1] - 3.0*p2[1] + p3[1])*t2)
                tl = math.hypot(tx, ty)
                if tl > 0.001:
                    tx /= tl; ty /= tl
                break
            acc += seg_len
        result.append((px, py, tx, ty))
    return result


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
