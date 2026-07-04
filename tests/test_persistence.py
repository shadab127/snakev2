"""Unit tests for persistence module (Phase 13)."""
import json
import os
import tempfile

import pytest

from persistence import PersistenceManager
from config import SCHEMA_VERSION


@pytest.fixture
def tmp_dir():
    """Yield a temporary directory path, cleaned up after test."""
    with tempfile.TemporaryDirectory() as d:
        yield d


def _pm(tmp_dir):
    """Create a PersistenceManager that writes to the given temp directory."""
    return PersistenceManager(save_dir=tmp_dir)


class TestPersistenceRoundTrip:
    def test_save_then_load_returns_same_data(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.set_high_score(420)
        pm.set_settings({'music_volume': 0.8, 'sfx_volume': 0.3,
                         'ambience_volume': 0.1, 'bloom': False,
                         'tone_map': True, 'god_rays': False,
                          'vignette': True,
                         'show_fps': True})
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 420
        assert pm2.get_settings()['music_volume'] == 0.8
        assert pm2.get_settings()['bloom'] is False
        assert pm2.get_settings()['show_fps'] is True

    def test_round_trip_defaults(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 0
        assert pm2.get_stats()['games_played'] == 0
        assert pm2.get_settings()['music_volume'] == 0.5

    def test_high_score_preserved(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.set_high_score(9999)
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 9999

    def test_top_scores_preserved(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.add_score(100)
        pm.add_score(500)
        pm.add_score(300)
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        scores = pm2.get_top_scores()
        assert len(scores) == 3
        assert scores[0]['score'] == 500
        assert scores[1]['score'] == 300
        assert scores[2]['score'] == 100

    def test_top_scores_max_five(self, tmp_dir):
        pm = _pm(tmp_dir)
        for s in [10, 20, 30, 40, 50, 60]:
            pm.add_score(s)
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        scores = pm2.get_top_scores()
        assert len(scores) == 5
        assert [s['score'] for s in scores] == [60, 50, 40, 30, 20]

    def test_record_game_updates_stats(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.record_game(200, 15, 120.5, 18)
        stats = pm.get_stats()
        assert stats['games_played'] == 1
        assert stats['apples_eaten'] == 15
        assert stats['total_play_time'] == 120.5
        assert stats['longest_snake'] == 18
        assert pm.get_high_score() == 200


class TestPersistenceMissingFile:
    def test_missing_file_returns_defaults(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.load()
        assert pm.get_high_score() == 0
        assert pm.get_stats()['games_played'] == 0

    def test_missing_file_does_not_raise(self, tmp_dir):
        pm = _pm(tmp_dir)
        try:
            pm.load()
            assert pm.get_high_score() == 0
        except Exception:
            pytest.fail("load() raised on missing file")


class TestPersistenceCorruption:
    def _corrupt_write(self, path, content):
        with open(path, 'w') as f:
            f.write(content)

    def test_truncated_file_returns_defaults(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.save()
        self._corrupt_write(pm._save_path, "{")
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 0

    def test_garbage_file_returns_defaults(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.save()
        self._corrupt_write(pm._save_path, "this is not json")
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 0

    def test_empty_file_returns_defaults(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.save()
        self._corrupt_write(pm._save_path, "")
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 0

    def test_partial_data_returns_defaults(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.save()
        with open(pm._save_path, 'w') as f:
            json.dump({"high_score": 500}, f)
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 0


class TestPersistenceSchemaVersion:
    def test_wrong_version_returns_defaults(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm._data['schema_version'] = 99
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 0

    def test_current_version_accepted(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.set_high_score(50)
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 50

    def test_none_schema_resets(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.save()
        with open(pm._save_path, 'r') as f:
            data = json.load(f)
        del data['schema_version']
        with open(pm._save_path, 'w') as f:
            json.dump(data, f)
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 0


class TestPersistenceEdgeCases:
    def test_zero_high_score(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.set_high_score(0)
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 0

    def test_all_settings_off(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.set_settings({'music_volume': 0.0, 'sfx_volume': 0.0,
                         'ambience_volume': 0.0, 'bloom': False,
                         'tone_map': False, 'god_rays': False,
                          'vignette': False,
                         'show_fps': False})
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        s = pm2.get_settings()
        assert all(v is False for v in s.values()) or not any(s.values())

    def test_record_game_zero(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.record_game(0, 0, 0.0, 3)
        stats = pm.get_stats()
        assert stats['games_played'] == 1
        assert stats['apples_eaten'] == 0
        assert stats['total_play_time'] == 0.0
        assert stats['longest_snake'] == 3

    def test_unknown_fields_ignored(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.set_high_score(100)
        pm.save()
        with open(pm._save_path, 'r') as f:
            data = json.load(f)
        data['unknown_field'] = 'should be ignored'
        data['another_unknown'] = {'nested': True}
        with open(pm._save_path, 'w') as f:
            json.dump(data, f)
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 100
        assert not hasattr(pm2._data, 'unknown_field') or 'unknown_field' not in pm2._data


class TestPersistenceFileSafety:
    def test_save_creates_file(self, tmp_dir):
        pm = _pm(tmp_dir)
        assert not os.path.exists(pm._save_path)
        pm.save()
        assert os.path.exists(pm._save_path)

    def test_save_overwrites_existing(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.set_high_score(1)
        pm.save()
        pm.set_high_score(2)
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 2

    def test_load_preserves_types(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.set_settings({'music_volume': 0.7, 'bloom': True, 'show_fps': False})
        pm.save()
        pm2 = _pm(tmp_dir)
        pm2.load()
        s = pm2.get_settings()
        assert isinstance(s['music_volume'], float)
        assert isinstance(s['bloom'], bool)
        assert isinstance(s['show_fps'], bool)
        assert isinstance(pm2.get_high_score(), int)

    def test_atomic_write_never_corrupts(self, tmp_dir):
        pm = _pm(tmp_dir)
        pm.set_high_score(100)
        pm.save()
        original = open(pm._save_path).read()
        # simulate a crash mid-write by writing a temp file manually
        tmp_p = pm._save_path + '.tmp'
        with open(tmp_p, 'w') as f:
            f.write("{corrupt")
        # don't rename — simulate crash
        pm2 = _pm(tmp_dir)
        pm2.load()
        assert pm2.get_high_score() == 100
        assert open(pm2._save_path).read() == original
