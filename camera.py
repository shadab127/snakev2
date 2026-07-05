import math
import random
from config import *


class Matrix4:
    """4x4 column-major matrix utilities for the MVP pipeline."""

    @staticmethod
    def identity():
        return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]

    @staticmethod
    def multiply(a, b):
        res = [0]*16
        for i in range(4):
            for j in range(4):
                res[j*4+i] = sum(a[k*4+i] * b[j*4+k] for k in range(4))
        return res

    @staticmethod
    def perspective(fov_y, aspect, near, far):
        f = 1.0 / math.tan(fov_y / 2)
        d = near - far
        return [
            f/aspect, 0, 0, 0,
            0, f, 0, 0,
            0, 0, (far+near)/d, -1,
            0, 0, 2*far*near/d, 0
        ]

    @staticmethod
    def look_at(eye, target, up):
        f = (target[0]-eye[0], target[1]-eye[1], target[2]-eye[2])
        fl = math.hypot(*f)
        if fl < 1e-10:
            return Matrix4.identity()
        f = (f[0]/fl, f[1]/fl, f[2]/fl)

        s = (f[1]*up[2] - f[2]*up[1],
             f[2]*up[0] - f[0]*up[2],
             f[0]*up[1] - f[1]*up[0])
        sl = math.hypot(*s)
        if sl < 1e-10:
            return Matrix4.identity()
        s = (s[0]/sl, s[1]/sl, s[2]/sl)

        u = (s[1]*f[2] - s[2]*f[1],
             s[2]*f[0] - s[0]*f[2],
             s[0]*f[1] - s[1]*f[0])

        return [
            s[0], u[0], -f[0], 0,
            s[1], u[1], -f[1], 0,
            s[2], u[2], -f[2], 0,
            -s[0]*eye[0]-s[1]*eye[1]-s[2]*eye[2],
            -u[0]*eye[0]-u[1]*eye[1]-u[2]*eye[2],
            f[0]*eye[0]+f[1]*eye[1]+f[2]*eye[2],
            1
        ]

    @staticmethod
    def transform(m, x, y, z, w=1.0):
        return (
            m[0]*x + m[4]*y + m[8]*z  + m[12]*w,
            m[1]*x + m[5]*y + m[9]*z  + m[13]*w,
            m[2]*x + m[6]*y + m[10]*z + m[14]*w,
            m[3]*x + m[7]*y + m[11]*z + m[15]*w
        )


