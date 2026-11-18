"""Objets ramassables : kit de réparation, surcharge, module de données."""
import math
import numpy as np

PICKUP_INFO = {
    "repair": dict(model="repair_kit", color=(0.2, 1.0, 0.35), label="RÉPARATION"),
    "overcharge": dict(model="overcharge", color=(1.0, 0.55, 0.1), label="SURCHARGE"),
    "data": dict(model="data_core", color=(0.2, 0.8, 1.0), label="DONNÉES"),
}


class Pickup:
    def __init__(self, kind, pos, life=None):
        self.kind = kind
        self.info = PICKUP_INFO[kind]
        self.base = np.array(pos, np.float64)
        self.pos = self.base.copy()
        self.t = np.random.random() * 6.0
        self.life = life
        self.collected = False

    def update(self, dt):
        self.t += dt
        self.pos = self.base + np.array([0, 0.9 + math.sin(self.t * 2.2) * 0.15, 0])
        if self.life is not None:
            self.life -= dt
            if self.life <= 0:
                self.collected = True

    @property
    def yaw(self):
        return self.t * 1.6
