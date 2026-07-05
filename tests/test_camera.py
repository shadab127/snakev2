"""Unit tests for Camera class."""
import math

from config import WIDTH, HEIGHT, HEX_SIZE, CAM_3D_HEIGHT
from camera import Camera
from utils import hex_to_pixel


class TestCameraProjection:
    def test_project_origin_on_screen(self):
        """Projecting (0,0,0) after snap_to should land on screen."""
        cam = Camera()
        hx, hy = hex_to_pixel(0, 0)
        cam.snap_to(hx, hy, 0)
        sx, sy, depth = cam.project(0, 0, 0)
        assert 0 <= sx <= WIDTH
        assert 0 <= sy <= HEIGHT
        assert depth > 0

    def test_project_origin_deterministic(self):
        cam = Camera()
        hx, hy = hex_to_pixel(0, 0)
        cam.snap_to(hx, hy, 0)
        r1 = cam.project(100, 50, 10)
        r2 = cam.project(100, 50, 10)
        for a, b in zip(r1, r2):
            assert abs(a - b) < 1e-9

    def test_project_negative_z_still_visible(self):
        cam = Camera()
        hx, hy = hex_to_pixel(0, 0)
        cam.snap_to(hx, hy, 0)
        sx, sy, depth = cam.project(0, 0, -20)
        # Depth should still be positive
        assert depth > 0

    def test_project_out_of_bounds(self):
        cam = Camera()
        sx, sy, depth = cam.project(0, 0, 0)
        # Before snap_to, vp_matrix is identity, so depth can be 0 or unusual

    def test_project_z_affects_depth(self):
        cam = Camera()
        hx, hy = hex_to_pixel(0, 0)
        cam.snap_to(hx, hy, 0)
        _, _, d0 = cam.project(0, 0, 0)
        _, _, d1 = cam.project(0, 0, 20)
        # Higher z should be closer (smaller depth value)
        assert d1 < d0

    def test_snap_to_deterministic(self):
        cam1 = Camera()
        cam2 = Camera()
        hx, hy = hex_to_pixel(3, -2)
        cam1.snap_to(hx, hy, 1)
        cam2.snap_to(hx, hy, 1)
        p1 = cam1.project(10, 10, 5)
        p2 = cam2.project(10, 10, 5)
        for a, b in zip(p1, p2):
            assert abs(a - b) < 1e-9


class TestCameraFollow:
    def test_follow_snake_no_crash(self):
        cam = Camera()
        hx, hy = hex_to_pixel(0, 0)
        cam.snap_to(hx, hy, 0)
        cam.follow_snake(hx, hy, 0, dt=0.016)
        sx, sy, depth = cam.project(0, 0, 0)
        assert depth > 0

    def test_follow_snake_moves_camera(self):
        cam = Camera()
        hx, hy = hex_to_pixel(0, 0)
        cam.snap_to(hx, hy, 0)
        eye_before = cam.eye
        # Move snake far away
        hx2, hy2 = hex_to_pixel(5, 3)
        cam.follow_snake(hx2, hy2, 2, dt=0.016)
        # Camera should have moved
        assert cam.eye != eye_before

    def test_follow_snake_wrap_detection(self):
        cam = Camera()
        hx, hy = hex_to_pixel(0, 0)
        cam.snap_to(hx, hy, 0)
        eye_before = cam.eye
        # Large jump simulates wrap
        hx2, hy2 = hex_to_pixel(100, 0)
        cam.follow_snake(hx2, hy2, 0, dt=0.016)
        # Should snap (not spring) when far away
        eye_after = cam.eye
        assert eye_after != eye_before


class TestCameraShake:
    def test_shake_sets_timer(self):
        cam = Camera()
        cam.shake(5.0, 0.3)
        assert cam._shake_intensity == 5.0
        assert cam._shake_duration == 0.3
        assert cam._shake_timer == 0.3

    def test_shake_decays(self):
        cam = Camera()
        cam.shake(5.0, 0.3)
        hx, hy = hex_to_pixel(0, 0)
        cam.follow_snake(hx, hy, 0, dt=0.1)
        assert cam._shake_timer < 0.3
        assert cam._shake_timer > 0.0

    def test_shake_expires(self):
        cam = Camera()
        cam.shake(5.0, 0.1)
        hx, hy = hex_to_pixel(0, 0)
        for _ in range(10):
            cam.follow_snake(hx, hy, 0, dt=0.1)
        assert cam._shake_timer == 0.0


class TestCameraEvents:
    def test_eat_punch(self):
        cam = Camera()
        cam.eat_punch()
        assert cam._eat_punch_timer > 0

    def test_eat_punch_decays(self):
        cam = Camera()
        cam.eat_punch()
        hx, hy = hex_to_pixel(0, 0)
        cam.follow_snake(hx, hy, 0, dt=0.1)
        assert cam._eat_punch_timer < 0.2

    def test_death_pullout(self):
        cam = Camera()
        cam.death_pullout()
        assert cam._death_pull_timer > 0

    def test_on_turn_banking(self):
        cam = Camera()
        cam.on_turn(1)
        assert cam.roll_target > 0
        cam.on_turn(-1)
        assert cam.roll_target < 0


class TestCameraMatrices:
    def test_identity_matrix(self):
        from camera import Matrix4
        m = Matrix4.identity()
        res = Matrix4.transform(m, 1, 2, 3, 1)
        assert res == (1, 2, 3, 1)

    def test_matrix_multiplication(self):
        from camera import Matrix4
        a = Matrix4.identity()
        b = Matrix4.identity()
        c = Matrix4.multiply(a, b)
        assert c == Matrix4.identity()

    def test_perspective_fov(self):
        from camera import Matrix4
        m = Matrix4.perspective(math.radians(45), 16 / 9, 0.1, 100)
        assert len(m) == 16
