import math
from config import *


class Matrix4:
    """4×4 column-major matrix utilities for the MVP pipeline."""

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
        f = (eye[0]-target[0], eye[1]-target[1], eye[2]-target[2])
        fl = math.hypot(*f)
        if fl < 1e-10:
            return Matrix4.identity()
        f = (f[0]/fl, f[1]/fl, f[2]/fl)

        s = (up[1]*f[2] - up[2]*f[1],
             up[2]*f[0] - up[0]*f[2],
             up[0]*f[1] - up[1]*f[0])
        sl = math.hypot(*s)
        if sl < 1e-10:
            return Matrix4.identity()
        s = (s[0]/sl, s[1]/sl, s[2]/sl)

        u = (s[1]*f[2] - s[2]*f[1],
             s[2]*f[0] - s[0]*f[2],
             s[0]*f[1] - s[1]*f[0])

        return [
            s[0], u[0], f[0], 0,
            s[1], u[1], f[1], 0,
            s[2], u[2], f[2], 0,
            -s[0]*eye[0]-s[1]*eye[1]-s[2]*eye[2],
            -u[0]*eye[0]-u[1]*eye[1]-u[2]*eye[2],
            -f[0]*eye[0]-f[1]*eye[1]-f[2]*eye[2],
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
        self._old_x = 0.0
        self._old_y = 0.0
        self.width = WIDTH
        self.height = HEIGHT

    def _build_matrices(self):
        aspect = self.width / self.height
        self.view_matrix = Matrix4.look_at(self.eye, self.target, self.up)
        self.proj_matrix = Matrix4.perspective(CAM_3D_FOV_RAD, aspect, CAM_3D_NEAR, CAM_3D_FAR)
        self.vp_matrix = Matrix4.multiply(self.proj_matrix, self.view_matrix)

    def follow_snake(self, head_q, head_r, direction_idx):
        from utils import hex_to_pixel
        hx, hy = hex_to_pixel(head_q, head_r)
        dx, dy = DIR_VECTORS[direction_idx]

        desired_target = (hx + dx * CAM_3D_LOOKAHEAD, hy + dy * CAM_3D_LOOKAHEAD, 0.0)
        desired_eye = (hx - dx * CAM_3D_DIST, hy - dy * CAM_3D_DIST, CAM_3D_HEIGHT)

        lerp = CAM_3D_LERP
        self.eye = (
            self.eye[0] + (desired_eye[0] - self.eye[0]) * lerp,
            self.eye[1] + (desired_eye[1] - self.eye[1]) * lerp,
            self.eye[2] + (desired_eye[2] - self.eye[2]) * lerp,
        )
        self.target = (
            self.target[0] + (desired_target[0] - self.target[0]) * lerp,
            self.target[1] + (desired_target[1] - self.target[1]) * lerp,
            self.target[2] + (desired_target[2] - self.target[2]) * lerp,
        )

        self._old_x += (desired_eye[0] - self._old_x) * lerp
        self._old_y += (desired_eye[1] - self._old_y) * lerp

        self._build_matrices()

    def snap_to(self, head_q, head_r, direction_idx):
        from utils import hex_to_pixel
        hx, hy = hex_to_pixel(head_q, head_r)
        dx, dy = DIR_VECTORS[direction_idx]

        self.target = (hx + dx * CAM_3D_LOOKAHEAD, hy + dy * CAM_3D_LOOKAHEAD, 0.0)
        self.eye = (hx - dx * CAM_3D_DIST, hy - dy * CAM_3D_DIST, CAM_3D_HEIGHT)
        self._old_x = self.eye[0]
        self._old_y = self.eye[1]

        self._build_matrices()

    def project(self, x, y, z=0):
        if DEBUG_OLD_CAMERA:
            return self._project_old(x, y, z)
        v = Matrix4.transform(self.vp_matrix, x, y, z, 1.0)
        if abs(v[3]) < 1e-10:
            return (-999, -999, 99999)
        inv_w = 1.0 / v[3]
        sx_ndc = v[0] * inv_w
        sy_ndc = v[1] * inv_w
        depth = v[2] * inv_w
        sx = (sx_ndc + 1.0) * 0.5 * self.width
        sy = (1.0 - sy_ndc) * 0.5 * self.height
        return (sx, sy, depth)

    def _project_old(self, x, y, z=0):
        COS_TILT = math.cos(TILT)
        SIN_TILT = math.sin(TILT)
        wx = x - self._old_x
        wy = y - self._old_y
        y_rot = wy * COS_TILT - z * SIN_TILT
        depth = -wy * SIN_TILT - z * COS_TILT
        z_cam = depth + CAM_DIST
        if z_cam <= 0:
            return (-999, -999, 99999)
        factor = FOV / z_cam
        sx = wx * factor + WIDTH / 2
        sy = y_rot * factor + Y_OFFSET
        return (sx, sy, z_cam)
