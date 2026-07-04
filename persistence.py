"""Save/load game data (high score, settings, stats) to a JSON file."""
import json
import os
import tempfile
import atexit
from datetime import datetime
from config import SAVE_FILENAME, PERSISTENCE_DIR, SCHEMA_VERSION, MUSIC_VOLUME, SFX_VOLUME, AMBIENCE_VOLUME, POST_BLOOM_ENABLED, POST_TONE_MAP_ENABLED, POST_GOD_RAYS_ENABLED, POST_VIGNETTE_ENABLED, POST_FILM_GRAIN_ENABLED


class PersistenceManager:
    def __init__(self, save_dir=None):
        self._data = self._defaults()
        if save_dir is not None:
            self._save_dir = save_dir
        else:
            self._save_dir = self._get_save_dir()
        self._save_path = os.path.join(self._save_dir, SAVE_FILENAME)
        os.makedirs(self._save_dir, exist_ok=True)
        atexit.register(self._atexit_save)

    def _get_save_dir(self):
        if PERSISTENCE_DIR is not None:
            return PERSISTENCE_DIR
        try:
            import platformdirs
            return platformdirs.user_data_dir('snakev2', ensure_exists=True)
        except ImportError:
            return os.path.expanduser('~/.snakev2/')

    def _defaults(self):
        return {
            'schema_version': SCHEMA_VERSION,
            'high_score': 0,
            'top_scores': [],
            'settings': {
                'music_volume': MUSIC_VOLUME,
                'sfx_volume': SFX_VOLUME,
                'ambience_volume': AMBIENCE_VOLUME,
                'bloom': POST_BLOOM_ENABLED,
                'tone_map': POST_TONE_MAP_ENABLED,
                'god_rays': POST_GOD_RAYS_ENABLED,
                'vignette': POST_VIGNETTE_ENABLED,
                'film_grain': POST_FILM_GRAIN_ENABLED,
                'show_fps': False,
            },
            'stats': {
                'games_played': 0,
                'apples_eaten': 0,
                'total_play_time': 0.0,
                'longest_snake': 3,
            },
        }

    def load(self):
        if not os.path.exists(self._save_path):
            self._data = self._defaults()
            return

        try:
            with open(self._save_path, 'r') as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            self._data = self._defaults()
            self._overwrite_corrupt()
            return

        if not isinstance(raw, dict):
            self._data = self._defaults()
            self._overwrite_corrupt()
            return

        schema = raw.get('schema_version', 0)
        if not isinstance(schema, int) or schema < 1 or schema > SCHEMA_VERSION:
            self._data = self._defaults()
            self._overwrite_corrupt()
            return

        cleaned = self._defaults()
        cleaned['high_score'] = self._validate_int(raw.get('high_score'), 0, 0, 9999999)

        raw_scores = raw.get('top_scores', [])
        if isinstance(raw_scores, list):
            validated = []
            for entry in raw_scores:
                if isinstance(entry, dict) and isinstance(entry.get('score'), (int, float)):
                    validated.append({
                        'score': int(entry['score']),
                        'date': str(entry.get('date', datetime.now().isoformat())),
                    })
                    if len(validated) >= 5:
                        break
            validated.sort(key=lambda x: x['score'], reverse=True)
            cleaned['top_scores'] = validated[:5]

        raw_settings = raw.get('settings', {})
        if isinstance(raw_settings, dict):
            for key, default in cleaned['settings'].items():
                val = raw_settings.get(key)
                if isinstance(val, type(default)):
                    cleaned['settings'][key] = val

        raw_stats = raw.get('stats', {})
        if isinstance(raw_stats, dict):
            cleaned['stats']['games_played'] = self._validate_int(raw_stats.get('games_played'), 0, 0, 999999)
            cleaned['stats']['apples_eaten'] = self._validate_int(raw_stats.get('apples_eaten'), 0, 0, 999999999)
            cleaned['stats']['total_play_time'] = self._validate_float(raw_stats.get('total_play_time'), 0.0, 0.0, 1e9)
            cleaned['stats']['longest_snake'] = self._validate_int(raw_stats.get('longest_snake'), 3, 0, 9999)

        self._data = cleaned

    def _validate_int(self, val, default, lo, hi):
        if isinstance(val, int) and lo <= val <= hi:
            return val
        if isinstance(val, float) and lo <= int(val) <= hi:
            return int(val)
        return default

    def _validate_float(self, val, default, lo, hi):
        if isinstance(val, (int, float)) and lo <= val <= hi:
            return float(val)
        return default

    def _overwrite_corrupt(self):
        try:
            self.save()
        except Exception:
            pass

    def save(self):
        self._data['schema_version'] = SCHEMA_VERSION
        fd, tmp_path = tempfile.mkstemp(dir=self._save_dir, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp_path, self._save_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise

    def _atexit_save(self):
        try:
            self.save()
        except Exception:
            pass

    def get_high_score(self):
        return self._data['high_score']

    def set_high_score(self, score):
        score = int(score)
        if score > self._data['high_score']:
            self._data['high_score'] = score

    def add_score(self, score):
        score = int(score)
        if score > self._data['high_score']:
            self._data['high_score'] = score
        self._data['top_scores'].append({
            'score': score,
            'date': datetime.now().isoformat(),
        })
        self._data['top_scores'].sort(key=lambda x: x['score'], reverse=True)
        self._data['top_scores'] = self._data['top_scores'][:5]

    def record_game(self, score, apples, duration, length):
        self._data['stats']['games_played'] += 1
        self._data['stats']['apples_eaten'] += apples
        self._data['stats']['total_play_time'] += duration
        if length > self._data['stats']['longest_snake']:
            self._data['stats']['longest_snake'] = length
        self.add_score(score)

    def get_stats(self):
        return dict(self._data['stats'])

    def get_top_scores(self):
        return list(self._data['top_scores'])

    def get_settings(self):
        return dict(self._data['settings'])

    def set_settings(self, settings):
        self._data['settings'] = dict(settings)
