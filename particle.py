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
        # Physics
        self.vz -= PARTICLE_GRAVITY * dt
        self.vx *= PARTICLE_AIR_DRAG
        self.vy *= PARTICLE_AIR_DRAG

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        # Ground bounce
        if self.z < 0:
            self.z = 0
            self.vz = -self.vz * PARTICLE_BOUNCE
            # Ground friction
            self.vx *= PARTICLE_GROUND_FRICTION
            self.vy *= PARTICLE_GROUND_FRICTION

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
        if sx == -999:
            return
        s = max(1, int(self.current_size))
        a = self.alpha
        if a <= 0:
            return

        r, g, b = self.color
        if game is not None:
            amb = getattr(game, '_ambient', 1.0)
            sc = getattr(game, '_sun_color', (255, 255, 255))
            tone = min(1.0, 0.65 + amb * 0.35)
            r = int(r * tone * 0.8 + sc[0] * (1.0 - tone) * 0.2 * (r / 255.0))
            g = int(g * tone * 0.8 + sc[1] * (1.0 - tone) * 0.2 * (g / 255.0))
            b = int(b * tone * 0.8 + sc[2] * (1.0 - tone) * 0.2 * (b / 255.0))

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
            scaled_glow = game._particle_glow_scaled.get((self.color, g_size)) if game else None
            if scaled_glow is None:
                glow_surf = pygame.Surface((g_size, g_size), pygame.SRCALPHA)
                center = g_size // 2
                for gi in range(center, 0, -1):
                    ga = int(a * (1 - gi / center) * 0.5)
                    if ga > 0:
                        pygame.draw.circle(glow_surf, (r, g, b, ga), (center, center), gi)
                scaled_glow = glow_surf
                if game:
                    game._particle_glow_scaled[(self.color, g_size)] = scaled_glow
            else:
                scaled_glow.set_alpha(a)
            surf.blit(scaled_glow, (int(sx - g_size / 2), int(sy - g_size / 2)), special_flags=pygame.BLEND_ADD)
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

    def emit_apple_burst(self, cx, cy, cz):
        """Juicy splash with sparks on apple eat."""
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
            self.emit(cx + ox, cy + oy, cz, vx, vy, vz, color, size, lifetime, 'glow')
        for _ in range(10):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(4, 8)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed * 0.5
            vz = random.uniform(3, 6)
            self.emit(cx, cy, cz, vx, vy, vz, (255, 255, 200), random.uniform(1, 2), random.uniform(0.3, 0.8), 'spark')

    def emit_movement_dust(self, cx, cy, cz, dir_x, dir_y):
        """Faint puffs kicked up when the snake changes direction."""
        for _ in range(3):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(0.3, 0.8)
            vx = math.cos(angle) * speed + dir_x * 0.2
            vy = math.sin(angle) * speed + dir_y * 0.2
            vz = random.uniform(0.1, 0.3)
            color = (160, 190, 150)
            size = random.uniform(1, 2)
            lifetime = random.uniform(0.4, 0.8)
            self.emit(cx, cy, cz, vx, vy, vz, color, size, lifetime)

    def emit_death_burst(self, cx, cy, cz):
        """Dramatic burst on snake death."""
        for _ in range(40):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(3, 10)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed * 0.7
            vz = random.uniform(2, 8)
            color = random.choice([
                (220, 60, 60), (200, 40, 40), (255, 100, 80),
                (180, 50, 50), (255, 80, 60), (100, 220, 120),
            ])
            size = random.uniform(2, 5)
            lifetime = random.uniform(0.5, 1.5)
            ox = random.uniform(-6, 6)
            oy = random.uniform(-6, 6)
            pt = 'glow' if random.random() < 0.3 else 'spark'
            self.emit(cx + ox, cy + oy, cz, vx, vy, vz, color, size, lifetime, pt)

    def emit_ambient_mote(self, cx, cy, cz):
        """Drifting ambient mote or firefly."""
        vx = random.uniform(-0.12, 0.12)
        vy = random.uniform(-0.06, 0.06)
        vz = random.uniform(0.01, 0.06)
        is_firefly = random.random() < 0.3
        if is_firefly:
            c = random.choice([(180, 230, 100), (220, 255, 150), (200, 240, 120)])
            self.emit(cx, cy, cz, vx, vy, vz, c, random.uniform(2, 3.5), random.uniform(4, 8), 'glow')
        else:
            c = random.choice([(50, 160, 140), (70, 190, 155), (90, 210, 170), (40, 140, 130)])
            self.emit(cx, cy, cz, vx, vy, vz, c, random.uniform(1, 2), random.uniform(3, 7))

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
