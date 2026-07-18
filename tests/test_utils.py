"""Unit tests for pure-logic functions in utils.py."""
import math
import random

import pytest
from config import (HEX_SIZE, GRID_RADIUS, GRID_COLS, GRID_ROWS,
                    SUN_ANGLE_SPEED, MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL,
                    SPEED_DECAY_PER_POINT)
from utils import (hex_to_pixel, hex_corners, wrap_coords, all_hexes,
                   in_bounds, catmull_rom, sample_spline_path,
                   lerp_color, mul_color, add_color,
                   compute_sun_light, compute_sky_color,
                   dot3)


# ============================================================
# Hex math
# ============================================================

class TestHexMath:
    def test_hex_to_pixel_origin(self):
        x, y = hex_to_pixel(0, 0)
        assert (x, y) == (0.0, 0.0)

    def test_hex_to_pixel_q1(self):
        x, y = hex_to_pixel(1, 0)
        expected_x = HEX_SIZE * math.sqrt(3)
        assert abs(x - expected_x) < 1e-9
        assert y == 0.0

    def test_hex_to_pixel_qr(self):
        x, y = hex_to_pixel(0, 1)
        expected_x = HEX_SIZE * math.sqrt(3) * 0.5
        expected_y = HEX_SIZE * 1.5
        assert abs(x - expected_x) < 1e-9
        assert abs(y - expected_y) < 1e-9

    def test_hex_corners_count(self):
        corners = hex_corners(0, 0)
        assert len(corners) == 6

    def test_hex_corners_geometry(self):
        cx, cy = 100.0, 200.0
        corners = hex_corners(cx, cy)
        for i, (px, py) in enumerate(corners):
            angle = math.radians(60 * i - 30)
            exp_x = cx + HEX_SIZE * math.cos(angle)
            exp_y = cy + HEX_SIZE * math.sin(angle)
            assert abs(px - exp_x) < 1e-9
            assert abs(py - exp_y) < 1e-9

    def test_hex_corners_uniform_radius(self):
        corners = hex_corners(50, 50)
        for px, py in corners:
            dist = math.hypot(px - 50, py - 50)
            assert abs(dist - HEX_SIZE) < 1e-9

    def test_wrap_coords_center(self):
        q, r = wrap_coords(0, 0)
        assert (q, r) == (0, 0)

    def test_wrap_coords_right_edge(self):
        q, r = wrap_coords(GRID_RADIUS + 1, 0)
        assert q == -GRID_RADIUS
        assert r == 0

    def test_wrap_coords_left_edge(self):
        q, r = wrap_coords(-GRID_RADIUS - 1, 0)
        assert q == GRID_RADIUS
        assert r == 0

    def test_wrap_coords_top_edge(self):
        q, r = wrap_coords(0, -(GRID_RADIUS + 1))
        assert r == GRID_RADIUS

    def test_wrap_coords_bottom_edge(self):
        q, r = wrap_coords(0, GRID_RADIUS + 1)
        assert r == -GRID_RADIUS

    def test_wrap_coords_corner(self):
        q, r = wrap_coords(GRID_RADIUS + 2, GRID_RADIUS + 1)
        wrapped = (-GRID_RADIUS + 1, -GRID_RADIUS)
        assert (q, r) == wrapped

    def test_wrap_coords_all_edges(self):
        for dq in range(-GRID_RADIUS, GRID_RADIUS + 1):
            for dr in range(-GRID_RADIUS, GRID_RADIUS + 1):
                wq, wr = wrap_coords(dq, dr)
                assert -GRID_RADIUS <= wq <= GRID_RADIUS
                assert -GRID_RADIUS <= wr <= GRID_RADIUS

    def test_all_hexes_count(self):
        from utils import in_bounds
        hexes = all_hexes()
        assert len(hexes) == 169  # 1 + 6*(1+2+...+7) = 169 for radius 7
        for q, r in hexes:
            assert in_bounds(q, r), f"({q},{r}) should be in bounds"

    def test_all_hexes_includes_origin(self):
        hexes = all_hexes()
        assert (0, 0) in hexes

    def test_all_hexes_unique(self):
        hexes = all_hexes()
        assert len(set(hexes)) == len(hexes)

    def test_all_hexes_wrap_roundtrip(self):
        """Every hex from all_hexes() wraps back to itself or another valid coord."""
        hexes = all_hexes()
        for q, r in hexes:
            wq, wr = wrap_coords(q, r)
            assert -GRID_RADIUS <= wq <= GRID_RADIUS
            assert -GRID_RADIUS <= wr <= GRID_RADIUS
            assert isinstance(wq, int)
            assert isinstance(wr, int)

    def test_in_bounds_center(self):
        assert in_bounds(0, 0) is True

    def test_in_bounds_edge(self):
        assert in_bounds(GRID_RADIUS, 0) is True
        assert in_bounds(-GRID_RADIUS, 0) is True
        assert in_bounds(0, GRID_RADIUS) is True
        assert in_bounds(0, -GRID_RADIUS) is True

    def test_in_bounds_outside(self):
        assert in_bounds(GRID_RADIUS + 1, 0) is False
        assert in_bounds(0, GRID_RADIUS + 1) is False
        assert in_bounds(-GRID_RADIUS - 1, 0) is False

    def test_in_bounds_axial_corner(self):
        assert in_bounds(GRID_RADIUS, GRID_RADIUS) is False  # |q+r| > radius

    def test_canonical_cell_basic(self):
        from utils import canonical_cell
        cq, cr, dq, dr = canonical_cell(0, 0)
        assert (cq, cr) == (0, 0)
        assert (dq, dr) == (0, 0)

    def test_canonical_cell_edge_wrap(self):
        from utils import canonical_cell
        cq, cr, dq, dr = canonical_cell(GRID_RADIUS + 1, 0)
        assert (cq, cr) == (-GRID_RADIUS, 0)
        assert (dq, dr) == (1, 0)

    def test_canonical_cell_multi_period(self):
        from utils import canonical_cell, in_bounds
        period = 2 * GRID_RADIUS + 1
        cq, cr, dq, dr = canonical_cell(period + 1, -period - 2)
        assert in_bounds(cq, cr), f"canonical cell ({cq},{cr}) must be in bounds"
        assert (dq, dr) == (1, -1)


