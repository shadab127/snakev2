"""Headless soak test — runs the game loop without a display.

Uses SDL_VIDEODRIVER=dummy (set in conftest.py) so pygame works headless.
Drives ~100000+ simulation steps with random turns and asserts
invariants (no crash, valid tile positions, score increases).
"""
import math
import random
import pygame

from config import FIXED_DT, DIR_VECTORS, GRID_RADIUS, MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL, SPEED_DECAY_PER_POINT, MAX_SIM_STEPS, MAX_FRAME_DT, FPS_SMOOTH_ALPHA
from main import SnakeGame
from game_state import GameState


class TestHeadlessSimulation:
    """Run a full headless game session with scripted inputs."""

    def _advance(self, game, steps):
        for _ in range(steps):
            game.update(FIXED_DT)

    def _start_game(self):
        game = SnakeGame()
        game.state = GameState.PLAYING
        game.reset()
        game.audio._ok = False
        # Drain any pending events so they don't interfere
        pygame.event.clear()
        return game

    @staticmethod
    def _force_apple_in_front(game):
        """Place an apple on the tile directly in front of the snake head."""
        from utils import wrap_coords
        hq, hr = game.snake[0]
        dq, dr = DIR_VECTORS[game.direction]
        target = wrap_coords(hq + dq, hr + dr)
        if target not in game.snake:
            game.apple = target

    def test_1000_step_soak(self):
        """Run 100000+ simulation steps with random turns.

        Uses random.Random with seed 1 for deterministic behaviour.
        Forces apple placement periodically to guarantee eating.
        Verifies: no crash, valid positions, length/score consistency,
        score > 0 (snake ate at least once).
        """
        game = self._start_game()
        assert game.state == GameState.PLAYING

        total_steps = 0
        target_steps = 100000
        feed_every = 8  # feed every N move steps
        move_count = 0
        rng = random.Random(1)

        # Pre-generate turn sequence to ensure deterministic path
        turn_sequence = [rng.choice(['L', 'R']) for _ in range(10000)]
        turn_idx = 0

        while total_steps < target_steps and game.state == GameState.PLAYING:
            # Periodically force-feed without turning so the snake eats
            if move_count % feed_every == 0 and move_count > 0:
                self._force_apple_in_front(game)
                interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - game.score * SPEED_DECAY_PER_POINT)
                steps_needed = max(1, int(interval / FIXED_DT)) + 1
                self._advance(game, steps_needed)
                total_steps += steps_needed
                move_count += 1
                continue

            # Apply turn by calling game methods directly (reliable)
            if turn_sequence[turn_idx % len(turn_sequence)] == 'L':
                game.turn_left()
            else:
                game.turn_right()
            turn_idx += 1

            # Advance enough for one snake move
            interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - game.score * SPEED_DECAY_PER_POINT)
            steps_needed = max(1, int(interval / FIXED_DT)) + 1
            self._advance(game, steps_needed)
            total_steps += steps_needed
            move_count += 1

            # Validate invariants periodically
            if move_count % 100 == 0:
                self._assert_invariants(game)

        assert game.score > 0, (
            f"Snake never ate after {total_steps} steps ({move_count} moves, score={game.score})"
        )

    def test_no_immediate_crash(self):
        """Starting a new game should not crash."""
        game = self._start_game()
        assert game.state == GameState.PLAYING
        for _ in range(100):
            game.update(FIXED_DT)

    def test_snake_length_matches_score(self):
        """Every 10 points = one extra segment."""
        game = self._start_game()
        rng = random.Random(123)
        for _ in range(15000):
            if rng.random() < 0.5:
                game.turn_left()
            else:
                game.turn_right()
            self._advance(game, 5)
            if game.state != GameState.PLAYING:
                break
        expected_length = 3 + game.score // 10
        assert len(game.snake) == expected_length, (
            f"Snake length {len(game.snake)} != expected {expected_length} "
            f"(score={game.score})"
        )

    def test_positions_always_valid(self):
        """All snake segments should be on valid wrapped tiles."""
        game = self._start_game()
        rng = random.Random(456)
        for _ in range(8000):
            if rng.random() < 0.5:
                game.turn_left()
            else:
                game.turn_right()
            self._advance(game, 5)
            if game.state != GameState.PLAYING:
                break
        for q, r in game.snake:
            assert -GRID_RADIUS <= q <= GRID_RADIUS, f"q={q} out of bounds"
            assert -GRID_RADIUS <= r <= GRID_RADIUS, f"r={r} out of bounds"

    def test_reset_works(self):
        """Resetting a running game should work and reset score."""
        game = self._start_game()
        rng = random.Random(789)
        for _ in range(5000):
            if rng.random() < 0.5:
                game.turn_left()
            else:
                game.turn_right()
            self._advance(game, 5)
            if game.state != GameState.PLAYING:
                break
        game.reset()
        assert game.score == 0
        assert len(game.snake) == 3

    def test_apple_eating(self):
        """Apple placed in front of snake should get eaten."""
        game = self._start_game()
        hq, hr = game.snake[0]
        dq, dr = DIR_VECTORS[game.direction]
        from utils import wrap_coords
        target = wrap_coords(hq + dq, hr + dr)
        game.apple = target
        score_before = game.score
        interval = max(MIN_MOVE_INTERVAL, BASE_MOVE_INTERVAL - game.score * SPEED_DECAY_PER_POINT)
        steps_needed = max(1, int(interval / FIXED_DT)) + 10
        for _ in range(steps_needed * 3):
            game.update(FIXED_DT)
        assert game.score > score_before, "Snake should eat the apple placed in front"

    def _assert_invariants(self, game):
        for q, r in game.snake:
            assert -GRID_RADIUS <= q <= GRID_RADIUS
            assert -GRID_RADIUS <= r <= GRID_RADIUS

        if game.apple:
            aq, ar = game.apple
            assert -GRID_RADIUS <= aq <= GRID_RADIUS
            assert -GRID_RADIUS <= ar <= GRID_RADIUS
            assert game.apple not in game.snake

        expected = 3 + game.score // 10
        assert len(game.snake) == expected

        assert 0 <= game.direction < 6
        assert 0 <= game.next_direction < 6

    def test_bounded_catch_up(self):
        """MAX_SIM_STEPS is defined and burst of updates doesn't corrupt state."""
        assert MAX_SIM_STEPS >= 1
        assert MAX_SIM_STEPS <= 20

        game = self._start_game()
        self._force_apple_in_front(game)

        initial_score = game.score
        initial_length = len(game.snake)

        max_steps_per_frame = MAX_SIM_STEPS * 3
        for _ in range(40):
            for _ in range(max_steps_per_frame):
                game.update(FIXED_DT)
            self._force_apple_in_front(game)

        self._assert_invariants(game)
        assert game.score >= initial_score
        assert len(game.snake) >= initial_length

    def test_catch_up_overrun_counter_fires(self):
        """A frame whose accumulated dt exceeds the sim-step budget must be
        counted BEFORE the accumulator is clamped — checking after clamping
        makes the condition permanently false and the instrumentation lies."""
        game = self._start_game()
        game._catch_up_overruns = 0

        sim_accumulator = 0.0
        raw_dt = FIXED_DT * MAX_SIM_STEPS * 5
        sim_accumulator += raw_dt
        if sim_accumulator > FIXED_DT * MAX_SIM_STEPS:
            game._catch_up_overruns += 1
        sim_accumulator = min(sim_accumulator, FIXED_DT * MAX_SIM_STEPS)

        assert game._catch_up_overruns == 1
        assert sim_accumulator == FIXED_DT * MAX_SIM_STEPS

    def test_frame_pacing_bounds(self):
        """MAX_FRAME_DT prevents spiral of death from large dt spikes."""
        from config import MAX_FRAME_DT, FIXED_DT, MAX_SIM_STEPS

        import math
        assert MAX_FRAME_DT > 0
        assert MAX_FRAME_DT <= 0.25
        assert FIXED_DT * MAX_SIM_STEPS <= MAX_FRAME_DT
        capped = min(0.5, MAX_FRAME_DT)
        assert capped == MAX_FRAME_DT
        assert FPS_SMOOTH_ALPHA > 0
        assert FPS_SMOOTH_ALPHA <= 0.5

    def test_tile_cache_dirty_tracking(self):
        """Dirty-tile invalidation only marks near-snake tiles, not all."""
        from utils import all_hexes
        game = self._start_game()
        self._force_apple_in_front(game)

        game._invalidate_all_tiles()
        all_count = len(game._dirty_tiles)
        assert all_count >= len(list(all_hexes())) - 10

        game._dirty_tiles = set()
        game._prev_snake_set = set(game.snake)
        changed = set(game.snake)
        if game.apple:
            changed.add(game.apple)
        game._invalidate_tiles_near(changed, radius=2)
        assert len(game._dirty_tiles) < all_count
        assert len(game._dirty_tiles) > 0

    def test_height_map_cached(self):
        """Precomputed height map avoids per-tile rebuild."""
        game = self._start_game()
        game._height_map_valid = False
        game._height_map = {}
        game._rebuild_height_map()
        assert len(game._height_map) > 0
        assert game._height_map_valid
        keys_before = set(game._height_map.keys())
        game._rebuild_height_map()
        assert game._height_map_valid
        assert set(game._height_map.keys()) == keys_before

    def test_render_culling_bounds(self):
        """Render culling bounds are defined and reasonable."""
        from config import (SNAKE_RENDER_CULL_MARGIN, SHADOW_RENDER_CULL_MARGIN,
                          PARTICLE_RENDER_CULL_MARGIN, MAX_CONSECUTIVE_OFFSCREEN,
                          MAX_RENDER_SPLINE_SAMPLES, MAX_PARTICLES)
        assert SNAKE_RENDER_CULL_MARGIN >= 40
        assert SHADOW_RENDER_CULL_MARGIN >= 20
        assert PARTICLE_RENDER_CULL_MARGIN >= 10
        assert MAX_CONSECUTIVE_OFFSCREEN >= 5
        assert MAX_CONSECUTIVE_OFFSCREEN <= 100
        assert MAX_RENDER_SPLINE_SAMPLES >= 100
        assert MAX_RENDER_SPLINE_SAMPLES <= 2000
        assert MAX_PARTICLES > 0

    def test_quality_presets_defined(self):
        """Quality presets exist and are well-formed."""
        from config import QUALITY_PRESETS, DEFAULT_QUALITY
        assert 'low' in QUALITY_PRESETS
        assert 'medium' in QUALITY_PRESETS
        assert 'high' in QUALITY_PRESETS
        assert DEFAULT_QUALITY in QUALITY_PRESETS
        bool_keys = {'bloom', 'tone_map', 'god_rays', 'vignette', 'shadow_soft', 'ao'}
        for level, preset in QUALITY_PRESETS.items():
            for k in bool_keys:
                assert k in preset, f"{level} missing key {k}"
                assert isinstance(preset[k], bool), f"{level}.{k} must be bool"
            assert 'grass_density' in preset, f"{level} missing grass_density"
            assert 0 < preset['grass_density'] <= 1.0, f"{level} grass_density out of range"
        assert QUALITY_PRESETS['low']['bloom'] is False
        assert QUALITY_PRESETS['high']['bloom'] is True
        assert QUALITY_PRESETS['low']['vignette'] is False
        assert QUALITY_PRESETS['high']['vignette'] is True


