import math
from config import *


COS_TILT = math.cos(TILT)
SIN_TILT = math.sin(TILT)


class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def snap_to(self, head_q, head_r, direction_idx):
        from utils import hex_to_pixel
        hx, hy = hex_to_pixel(head_q, head_r)
        dx, dy = DIR_VECTORS[direction_idx]
        self.x = hx - dx * CAM_DIST
        self.y = hy - dy * CAM_DIST

    def follow_snake(self, head_q, head_r, direction_idx):
        from utils import hex_to_pixel
        hx, hy = hex_to_pixel(head_q, head_r)
        dx, dy = DIR_VECTORS[direction_idx]
        desired_x = hx - dx * CAM_DIST
        desired_y = hy - dy * CAM_DIST
        self.x += (desired_x - self.x) * CAM_3D_LERP
        self.y += (desired_y - self.y) * CAM_3D_LERP

    def project(self, x, y, z=0):
        wx = x - self.x
        wy = y - self.y
        y_rot = wy * COS_TILT - z * SIN_TILT
        depth = -wy * SIN_TILT - z * COS_TILT
        z_cam = depth + CAM_DIST
        if z_cam <= 0:
            return (-999, -999, 99999)
        factor = FOV / z_cam
        sx = wx * factor + WIDTH / 2
        sy = y_rot * factor + Y_OFFSET
        return (sx, sy, z_cam)
