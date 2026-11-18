"""Cycle jour/nuit et paramètres d'éclairage/brouillard en fonction de la météo."""
import math
import numpy as np

from engine.mathutils import smoothstep, normalize

# (élévation solaire en degrés, zénith, horizon, couleur soleil, intensité soleil)
_KEYS = [
    (-18, (0.004, 0.006, 0.016), (0.012, 0.016, 0.03), (0.0, 0.0, 0.0), 0.0),
    (-6, (0.02, 0.03, 0.08), (0.12, 0.08, 0.12), (0.6, 0.3, 0.2), 0.0),
    (0, (0.10, 0.16, 0.35), (0.85, 0.42, 0.22), (1.0, 0.45, 0.2), 1.2),
    (6, (0.16, 0.28, 0.55), (0.95, 0.62, 0.4), (1.0, 0.62, 0.35), 2.4),
    (15, (0.18, 0.36, 0.72), (0.7, 0.72, 0.78), (1.0, 0.85, 0.65), 3.2),
    (35, (0.15, 0.36, 0.8), (0.58, 0.7, 0.86), (1.0, 0.95, 0.88), 3.8),
    (90, (0.12, 0.32, 0.78), (0.55, 0.68, 0.86), (1.0, 0.97, 0.92), 4.0),
]


def _interp(elev):
    if elev <= _KEYS[0][0]:
        k = _KEYS[0]
        return np.array(k[1]), np.array(k[2]), np.array(k[3]), k[4]
    for a, b in zip(_KEYS, _KEYS[1:]):
        if elev <= b[0]:
            t = (elev - a[0]) / (b[0] - a[0])
            t = t * t * (3 - 2 * t)
            lerp = lambda x, y: np.array(x) * (1 - t) + np.array(y) * t
            return lerp(a[1], b[1]), lerp(a[2], b[2]), lerp(a[3], b[3]), a[4] * (1 - t) + b[4] * t
    k = _KEYS[-1]
    return np.array(k[1]), np.array(k[2]), np.array(k[3]), k[4]


class Environment:
    """État atmosphérique courant transmis au renderer."""

    def __init__(self):
        self.hour = 17.5
        self.cloud_cover = 0.35
        self.fog_base = 0.004
        self.rain = 0.0          # intensité de pluie 0..1
        self.wetness = 0.0
        self.wind = 1.0
        self.lightning = 0.0
        self.time_speed = 1.0 / 240.0  # heures de jeu par seconde
        self.update(0.0)

    def configure(self, hour, clouds, fog, rain):
        self.hour = hour
        self.cloud_cover = clouds
        self.fog_base = fog
        self.rain = rain
        self.wetness = 1.0 if rain > 0 else 0.0
        self.update(0.0)

    def update(self, dt):
        self.hour = (self.hour + dt * self.time_speed) % 24.0
        if self.rain > 0:
            self.wetness = min(1.0, self.wetness + dt * 0.05)
        else:
            self.wetness = max(0.0, self.wetness - dt * 0.01)
        self.lightning = max(0.0, self.lightning - dt * 4.0)
        # trajectoire solaire : lever 6 h, coucher 18 h
        ang = (self.hour - 6.0) / 12.0 * math.pi
        elev = math.sin(ang) * 62.0
        az = ang
        el_r = math.radians(elev)
        self.true_sun = normalize(np.array([math.cos(az) * math.cos(el_r), math.sin(el_r),
                                            0.35 * math.cos(el_r) + 0.2]))
        zen, hor, sunc, inten = _interp(elev)
        self.night = 1.0 - smoothstep(-10.0, 2.0, elev)
        cov = self.cloud_cover
        overcast = smoothstep(0.55, 1.0, cov)
        grey = np.array([0.45, 0.48, 0.52]) * (0.15 + 0.85 * (1 - self.night))
        zen = zen * (1 - overcast * 0.7) + grey * 0.6 * overcast
        hor = hor * (1 - overcast * 0.6) + grey * 0.75 * overcast
        inten *= (1.0 - 0.75 * overcast)
        # lumière principale : soleil le jour, lune la nuit
        if elev > -3.0:
            self.light_dir = self.true_sun.copy()
            if self.light_dir[1] < 0.08:
                self.light_dir[1] = 0.08
                self.light_dir = normalize(self.light_dir)
            self.light_color = sunc * inten
        else:
            moon = normalize(np.array([-self.true_sun[0], abs(self.true_sun[1]) + 0.35, -self.true_sun[2]]))
            self.light_dir = moon
            self.light_color = np.array([0.32, 0.42, 0.7]) * 0.32 * (1 - overcast * 0.6)
        # fondu doux entre soleil et lune autour du crépuscule
        if -3.0 < elev < 2.0:
            self.light_color = self.light_color * smoothstep(-3.0, 2.0, elev)
        self.zenith = zen
        self.horizon = hor
        self.ground = hor * 0.35 + np.array([0.02, 0.02, 0.02])
        self.sun_elev = elev
        fog = self.fog_base + self.rain * 0.006 + overcast * 0.002
        self.fog_density = fog
        self.fog_color = hor * 0.9 + zen * 0.1
        if self.night > 0.5:
            self.fog_color = self.fog_color + np.array([0.01, 0.012, 0.02])
        light_boost = self.lightning
        self.ambient = 0.5 + 0.35 * self.night + 0.25 * overcast + light_boost * 3.0
        self.window_lights = 1.0 - smoothstep(-6.0, 8.0, elev)
        self.lamp_glow = 0.25 + 2.75 * (1.0 - smoothstep(-4.0, 6.0, elev))
        self.exposure = 1.0 + 1.1 * self.night + overcast * 0.3
