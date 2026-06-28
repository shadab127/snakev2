import math
import random
import pygame
from config import *



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
        sx, sy, depth = game.camera.project(self.x, self.y, self.z)
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
