"""Système de particules vectorisé (NumPy) : étincelles, fumée, explosions, rayons, débris.

Format d'instance (12 flottants) : pos(3) axe(3) taille(1) couleur rgba(4) type(1)
Types : 0 lueur additive, 1 fumée, 2 traînée additive, 3 pluie, 4 débris.
"""
import numpy as np

GLOW, SMOKE, STREAK, RAIN, DEBRIS = 0, 1, 2, 3, 4


class ParticleSystem:
    def __init__(self, capacity=4000):
        self.resize(capacity)

    def resize(self, capacity):
        self.cap = int(capacity)
        c = self.cap
        self.alive = np.zeros(c, bool)
        self.pos = np.zeros((c, 3), np.float32)
        self.vel = np.zeros((c, 3), np.float32)
        self.axis = np.zeros((c, 3), np.float32)   # traînée : longueur fixe, orientée selon la vitesse si stretch>0
        self.stretch = np.zeros(c, np.float32)
        self.size = np.zeros(c, np.float32)
        self.grow = np.zeros(c, np.float32)
        self.color = np.zeros((c, 4), np.float32)
        self.life = np.zeros(c, np.float32)
        self.max_life = np.ones(c, np.float32)
        self.kind = np.zeros(c, np.float32)
        self.gravity = np.zeros(c, np.float32)
        self.drag = np.zeros(c, np.float32)
        self.fade_mode = np.zeros(c, np.int8)  # 0 : alpha linéaire, 1 : fondu en fin de vie

    def clear(self):
        self.alive[:] = False

    def _slots(self, n):
        free = np.flatnonzero(~self.alive)
        if len(free) < n:
            # recyclage des plus vieilles particules
            extra = np.argsort(self.life)[: n - len(free)]
            free = np.concatenate([free, extra])
        return free[:n]

    def emit(self, n, pos, vel, size, color, life, kind=GLOW, gravity=0.0, drag=0.0, grow=0.0, stretch=0.0,
             axis=None, fade_mode=0):
        if n <= 0:
            return
        idx = self._slots(n)
        n = len(idx)
        self.alive[idx] = True
        self.pos[idx] = pos
        self.vel[idx] = vel
        self.size[idx] = size
        self.color[idx] = color
        self.life[idx] = life
        self.max_life[idx] = life
        self.kind[idx] = kind
        self.gravity[idx] = gravity
        self.drag[idx] = drag
        self.grow[idx] = grow
        self.stretch[idx] = stretch
        self.axis[idx] = 0.0 if axis is None else axis
        self.fade_mode[idx] = fade_mode

    # ------------------------------------------------------------------
    def burst_sparks(self, p, normal, color=(1.0, 0.6, 0.2), n=14, speed=8.0):
        rng = np.random.default_rng()
        d = rng.normal(size=(n, 3)) * 0.6 + np.asarray(normal)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        v = d * (speed * (0.4 + rng.random((n, 1))))
        c = np.zeros((n, 4), np.float32)
        c[:, :3] = np.asarray(color) * 6.0
        c[:, 3] = 1.0
        self.emit(n, p, v, 0.025, c, 0.25 + rng.random(n) * 0.35, STREAK, gravity=9.0, drag=1.5, stretch=0.035)

    def impact(self, p, normal, color):
        self.burst_sparks(p, normal, color, n=10, speed=6.0)
        c = np.array([*np.asarray(color) * 4.0, 1.0], np.float32)
        self.emit(1, p + np.asarray(normal) * 0.05, np.zeros(3), 0.35, c, 0.12, GLOW, grow=2.0)
        rng = np.random.default_rng()
        sm = np.zeros((3, 4), np.float32)
        sm[:, :3] = 0.25
        sm[:, 3] = 0.35
        v = rng.normal(size=(3, 3)) * 0.4 + np.asarray(normal) * 0.6
        self.emit(3, p, v, 0.15, sm, 0.8 + rng.random(3) * 0.5, SMOKE, drag=1.0, grow=0.8, gravity=-0.3)

    def explosion(self, p, scale=1.0, color=(1.0, 0.55, 0.2)):
        rng = np.random.default_rng()
        p = np.asarray(p, np.float32)
        # boule de feu
        n = int(18 * scale)
        v = rng.normal(size=(n, 3)) * 3.0 * scale
        c = np.zeros((n, 4), np.float32)
        c[:, :3] = np.asarray(color) * (5.0 + rng.random((n, 1)) * 4.0)
        c[:, 3] = 1.0
        self.emit(n, p, v, 0.6 * scale, c, 0.25 + rng.random(n) * 0.35, GLOW, drag=3.0, grow=2.5 * scale)
        # étincelles
        self.burst_sparks(p, (0, 0.5, 0), color, n=int(40 * scale), speed=16.0 * scale)
        # fumée
        n = int(16 * scale)
        v = rng.normal(size=(n, 3)) * 2.0 * scale + np.array([0, 1.2, 0])
        c = np.zeros((n, 4), np.float32)
        g = 0.12 + rng.random((n, 1)) * 0.1
        c[:, :3] = g
        c[:, 3] = 0.6
        self.emit(n, p + rng.normal(size=(n, 3)) * 0.3 * scale, v, 0.7 * scale, c,
                  1.8 + rng.random(n) * 1.6, SMOKE, drag=1.4, grow=1.5 * scale, gravity=-0.4)
        # débris
        n = int(14 * scale)
        v = rng.normal(size=(n, 3)) * 7.0 * scale + np.array([0, 5.0, 0])
        c = np.zeros((n, 4), np.float32)
        c[:, :3] = 0.08
        c[:, 3] = 1.0
        self.emit(n, p, v, 0.07 * scale, c, 1.0 + rng.random(n), DEBRIS, gravity=14.0, drag=0.3)
        # onde de choc lumineuse
        self.emit(1, p, np.zeros(3), 1.0 * scale, np.array([*np.asarray(color) * 3.0, 1.0]), 0.18, GLOW,
                  grow=30.0 * scale)

    def beam(self, a, b, color, width=0.035, life=0.09):
        a = np.asarray(a, np.float32)
        b = np.asarray(b, np.float32)
        mid = (a + b) * 0.5
        half = (b - a) * 0.5
        c = np.array([*np.asarray(color) * 5.0, 1.0], np.float32)
        self.emit(1, mid, np.zeros(3), width, c, life, STREAK, axis=half)
        self.emit(1, mid, np.zeros(3), width * 4.0, np.array([*np.asarray(color) * 0.8, 1.0]), life * 1.4,
                  STREAK, axis=half)

    def smoke_trail(self, p, dense=1.0):
        rng = np.random.default_rng()
        c = np.array([0.08, 0.08, 0.08, 0.5 * dense], np.float32)
        self.emit(1, np.asarray(p) + rng.normal(size=3) * 0.1, rng.normal(size=3) * 0.3 + np.array([0, 0.8, 0]),
                  0.3, c, 1.2, SMOKE, drag=0.8, grow=1.2)
        if rng.random() < 0.5:
            self.emit(1, p, rng.normal(size=3), 0.2, np.array([3.0, 1.2, 0.3, 1.0]), 0.15, GLOW, grow=1.0)

    # ------------------------------------------------------------------
    def update(self, dt, world=None):
        a = self.alive
        if not a.any():
            return
        idx = np.flatnonzero(a)
        self.life[idx] -= dt
        dead = idx[self.life[idx] <= 0]
        self.alive[dead] = False
        idx = np.flatnonzero(self.alive)
        if not len(idx):
            return
        v = self.vel[idx]
        v[:, 1] -= self.gravity[idx] * dt
        v *= np.maximum(0.0, 1.0 - self.drag[idx] * dt)[:, None]
        self.vel[idx] = v
        p = self.pos[idx] + v * dt
        # rebond simple sur le sol
        under = p[:, 1] < 0.02
        if under.any():
            p[under, 1] = 0.02
            vv = self.vel[idx[under]]
            vv[:, 1] *= -0.3
            vv[:, [0, 2]] *= 0.6
            self.vel[idx[under]] = vv
        self.pos[idx] = p
        self.size[idx] += self.grow[idx] * dt

    def instances(self):
        idx = np.flatnonzero(self.alive)
        n = len(idx)
        out = np.zeros((n, 12), np.float32)
        if n == 0:
            return out
        t = self.life[idx] / self.max_life[idx]
        out[:, 0:3] = self.pos[idx]
        st = self.stretch[idx]
        ax = self.axis[idx].copy()
        moving = st > 0
        if moving.any():
            ax[moving] = self.vel[idx][moving] * st[moving, None]
        out[:, 3:6] = ax
        out[:, 6] = self.size[idx]
        col = self.color[idx].copy()
        fade = np.where(self.fade_mode[idx] == 1, np.clip(t * 3.0, 0, 1), t)
        col[:, 3] *= fade
        out[:, 7:11] = col
        out[:, 11] = self.kind[idx]
        return out