class Camera:
    def __init__(self):
        self.eye = (0.0, 0.0, CAM_3D_HEIGHT)
        self.target = (0.0, 0.0, 0.0)
        self.up = (0.0, 0.0, 1.0)
        self.view_matrix = Matrix4.identity()
        self.proj_matrix = Matrix4.identity()
        self.vp_matrix = Matrix4.identity()
        self.width = WIDTH
        self.height = HEIGHT

        # Banking
        self.roll = 0.0
        self.roll_target = 0.0

        # Smooth yaw interpolation
        self._yaw = 0.0
        self._yaw_target = 0.0

        # Shake
        self._shake_intensity = 0.0
        self._shake_duration = 0.0
        self._shake_timer = 0.0

        # Event reactions
        self._eat_punch_timer = 0.0
        self._death_pull_timer = 0.0

    def _build_matrices(self):
        aspect = self.width / self.height
        self.view_matrix = Matrix4.look_at(self.eye, self.target, self.up)
        self.proj_matrix = Matrix4.perspective(CAM_3D_FOV_RAD, aspect, CAM_3D_NEAR, CAM_3D_FAR)
        self.vp_matrix = Matrix4.multiply(self.proj_matrix, self.view_matrix)

    def follow_snake(self, hx, hy, direction_idx, dt=1/60.0, speed_ratio=0.0, build_matrices=True):
        # Yaw target from current direction, interpolate with capped speed
        self._yaw_target = direction_idx * (math.pi / 3)
        angle_diff = (self._yaw_target - self._yaw + math.pi) % (2 * math.pi) - math.pi
        max_delta = math.radians(MAX_YAW_SPEED) * dt
        if abs(angle_diff) <= max_delta:
            self._yaw = self._yaw_target
        else:
            self._yaw += max_delta if angle_diff > 0 else -max_delta

        # Direction from interpolated yaw (smooth heading)
        dx = math.cos(self._yaw)
        dy = math.sin(self._yaw)

        # Speed-based pull-back
        dist = CAM_3D_DIST * (1.0 + speed_ratio * CAM_PULLBACK_SPEED)
        height = CAM_3D_HEIGHT * (1.0 + speed_ratio * CAM_PULLBACK_SPEED * 0.66)

        # Eat punch-in
        if self._eat_punch_timer > 0:
            punch_t = self._eat_punch_timer / CAM_EAT_PUNCH_DURATION
            dist *= (1.0 - CAM_EAT_PUNCH * punch_t)
            self._eat_punch_timer = max(0.0, self._eat_punch_timer - dt)

        # Death pull-out
        if self._death_pull_timer > 0:
            pull_t = 1.0 - self._death_pull_timer / CAM_DEATH_PULLOUT_DURATION
            dist *= (1.0 + (CAM_DEATH_PULLOUT - 1.0) * pull_t)
            height *= (1.0 + (CAM_DEATH_PULLOUT - 1.0) * pull_t * 0.5)
            self._death_pull_timer = max(0.0, self._death_pull_timer - dt)

        # Eye and target from head pixel position + direct yaw offset
        self.target = (hx + dx * CAM_3D_LOOKAHEAD, hy + dy * CAM_3D_LOOKAHEAD, 0.0)
        self.eye = (hx - dx * dist, hy - dy * dist, max(CAM_MIN_HEIGHT, height))

        # Banking decay (rate-normalized: assumes 0.9/0.1 at 60 FPS)
        fps_ratio = dt * 60.0
        self.roll_target *= 0.9 ** fps_ratio
        self.roll += (self.roll_target - self.roll) * (1.0 - 0.9 ** fps_ratio)

        # Screen shake in camera space
        if self._shake_timer > 0:
            intensity = self._shake_intensity * (self._shake_timer / self._shake_duration)
            shake_x = random.uniform(-1, 1) * intensity
            shake_y = random.uniform(-1, 1) * intensity
            shake_z = random.uniform(-1, 1) * intensity * 0.5
            self.eye = (self.eye[0] + shake_x, self.eye[1] + shake_y, self.eye[2] + shake_z)
            self._shake_timer = max(0.0, self._shake_timer - dt)

        if build_matrices:
            self._build_matrices()

    def update_idle(self, dt, time_float):
        """Gentle breathing drift for title screen / idle scenes."""
        ox = math.sin(time_float * 0.12) * 18
        oy = math.cos(time_float * 0.10) * 12
        oz = math.sin(time_float * 0.06) * 3
        eye = (self.eye[0] + ox, self.eye[1] + oy, self.eye[2] + oz)
        target = (self.target[0] + ox * 0.3, self.target[1] + oy * 0.3, self.target[2])
        self.view_matrix = Matrix4.look_at(eye, target, self.up)
        aspect = self.width / self.height
        self.proj_matrix = Matrix4.perspective(CAM_3D_FOV_RAD, aspect, CAM_3D_NEAR, CAM_3D_FAR)
        self.vp_matrix = Matrix4.multiply(self.proj_matrix, self.view_matrix)

    def snap_to(self, hx, hy, direction_idx):
        self._yaw = direction_idx * (math.pi / 3)
        self._yaw_target = self._yaw
        dx = math.cos(self._yaw)
        dy = math.sin(self._yaw)
        self.target = (hx + dx * CAM_3D_LOOKAHEAD, hy + dy * CAM_3D_LOOKAHEAD, 0.0)
        self.eye = (hx - dx * CAM_3D_DIST, hy - dy * CAM_3D_DIST, CAM_3D_HEIGHT)
        self.roll = 0.0
        self.roll_target = 0.0
        self._build_matrices()

    def eat_punch(self):
        self._eat_punch_timer = CAM_EAT_PUNCH_DURATION

    def death_pullout(self):
        self._death_pull_timer = CAM_DEATH_PULLOUT_DURATION

    def on_turn(self, direction_change):
        """direction_change: +1 for right, -1 for left."""
        self.roll_target = direction_change * CAM_BANK_INTENSITY

    def project(self, x, y, z=0):
        v = Matrix4.transform(self.vp_matrix, x, y, z, 1.0)
        if v[3] <= 1e-10:
            return (-999, -999, 99999)
        inv_w = 1.0 / v[3]
        sx_ndc = v[0] * inv_w
        sy_ndc = v[1] * inv_w
        depth = v[2] * inv_w
        sx = (sx_ndc + 1.0) * 0.5 * self.width
        sy = (1.0 - sy_ndc) * 0.5 * self.height
        if abs(self.roll) > 0.001:
            cos_r = math.cos(self.roll)
            sin_r = math.sin(self.roll)
            cx_s = self.width * 0.5
            cy_s = self.height * 0.5
            rx = sx - cx_s
            ry = sy - cy_s
            sx = cx_s + rx * cos_r - ry * sin_r
            sy = cy_s + rx * sin_r + ry * cos_r
        return (sx, sy, depth)
