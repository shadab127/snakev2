import math
import struct
import time
import pygame
from config import *


class AudioManager:
    def __init__(self):
        self._ok = False
        self._init_mixer()
        if not self._ok:
            return

        self.music_day_channel = pygame.mixer.Channel(0)
        self.music_night_channel = pygame.mixer.Channel(1)
        self.sfx_channel = pygame.mixer.Channel(2)
        self.ambience_channel = pygame.mixer.Channel(3)

        self.muted = False
        self.music_volume = MUSIC_VOLUME
        self.sfx_volume = SFX_VOLUME
        self.ambience_volume = AMBIENCE_VOLUME

        self._last_slither_time = 0.0
        self._current_day_cycle = 0.0
        self._current_snake_speed = 0.0
        self._music_update_timer = 0.0
        self._duck_timer = 0.0

        self._sounds = {}
        self._generate_all_sounds()

        self.ambience_channel.play(self._sounds['ambient'], loops=-1)
        self.ambience_channel.set_volume(self.ambience_volume)

        self.music_day_channel.play(self._sounds['music_day'], loops=-1)
        self.music_night_channel.play(self._sounds['music_night'], loops=-1)
        self.music_day_channel.set_volume(self.music_volume)
        self.music_night_channel.set_volume(0.0)

    def _init_mixer(self):
        try:
            if pygame.mixer.get_init():
                return
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(8)
            self._ok = True
        except pygame.error:
            self._ok = False

    def _make_sound(self, samples_func, duration):
        sr = 22050
        n = int(sr * duration)
        buf = bytearray()
        for i in range(n):
            t = i / sr
            l, r = samples_func(t)
            l = max(-1.0, min(1.0, l))
            r = max(-1.0, min(1.0, r))
            buf.extend(struct.pack('<hh', int(l * 32767), int(r * 32767)))
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _mono(self, mono_func, duration):
        return self._make_sound(lambda t: (mono_func(t), mono_func(t)), duration)

    def _env_exp(self, t, dur, k=4.0):
        if t >= dur:
            return 0.0
        return math.exp(-k * t / dur)

    def _noise(self, t, seed=0):
        x = int((t * 10000 + seed * 1000))
        x = ((x << 13) ^ x) & 0x7FFFFFFF
        x = ((x * (x * x * 15731 + 789221) + 1376312589) & 0x7FFFFFFF)
        return x / 0x40000000 - 1.0

    def _window(self, t, dur):
        fade = 0.04
        if t < fade:
            return t / fade
        if t > dur - fade:
            return (dur - t) / fade
        return 1.0

    def _generate_all_sounds(self):
        self._sounds['eat'] = self._mono(lambda t: (
            math.sin(2 * math.pi * 880 * t) * 0.5 +
            math.sin(2 * math.pi * 1320 * t) * 0.3
        ) * self._env_exp(t, 0.12, 6), 0.15)

        self._sounds['slither'] = self._mono(lambda t: (
            math.sin(2 * math.pi * 110 * t + math.sin(2 * math.pi * 20 * t) * 2) *
            self._env_exp(t, 0.08, 8) * 0.2
        ), 0.1)

        self._sounds['death'] = self._mono(lambda t: (
            math.sin(2 * math.pi * (440 * t - 330 * t * t)) * 0.5 +
            self._noise(t) * 0.15 * min(1.0, t * 10) *
            max(0.0, 1.0 - abs(t - 0.3) * 4)
        ) * self._env_exp(t, 0.5, 3), 0.5)

        self._sounds['ui_click'] = self._mono(lambda t: (
            math.sin(2 * math.pi * 2500 * t) * self._env_exp(t, 0.015, 15) * 0.4
        ), 0.025)

        self._sounds['score_chime'] = self._mono(lambda t: (
            self._arpeggio(t, [262, 330, 392, 523], 0.35)
        ), 0.4)

        self._sounds['ambient'] = self._make_sound(lambda t: (
            self._ambient_func(t, 0) * 0.3,
            self._ambient_func(t, 50) * 0.3
        ), 3.0)

        self._sounds['music_day'] = self._mono(lambda t: (
            self._music_tone(t, True) * self._window(t, 4.0)
        ), 4.0)

        self._sounds['music_night'] = self._mono(lambda t: (
            self._music_tone(t, False) * self._window(t, 4.0)
        ), 4.0)

    def _arpeggio(self, t, notes, duration):
        nlen = duration / len(notes)
        idx = int(t / nlen) % len(notes)
        local_t = t - idx * nlen
        freq = notes[idx]
        fade = min(0.02, nlen * 0.3)
        if local_t < fade:
            env = local_t / fade
        elif local_t > nlen - fade:
            env = (nlen - local_t) / fade
        else:
            env = 1.0
        return math.sin(2 * math.pi * freq * local_t) * env * 0.4

    def _ambient_func(self, t, seed):
        val = 0.0
        freqs = [55, 88, 120, 180]
        for i, f in enumerate(freqs):
            fm = math.sin(2 * math.pi * 0.08 * (t + seed * 0.01 + i)) * 10
            val += math.sin(2 * math.pi * (f + fm) * t + i * 1.3 + seed * 0.01) * (0.12 - i * 0.02)
        val += self._noise(t, seed) * 0.015
        return val

    def _music_tone(self, t, is_day):
        if is_day:
            bass_f = 65.0
            pad_fs = [261, 329, 392]
            arp_fs = [523, 659, 784, 1047]
            amp = 0.3
        else:
            bass_f = 55.0
            pad_fs = [220, 261, 329]
            arp_fs = [440, 523, 659, 784]
            amp = 0.25

        val = 0.0
        val += math.sin(2 * math.pi * bass_f * t) * 0.15
        val += math.sin(2 * math.pi * bass_f * 2 * t) * 0.03

        for i, f in enumerate(pad_fs):
            lfo = math.sin(2 * math.pi * 0.15 * t + i * 2.1) * 0.08
            val += math.sin(2 * math.pi * (f + lfo * 5) * t) * 0.04

        arp_len = 2.0
        nlen = arp_len / len(arp_fs)
        idx = int(t / nlen) % len(arp_fs)
        local_t = t - idx * nlen
        val += math.sin(2 * math.pi * arp_fs[idx] * local_t) * self._env_exp(local_t, nlen, 3) * 0.06

        return val * amp

    def play_eat(self):
        if not self._ok or self.muted:
            return
        self.sfx_channel.play(self._sounds['eat'])

    def play_slither(self, speed_ratio=0.5):
        if not self._ok or self.muted:
            return
        now = time.time()
        cooldown = max(0.05, 0.15 - speed_ratio * 0.1)
        if now - self._last_slither_time < cooldown:
            return
        self._last_slither_time = now
        self.sfx_channel.play(self._sounds['slither'])

    def play_death(self):
        if not self._ok or self.muted:
            return
        self.sfx_channel.play(self._sounds['death'])
        self._duck_timer = AUDIO_FADE_TIME

    def play_ui_click(self):
        if not self._ok or self.muted:
            return
        self.sfx_channel.play(self._sounds['ui_click'])

    def play_score_chime(self):
        if not self._ok or self.muted:
            return
        self.sfx_channel.play(self._sounds['score_chime'])

    def toggle_mute(self):
        if not self._ok:
            return False
        self.muted = not self.muted
        if self.muted:
            self.sfx_channel.set_volume(0)
            self.ambience_channel.set_volume(0)
            self.music_day_channel.set_volume(0)
            self.music_night_channel.set_volume(0)
        else:
            self.sfx_channel.set_volume(self.sfx_volume)
            self.ambience_channel.set_volume(self.ambience_volume)
            day_factor = (self._current_day_cycle + 1) * 0.5
            vol = self.music_volume
            self.music_day_channel.set_volume(vol * day_factor)
            self.music_night_channel.set_volume(vol * (1.0 - day_factor))
        return self.muted

    def update(self, day_cycle, snake_speed, dt):
        if not self._ok:
            return
        self._current_day_cycle = day_cycle
        self._current_snake_speed = snake_speed

        day_factor = (day_cycle + 1) * 0.5
        speed_boost = 1.0 + snake_speed * 0.3
        base_vol = min(1.0, self.music_volume * speed_boost)

        if self._duck_timer > 0:
            self._duck_timer -= dt
            duck = 0.3 if self._duck_timer > 0 else 1.0
            vol = base_vol * duck * (0.0 if self.muted else 1.0)
            self.music_day_channel.set_volume(vol * day_factor)
            self.music_night_channel.set_volume(vol * (1.0 - day_factor))
        else:
            self._music_update_timer += dt
            if self._music_update_timer >= 1.0:
                self._music_update_timer -= 1.0
                vol = base_vol * (0.0 if self.muted else 1.0)
                self.music_day_channel.set_volume(vol * day_factor)
                self.music_night_channel.set_volume(vol * (1.0 - day_factor))

        self.ambience_channel.set_volume(
            self.ambience_volume * (0.0 if self.muted else 1.0)
        )

    def pause(self):
        if not self._ok:
            return
        self.sfx_channel.set_volume(0)
        self.ambience_channel.set_volume(0)
        self.music_day_channel.set_volume(self.music_day_channel.get_volume() * 0.15)
        self.music_night_channel.set_volume(self.music_night_channel.get_volume() * 0.15)

    def resume(self):
        if not self._ok or self.muted:
            return
        self.sfx_channel.set_volume(self.sfx_volume)
        self.ambience_channel.set_volume(self.ambience_volume)
        day_factor = (self._current_day_cycle + 1) * 0.5
        speed_boost = 1.0 + self._current_snake_speed * 0.3
        vol = min(1.0, self.music_volume * speed_boost)
        self.music_day_channel.set_volume(vol * day_factor)
        self.music_night_channel.set_volume(vol * (1.0 - day_factor))

    def fade_out_music(self, duration=0.5):
        if not self._ok:
            return
        self.music_day_channel.fadeout(int(duration * 1000))
        self.music_night_channel.fadeout(int(duration * 1000))
