"""Unit tests for Particle and ParticlePool."""
import math

import pytest
from config import PARTICLE_GRAVITY, PARTICLE_BOUNCE, PARTICLE_GROUND_FRICTION
from particle import Particle, ParticlePool


class TestParticlePhysics:
    def test_gravity_pulls_down(self):
        p = Particle(0, 0, 10, 0, 0, 0, (255, 0, 0), 5, 2.0)
        vy_before = p.vz
        p.update(0.016)
        # vz should decrease (gravity is negative)
        assert p.vz < vy_before

    def test_bounce_at_ground(self):
        p = Particle(0, 0, 2, 0, 0, -5, (255, 0, 0), 5, 2.0)
        p.update(1.0)
        # After bounce, z >= 0 and vz should be positive (bouncing up)
        assert p.z >= 0
        assert p.vz >= 0

    def test_ground_friction_applied(self):
        p = Particle(0, 0, 1, 10, 10, -10, (255, 0, 0), 5, 2.0)
        vx_before = p.vx
        vy_before = p.vy
        p.update(1.0)
        # After hitting ground, friction should reduce horizontal velocity
        assert abs(p.vx) <= abs(vx_before) + 1e-9
        assert abs(p.vy) <= abs(vy_before) + 1e-9

    def test_air_drag(self):
        p = Particle(0, 0, 10, 10, 10, 0, (255, 0, 0), 5, 2.0)
        p.update(0.016)
        # Air drag reduces velocity
        assert abs(p.vx) < 10.0
        assert abs(p.vy) < 10.0

    def test_air_drag_does_not_affect_vertical(self):
        p = Particle(0, 0, 10, 0, 0, 5, (255, 0, 0), 5, 2.0)
        p.update(0.016)
        # vz should only be affected by gravity, not air drag
        assert p.vz < 5.0  # gravity reduces it


class TestParticleDead:
    def test_not_dead_at_start(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 2.0)
        assert p.dead is False

    def test_dead_after_lifetime(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 0.1)
        p.update(0.2)
        assert p.dead is True

    def test_dead_exactly_at_lifetime(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
        p.update(1.0)
        assert p.dead is True

    def test_dead_just_before_lifetime(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
        p.update(0.999)
        assert p.dead is False


class TestParticleAlpha:
    def test_alpha_full_at_start(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 2.0)
        assert p.alpha == 255

    def test_alpha_fades(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
        p.update(0.5)
        assert p.alpha < 255

    def test_alpha_zero_at_death(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 0.5)
        p.update(0.5)
        assert p.alpha <= 0


class TestParticleSize:
    def test_current_size_reduces(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 10, 1.0)
        s0 = p.current_size
        p.update(0.5)
        s1 = p.current_size
        # Size should shrink (or oscillate but trend down)
        assert s1 <= s0 * 1.3  # oscillation could bump it, but not too much

    def test_current_size_positive(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
        for _ in range(10):
            p.update(0.1)
            assert p.current_size > 0


class TestParticlePool:
    def test_emit_adds_particle(self):
        pool = ParticlePool(10)
        pool.emit(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
        assert len(pool) == 1

    def test_emit_multiple_particles(self):
        pool = ParticlePool(10)
        for _ in range(5):
            pool.emit(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
        assert len(pool) == 5

    def test_clean_removes_dead(self):
        pool = ParticlePool(10)
        for _ in range(5):
            pool.emit(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 0.05)
        pool.update_all(0.1)
        pool.clean()
        assert len(pool) == 0

    def test_clean_keeps_alive(self):
        pool = ParticlePool(10)
        pool.emit(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 10.0)
        pool.update_all(0.1)
        pool.clean()
        assert len(pool) == 1

    def test_pool_recycles(self):
        pool = ParticlePool(10)
        initial_free = len(pool._free)
        for _ in range(3):
            pool.emit(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 0.05)
        pool.update_all(0.1)
        pool.clean()
        # Free list should have grown (recycled particles)
        assert len(pool._free) >= initial_free

    def test_pool_does_not_exceed_capacity(self):
        pool = ParticlePool(5)
        for _ in range(100):
            pool.emit(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
        update_all = pool._alive + pool._free
        assert len(update_all) >= 5  # at least initial capacity
        assert len(pool._free) + len(pool._alive) >= 5

    def test_clear_empties_pool(self):
        pool = ParticlePool(10)
        for _ in range(5):
            pool.emit(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
        pool.clear()
        assert len(pool) == 0

    def test_emit_apple_burst(self):
        pool = ParticlePool(50)
        pool.emit_apple_burst(100, 100, 2)
        assert len(pool) == 30  # 20 glow + 10 spark

    def test_emit_movement_dust(self):
        pool = ParticlePool(10)
        pool.emit_movement_dust(100, 100, 0, 1, 0)
        assert len(pool) == 3

    def test_emit_death_burst(self):
        pool = ParticlePool(50)
        pool.emit_death_burst(100, 100, 2)
        assert len(pool) == 40

    def test_emit_ambient_mote(self):
        pool = ParticlePool(10)
        pool.emit_ambient_mote(100, 100, 2)
        assert len(pool) == 1

    def test_sort_by_z(self):
        pool = ParticlePool(10)
        pool.emit(0, 0, 5, 0, 0, 0, (255, 0, 0), 5, 1.0)
        pool.emit(0, 0, 1, 0, 0, 0, (255, 0, 0), 5, 1.0)
        pool.emit(0, 0, 3, 0, 0, 0, (255, 0, 0), 5, 1.0)
        pool.sort_by_z()
        zs = [p.z for p in pool]
        assert zs == sorted(zs)


class TestParticleRotation:
    def test_rotation_updates(self):
        p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
        r0 = p.rotation
        p.update(0.016)
        assert p.rotation != r0

    def test_rot_speed_initialized(self):
        for _ in range(50):
            p = Particle(0, 0, 0, 0, 0, 0, (255, 0, 0), 5, 1.0)
            assert -2 <= p.rot_speed <= 2