class WeatherFX:
    """Pluie en traînées autour de la caméra + poussières en suspension."""

    def __init__(self, rain_count=1800, dust_count=260):
        rng = np.random.default_rng(5)
        self.rain_off = rng.random((rain_count, 3)).astype(np.float32)
        self.rain_speed = (16 + rng.random(rain_count) * 6).astype(np.float32)
        self.dust_off = rng.random((dust_count, 3)).astype(np.float32)
        self.dust_phase = (rng.random(dust_count) * 6.28).astype(np.float32)
        self.box = np.array([44.0, 26.0, 44.0], np.float32)
        self.dust_box = np.array([26.0, 10.0, 26.0], np.float32)
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    def instances(self, cam, env, enabled=True, quality_scale=1.0):
        parts = []
        cam = np.asarray(cam, np.float32)
        if enabled and env.rain > 0.01:
            n = int(len(self.rain_off) * min(1.0, env.rain) * quality_scale)
            off = self.rain_off[:n]
            fall = (self.t * self.rain_speed[:n] / self.box[1]) % 1.0
            rel = off.copy()
            rel[:, 1] = (off[:, 1] - fall) % 1.0
            # positions relatives à une grille fixe pour éviter que la pluie « suive » la caméra
            p = (np.floor(cam / self.box) * self.box) + rel * self.box
            p = np.where(p - cam > self.box / 2, p - self.box, p)
            p = np.where(cam - p > self.box / 2, p + self.box, p)
            p[:, 1] = cam[1] - 8 + rel[:, 1] * self.box[1]
            out = np.zeros((n, 12), np.float32)
            out[:, 0:3] = p
            wind = np.array([1.2, -1.0, 0.6], np.float32)
            wind /= np.linalg.norm(wind)
            out[:, 3:6] = wind * 0.45
            out[:, 6] = 0.012
            lum = 0.35 + 0.65 * (1 - env.night)
            out[:, 7:10] = np.array([0.55, 0.6, 0.68]) * lum
            out[:, 10] = 0.32
            out[:, 11] = RAIN
            parts.append(out)
        if enabled:
            n = int(len(self.dust_off) * quality_scale)
            off = self.dust_off[:n]
            drift = np.stack([np.sin(self.t * 0.13 + self.dust_phase[:n]) * 0.02,
                              (self.t * 0.004) % 1.0 + 0 * off[:, 1],
                              np.cos(self.t * 0.11 + self.dust_phase[:n]) * 0.02], -1)
            rel = (off + drift) % 1.0
            p = (np.floor(cam / self.dust_box) * self.dust_box) + rel * self.dust_box
            p = np.where(p - cam > self.dust_box / 2, p - self.dust_box, p)
            p = np.where(cam - p > self.dust_box / 2, p + self.dust_box, p)
            p[:, 1] = cam[1] - 3 + rel[:, 1] * self.dust_box[1]
            out = np.zeros((n, 12), np.float32)
            out[:, 0:3] = p
            out[:, 6] = 0.025
            sun = np.asarray(env.light_color, np.float32)
            out[:, 7:10] = 0.08 + sun * 0.18
            out[:, 10] = 0.55
            out[:, 11] = GLOW
            parts.append(out)
        if not parts:
            return np.zeros((0, 12), np.float32)
        return np.concatenate(parts)