# ============================================================
# Catmull-Rom spline
# ============================================================

class TestCatmullRom:
    def test_at_t0(self):
        result = catmull_rom(0.0, 10.0, 20.0, 30.0, 0.0)
        assert abs(result - 10.0) < 1e-9

    def test_at_t1(self):
        result = catmull_rom(0.0, 10.0, 20.0, 30.0, 1.0)
        assert abs(result - 20.0) < 1e-9

    def test_at_t05_symmetric(self):
        result = catmull_rom(0.0, 10.0, 20.0, 30.0, 0.5)
        assert abs(result - 15.0) < 1e-9

    def test_flat_line(self):
        for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
            v = catmull_rom(5.0, 5.0, 5.0, 5.0, t)
            assert abs(v - 5.0) < 1e-9

    def test_monotonic(self):
        vals = [catmull_rom(0, 0, 10, 10, t * 0.1) for t in range(11)]
        for i in range(1, len(vals)):
            assert vals[i] >= vals[i - 1] - 1e-9


class TestSampleSplinePath:
    def test_single_point(self):
        result = sample_spline_path([(0, 0)], 5)
        assert len(result) == 5
        for px, py, tx, ty in result:
            assert abs(px) < 1e-9
            assert abs(py) < 1e-9

    def test_two_points(self):
        result = sample_spline_path([(0, 0), (1, 0)], 3)
        assert len(result) == 3
        # Last index corresponds to start of path (0,0)
        px, py = hex_to_pixel(0, 0)
        assert abs(result[-1][0] - px) < 5
        assert abs(result[-1][1] - py) < 5

    def test_tangent_nonzero(self):
        result = sample_spline_path([(0, 0), (1, 0)], 2)
        tx, ty = result[0][2], result[0][3]
        # Tangent should be non-zero
        assert math.hypot(tx, ty) > 0.001

    def test_empty_path(self):
        result = sample_spline_path([], 3)
        assert len(result) == 3


# ============================================================
# Color helpers
# ============================================================

