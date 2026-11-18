"""Orbes d'énergie tirés par les drones (projectiles visibles et esquivables)."""
import numpy as np


class Projectile:
    def __init__(self, pos, vel, damage, color, splash=0.0, big=False):
        self.pos = np.array(pos, np.float64)
        self.vel = np.array(vel, np.float64)
        self.damage = damage
        self.color = np.array(color)
        self.splash = splash
        self.big = big
        self.life = 4.0
        self.dead = False
        self.size = 0.32 if big else 0.18

    def update(self, dt, session):
        old = self.pos.copy()
        step = self.vel * dt
        self.pos = self.pos + step
        self.life -= dt
        if self.life <= 0:
            self.dead = True
            return
        player = session.player
        # collision joueur : distance segment / axe du joueur
        c = player.center
        seg = self.pos - old
        sl = float(np.dot(seg, seg))
        t = 0.0 if sl < 1e-9 else max(0.0, min(1.0, float(np.dot(c - old, seg)) / sl))
        closest = old + seg * t
        dvec = closest - c
        hr = player.height * 0.5
        dy = max(0.0, abs(dvec[1]) - hr + 0.4)
        if dvec[0] ** 2 + dvec[2] ** 2 + dy * dy < (0.45 + self.size) ** 2:
            session.player_hit(self.damage, old, self)
            self.dead = True
            session.particles.impact(closest, -seg / max(np.sqrt(sl), 1e-6), self.color)
            return
        # collision décor
        d = np.linalg.norm(seg)
        if d > 1e-6:
            th, n = session.world.raycast(old, seg / d, d)
            if th is not None:
                hit = old + seg / d * th
                self.dead = True
                session.particles.impact(hit, n, self.color)
                session.audio_event("impact", hit, 0.6)
                if self.splash > 0:
                    dist = float(np.linalg.norm(player.center - hit))
                    if dist < self.splash:
                        session.player_hit(self.damage * (1 - dist / self.splash) * 0.7, hit, self)
                    session.particles.explosion(hit, 0.5, self.color)
