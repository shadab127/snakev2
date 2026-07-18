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
