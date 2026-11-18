"""Gestionnaire audio : sons positionnels, boucles d'ambiance, musique en fondu enchaîné."""
import math
import numpy as np
import pygame

from engine.resources import AUDIO_DIR
from audio import synth

MUSIC_A, MUSIC_B, AMBIENCE, RAIN, DRONE, HEART = range(6)
RESERVED = 6


class AudioManager:
    def __init__(self, settings):
        self.settings = settings
        self.sounds = {}
        self.enabled = False
        self.listener_pos = np.zeros(3)
        self.listener_right = np.array([1.0, 0, 0])
        self.music_channel = MUSIC_A
        self.current_music = None
        self.loop_state = {}
        try:
            pygame.mixer.pre_init(synth.SR, -16, 2, 512)
            if not pygame.mixer.get_init():
                pygame.mixer.init(synth.SR, -16, 2, 512)
            pygame.mixer.set_num_channels(40)
            pygame.mixer.set_reserved(RESERVED)
            self.enabled = True
        except pygame.error as e:
            print("[audio] désactivé :", e)

    def load(self, progress=None):
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        names = list(synth.CATALOG.keys())
        for i, name in enumerate(names):
            path = AUDIO_DIR / f"{name}.wav"
            if not path.exists():
                try:
                    synth.write_wav(path, synth.CATALOG[name]())
                except Exception as e:  # ne jamais bloquer le jeu pour un son
                    print("[audio] génération impossible", name, e)
                    continue
            if self.enabled:
                try:
                    self.sounds[name] = pygame.mixer.Sound(str(path))
                except pygame.error:
                    pass
            if progress:
                progress((i + 1) / len(names), f"Audio : {name}")

    # ------------------------------------------------------------------
    @property
    def sfx_vol(self):
        return self.settings["master_volume"] * self.settings["sfx_volume"]

    @property
    def music_vol(self):
        return self.settings["master_volume"] * self.settings["music_volume"]

    def set_listener(self, pos, right):
        self.listener_pos = np.asarray(pos, np.float64)
        self.listener_right = np.asarray(right, np.float64)

    def play(self, name, volume=1.0, pos=None, max_dist=120.0, variants=0):
        if not self.enabled:
            return None
        if variants:
            name = f"{name}_{np.random.randint(0, variants)}"
        snd = self.sounds.get(name)
        if snd is None:
            return None
        left = right = volume * self.sfx_vol
        if pos is not None:
            d = np.asarray(pos) - self.listener_pos
            dist = float(np.linalg.norm(d))
            if dist > max_dist:
                return None
            att = 1.0 / (1.0 + (dist / 8.0) ** 1.6)
            att *= max(0.0, 1.0 - dist / max_dist)
            pan = float(np.dot(d / max(dist, 1e-3), self.listener_right)) if dist > 0.5 else 0.0
            left = volume * self.sfx_vol * att * min(1.0, 1.0 - pan * 0.7)
            right = volume * self.sfx_vol * att * min(1.0, 1.0 + pan * 0.7)
        if max(left, right) < 0.005:
            return None
        ch = pygame.mixer.find_channel(True)
        if ch is None:
            return None
        ch.play(snd)
        ch.set_volume(min(1.0, left), min(1.0, right))
        return ch

    def play_music(self, name, fade_ms=1500):
        if not self.enabled or name == self.current_music:
            return
        snd = self.sounds.get(name)
        old = pygame.mixer.Channel(self.music_channel)
        old.fadeout(fade_ms)
        self.music_channel = MUSIC_B if self.music_channel == MUSIC_A else MUSIC_A
        self.current_music = name
        if snd is None:
            return
        ch = pygame.mixer.Channel(self.music_channel)
        ch.set_volume(self.music_vol)
        ch.play(snd, loops=-1, fade_ms=fade_ms)

    def stop_music(self, fade_ms=800):
        if not self.enabled:
            return
        pygame.mixer.Channel(self.music_channel).fadeout(fade_ms)
        self.current_music = None

    def refresh_volumes(self):
        if not self.enabled:
            return
        pygame.mixer.Channel(self.music_channel).set_volume(self.music_vol)

    def loop(self, channel, name, volume):
        """Maintient une boucle sur un canal réservé avec un volume cible (0 = arrêt progressif)."""
        if not self.enabled:
            return
        ch = pygame.mixer.Channel(channel)
        st = self.loop_state.get(channel)
        vol = max(0.0, min(1.0, volume * self.sfx_vol))
        if vol <= 0.001:
            if st is not None:
                ch.fadeout(400)
                self.loop_state.pop(channel, None)
            return
        if st != name or not ch.get_busy():
            snd = self.sounds.get(name)
            if snd is None:
                return
            ch.play(snd, loops=-1, fade_ms=600)
            self.loop_state[channel] = name
        ch.set_volume(vol)

    def stop_loops(self):
        if not self.enabled:
            return
        for c in (AMBIENCE, RAIN, DRONE, HEART):
            pygame.mixer.Channel(c).fadeout(300)
        self.loop_state.clear()

    def pause_all(self, paused):
        if not self.enabled:
            return
        for c in range(RESERVED, 40):
            ch = pygame.mixer.Channel(c)
            if paused:
                ch.pause()
            else:
                ch.unpause()