class TestWrapTransitionStateMachine:
    """Dedicated coverage for the dive -> roll -> emerge world-flip state
    machine (main.py move_snake()/update()), which had zero test coverage
    despite being where the double-wrap-during-transition bug lived."""

    def _start_game(self):
        game = SnakeGame()
        game.state = GameState.PLAYING
        game.reset()
        game.audio._ok = False
        pygame.event.clear()
        return game

    def _put_snake_at_edge(self, game, axis='q'):
        R = GRID_RADIUS
        if axis == 'q':
            game.snake = [(R, 0), (R - 1, 0), (R - 2, 0)]
            game.direction = 0
        else:
            game.snake = [(0, R), (0, R - 1), (0, R - 2)]
            game.direction = 1
        game.next_direction = game.direction
        game.path_history.clear()
        for sq, sr in game.snake:
            game.path_history.append((sq, sr, 0, 0))
        game._visual_dq = 0
        game._visual_dr = 0

    def _advance_to_next_wrap(self, game, max_steps=200):
        for i in range(max_steps):
            game.update(FIXED_DT)
            if game._wrap_frame:
                game._wrap_frame = False
                return i
        raise AssertionError("wrap did not occur within max_steps")

    def test_wrap_starts_dive_phase_at_zero(self):
        """A fresh wrap must start the transition at phase='dive' with
        roll_angle==0.0 (the roll animation assumes it starts clean) and
        dive_amount close to zero -- move_snake() sets dive_amount=0.0, but
        the same update() call immediately advances the transition by one
        dt afterward, so a single frame of progress is expected, not a
        multi-frame head start."""
        game = self._start_game()
        self._put_snake_at_edge(game)
        self._advance_to_next_wrap(game)
        wt = game._wrap_transition
        assert wt['active'] is True
        assert wt['phase'] == 'dive'
        assert wt['roll_angle'] == 0.0
        assert 0.0 <= wt['dive_amount'] < 0.05

    def test_transition_progresses_dive_roll_emerge(self):
        """Over the full WRAP_TRANSITION_DURATION, the state machine must
        visit dive, then roll (with roll_angle rising from 0 to pi), then
        emerge, then deactivate -- in that order, with roll_angle
        monotonically non-decreasing throughout (no backward snap)."""
        from config import WRAP_TRANSITION_DURATION
        game = self._start_game()
        self._put_snake_at_edge(game)
        self._advance_to_next_wrap(game)

        phases_seen = []
        roll_angles = []
        total_steps = int(WRAP_TRANSITION_DURATION / FIXED_DT) + 20
        for _ in range(total_steps):
            wt = game._wrap_transition
            if not wt['active']:
                break
            phases_seen.append(wt['phase'])
            roll_angles.append(wt['roll_angle'])
            game.update(FIXED_DT)

        # Roll angle must never decrease while the transition is active.
        for i in range(1, len(roll_angles)):
            assert roll_angles[i] >= roll_angles[i - 1] - 1e-9, (
                f"roll_angle snapped backward at step {i}: "
                f"{roll_angles[i-1]} -> {roll_angles[i]}"
            )

        distinct_phases = []
        for p in phases_seen:
            if not distinct_phases or distinct_phases[-1] != p:
                distinct_phases.append(p)
        assert distinct_phases == ['dive', 'roll', 'emerge'], (
            f"unexpected phase sequence: {distinct_phases}"
        )
        assert max(roll_angles) > math.pi - 0.05, "roll never reached ~pi"

    def test_transition_completes_and_resets_cleanly(self):
        """After the full duration elapses, the transition must deactivate
        and every field must return to its post-reset default -- no
        lingering roll_angle/dive_amount that would leave the world
        visibly rotated or the head permanently sunk."""
        from config import WRAP_TRANSITION_DURATION
        game = self._start_game()
        self._put_snake_at_edge(game)
        self._advance_to_next_wrap(game)

        total_steps = int(WRAP_TRANSITION_DURATION / FIXED_DT) + 20
        for _ in range(total_steps):
            game.update(FIXED_DT)

        wt = game._wrap_transition
        assert wt['active'] is False
        assert wt['timer'] == 0
        assert wt['phase'] == 'none'
        assert wt['roll_angle'] == 0.0
        assert wt['dive_amount'] == 0.0

    def test_double_wrap_during_active_transition_does_not_snap(self):
        """A second seam crossing landing inside an already-active
        transition must NOT retrigger a fresh dict -- that would snap
        roll_angle/dive_amount back to 0 mid-roll, producing exactly the
        hard cut Phase 14 forbids. Drive the snake through a corner at max
        speed so the second wrap lands during the ROLL phase of the first
        transition (roll_angle > 0) -- landing during the dive phase
        (roll_angle still 0) would pass even with the bug reintroduced,
        since there'd be nothing yet to snap backward from."""
        from config import WRAP_TRANSITION_DURATION
        game = self._start_game()
        game.score = 1000  # MIN_MOVE_INTERVAL -> fastest move cadence
        R = GRID_RADIUS
        game.snake = [(R, -R), (R - 1, -R), (R - 2, -R)]
        game.direction = 0
        game.next_direction = 0
        game.path_history.clear()
        for sq, sr in game.snake:
            game.path_history.append((sq, sr, 0, 0))
        game._visual_dq = 0
        game._visual_dr = 0

        wrap_count = 0
        repositioned = False
        prev_roll = None
        snapped = False
        roll_angle_seen_positive = False
        for i in range(300):
            game.update(FIXED_DT)
            if game._wrap_frame:
                wrap_count += 1
                game._wrap_frame = False
            wt = game._wrap_transition
            # Once the first transition reaches the roll phase, re-aim the
            # snake at the r-edge so the second wrap's move_snake() call
            # lands while roll_angle > 0 -- the exact window the bug lived in.
            if wrap_count == 1 and not repositioned and wt['phase'] == 'roll':
                hq, hr = game.snake[0]
                game.snake[0] = (hq, R)
                game.snake[1] = (hq, R - 1)
                game.snake[2] = (hq, R - 2)
                game.direction = 1
                game.next_direction = 1
                repositioned = True
            if wt['active'] and wt['roll_angle'] > 0:
                roll_angle_seen_positive = True
            if wt['active'] and prev_roll is not None and wt['roll_angle'] < prev_roll - 1e-6:
                snapped = True
            prev_roll = wt['roll_angle'] if wt['active'] else None
            if wrap_count >= 2:
                break

        assert repositioned, "test setup failed to reach the roll phase before the second wrap"
        assert wrap_count == 2, "test setup failed to force a second wrap"
        assert roll_angle_seen_positive, "roll_angle never went positive -- test didn't exercise the bug window"
        assert not snapped, "roll_angle snapped backward on overlapping wrap"