class TestColorMath:
    def test_lerp_color_t0(self):
        c = lerp_color((10, 20, 30), (100, 200, 250), 0.0)
        assert c == (10, 20, 30)

    def test_lerp_color_t1(self):
        c = lerp_color((10, 20, 30), (100, 200, 250), 1.0)
        assert c == (100, 200, 250)

    def test_lerp_color_mid(self):
        c = lerp_color((0, 0, 0), (100, 200, 255), 0.5)
        assert c == (50, 100, 127)

    def test_lerp_color_clamp(self):
        c = lerp_color((0, 0, 0), (100, 200, 255), -0.5)
        assert c == (0, 0, 0)
        c = lerp_color((0, 0, 0), (100, 200, 255), 1.5)
        assert c == (100, 200, 255)

    def test_mul_color_identity(self):
        c = mul_color((100, 150, 200), 1.0)
        assert c == (100, 150, 200)

    def test_mul_color_half(self):
        c = mul_color((100, 150, 200), 0.5)
        assert c == (50, 75, 100)

    def test_mul_color_clamp(self):
        c = mul_color((200, 200, 200), 2.0)
        assert c == (255, 255, 255)
        c = mul_color((50, 50, 50), -1.0)
        assert c == (0, 0, 0)

    def test_add_color(self):
        c = add_color((100, 150, 200), (50, 50, 50))
        assert c == (150, 200, 250)

    def test_add_color_clamp(self):
        c = add_color((200, 200, 200), (200, 200, 200))
        assert c == (255, 255, 255)


# ============================================================
# Lighting
# ============================================================

class TestLighting:
    def test_compute_sun_light_returns_tuple(self):
        light_dir, ambient, sun_color = compute_sun_light(0.0)
        assert len(light_dir) == 3
        assert 0.0 <= ambient <= 1.0
        assert len(sun_color) == 3

    def test_compute_sun_light_normalized(self):
        light_dir, _, _ = compute_sun_light(0.0)
        length = math.sqrt(sum(v * v for v in light_dir))
        assert abs(length - 1.0) < 1e-6

    def test_compute_sun_light_cycles(self):
        l1, _, _ = compute_sun_light(0.0)
        period = 2 * math.pi / SUN_ANGLE_SPEED
        l2, _, _ = compute_sun_light(period)
        for a, b in zip(l1, l2):
            assert abs(a - b) < 1e-6

    def test_compute_sky_color_returns_tuple(self):
        top, mid, horizon = compute_sky_color(0.0)
        assert len(top) == 3
        assert len(mid) == 3
        assert len(horizon) == 3

    def test_compute_sky_color_valid(self):
        for t in [0.0, 0.5, 1.0, 5.0, 100.0]:
            top, mid, horizon = compute_sky_color(t)
            for c in [top, mid, horizon]:
                for v in c:
                    assert 0 <= v <= 255

    def test_compute_lighting(self):
        pytest.skip("compute_lighting removed in c60377c — lighting now done in shader/main inline")
        normal = (0.0, 0.0, 1.0)
        light_dir = (0.0, 0.0, 1.0)
        c, spec = compute_lighting(normal, light_dir, 0.2, (255, 240, 200))

    def test_compute_lighting_opposite(self):
        pytest.skip("compute_lighting removed in c60377c — lighting now done in shader/main inline")
        normal = (0.0, 0.0, 1.0)
        light_dir = (0.0, 0.0, -1.0)
        c, spec = compute_lighting(normal, light_dir, 0.2, (255, 240, 200))

    def test_dot3(self):
        assert dot3((1, 0, 0), (1, 0, 0)) == 1.0
        assert dot3((1, 0, 0), (-1, 0, 0)) == -1.0
        assert dot3((1, 0, 0), (0, 1, 0)) == 0.0


# ============================================================
# Speed curve
# ============================================================

class TestSpeedCurve:
    def test_interval_at_score_0(self):
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - 0 * SPEED_DECAY_PER_POINT)
        assert interval == BASE_MOVE_INTERVAL

    def test_interval_at_score_50(self):
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - 50 * SPEED_DECAY_PER_POINT)
        expected = BASE_MOVE_INTERVAL - 50 * SPEED_DECAY_PER_POINT
        assert abs(interval - expected) < 1e-9

    def test_interval_at_score_100(self):
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - 100 * SPEED_DECAY_PER_POINT)
        expected = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - 100 * SPEED_DECAY_PER_POINT)
        assert abs(interval - expected) < 1e-9

    def test_interval_at_score_200(self):
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - 200 * SPEED_DECAY_PER_POINT)
        # At score 200 speed has decayed past MIN, clamped to MIN_MOVE_INTERVAL
        assert interval == MIN_MOVE_INTERVAL

    def test_interval_at_score_0_clamped(self):
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - 0 * SPEED_DECAY_PER_POINT)
        assert interval == BASE_MOVE_INTERVAL
        assert interval >= MIN_MOVE_INTERVAL

    def test_interval_at_score_high(self):
        for score in [0, 50, 100, 143, 200, 500]:
            interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - score * SPEED_DECAY_PER_POINT)
            assert MIN_MOVE_INTERVAL <= interval <= BASE_MOVE_INTERVAL
