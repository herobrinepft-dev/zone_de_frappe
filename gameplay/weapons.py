"""État d'un émetteur pendant la partie : cadence, chauffe, dispersion, recul."""
import math
import numpy as np


class WeaponState:
    def __init__(self, wid, stats, beam_color, finish_color):
        self.id = wid
        self.s = stats
        self.beam_color = np.array(beam_color)
        self.finish_color = finish_color
        self.cooldown = 0.0
        self.heat = 0.0
        self.overheated = False
        self.spread_bonus = 0.0
        self.recoil = 0.0        # animation du modèle
        self.kick = 0.0          # recul angulaire appliqué à la caméra
        self.muzzle_flash = 0.0
        self.overcharge = 0.0    # bonus temporaire (cadence x1.6, pas de chauffe)
        self.events = []

    def update(self, dt):
        self.events.clear()
        self.cooldown = max(0.0, self.cooldown - dt)
        cool = self.s["cool"] * (1.6 if self.overheated else 1.0)
        if self.cooldown <= 0.0 or self.overheated:
            self.heat = max(0.0, self.heat - cool * dt)
        if self.overheated and self.heat <= 0.25:
            self.overheated = False
            self.events.append("ready")
        self.spread_bonus = max(0.0, self.spread_bonus - dt * 0.08)
        self.recoil = max(0.0, self.recoil - dt * 6.0)
        self.muzzle_flash = max(0.0, self.muzzle_flash - dt)
        self.overcharge = max(0.0, self.overcharge - dt)

    def try_fire(self, trigger_held, trigger_pressed, moving, aiming, rng):
        """Renvoie une liste de directions locales (déviations) si un tir part, sinon []."""
        if self.overheated or self.cooldown > 0:
            return []
        if not (trigger_pressed or (trigger_held and self.s["auto"])):
            return []
        rate = self.s["rate"] * (1.6 if self.overcharge > 0 else 1.0)
        self.cooldown = 1.0 / rate
        if self.overcharge <= 0:
            self.heat += self.s["heat"]
        if self.heat >= 1.0:
            self.heat = 1.0
            self.overheated = True
            self.events.append("overheat")
        base = self.s["spread"] * (0.45 if aiming else 1.0) + self.spread_bonus
        if moving:
            base += 0.012 if not aiming else 0.004
        devs = []
        for _ in range(int(self.s["pellets"])):
            r = math.sqrt(rng.random()) * base
            a = rng.random() * 2 * math.pi
            devs.append((math.cos(a) * r, math.sin(a) * r))
        self.spread_bonus = min(0.04, self.spread_bonus + self.s["recoil"] * 0.25)
        self.recoil = 1.0
        self.kick += self.s["recoil"] * (0.55 if aiming else 1.0)
        self.muzzle_flash = 0.05
        self.events.append("fire")
        return devs

    @property
    def current_spread(self):
        return self.s["spread"] + self.spread_bonus
