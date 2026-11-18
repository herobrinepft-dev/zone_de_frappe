"""Drones d'entraînement fictifs : vol, évitement d'obstacles, tirs d'impulsions."""
import math
import numpy as np

from gameplay.data import DRONES

SHELL_TINT = {"eclaireur": (0.9, 0.9, 0.88), "sentinelle": (0.38, 0.43, 0.5), "blinde": (0.32, 0.31, 0.27)}


class Drone:
    _next_id = 0

    def __init__(self, kind, pos, difficulty, rng):
        Drone._next_id += 1
        self.id = Drone._next_id
        self.kind = kind
        self.d = DRONES[kind]
        self.pos = np.array(pos, np.float64)
        self.vel = np.zeros(3)
        self.max_hp = self.d["hp"] * difficulty["health"]
        self.hp = self.max_hp
        self.radius = self.d["radius"]
        self.alive = True
        self.dying = False
        self.dead = False
        self.die_timer = 0.0
        self.spin = 0.0
        self.rng = rng
        self.orbit_dir = 1 if rng.random() < 0.5 else -1
        self.alt = rng.uniform(*self.d["alt"])
        self.fire_cd = rng.uniform(1.5, 3.5)
        self.burst_left = 0
        self.burst_cd = 0.0
        self.los = False
        self.los_timer = rng.random() * 0.3
        self.yaw = 0.0
        self.tilt_x = 0.0
        self.tilt_z = 0.0
        self.rotor = rng.random() * 6.28
        self.flash = 0.0
        self.dive = 0.0
        self.dive_cd = rng.uniform(4, 9)
        self.retarget = 0.0
        self.offset = rng.normal(size=3) * np.array([1, 0.3, 1])
        self.difficulty = difficulty
        self.arrival = 1.0      # entrée en scène (descente)
        self.wobble = rng.random() * 10

    @property
    def tint(self):
        return SHELL_TINT[self.kind]

    @property
    def light_color(self):
        return self.d["color"]

    def damage(self, amount):
        if not self.alive:
            return False
        self.hp -= amount
        self.flash = 1.0
        if self.hp <= 0:
            self.alive = False
            self.dying = True
            self.die_timer = 0.0
            self.spin = self.rng.uniform(4, 9) * (1 if self.rng.random() < 0.5 else -1)
            self.vel += self.rng.normal(size=3) * 2 + np.array([0, 2.0, 0])
            return True
        return False

    def update(self, dt, session):
        world = session.world
        self.rotor += dt * (60.0 if not self.dying else 20.0)
        self.flash = max(0.0, self.flash - dt * 6.0)
        if self.dying:
            self.die_timer += dt
            self.vel[1] -= 16.0 * dt
            self.yaw += self.spin * dt
            self.tilt_z += self.spin * 0.3 * dt
            self.pos += self.vel * dt
            if self.rng.random() < 0.7:
                session.particles.smoke_trail(self.pos.copy())
            p2, hit = world.push_sphere(self.pos, self.radius * 0.6)
            if hit or self.die_timer > 2.0:
                self.pos = p2
                self.dead = True
            return

        player = session.player
        target = player.eye
        to = target - self.pos
        dist = float(np.linalg.norm(to))
        flat = np.array([to[0], 0.0, to[2]])
        fd = np.linalg.norm(flat)
        flat = flat / fd if fd > 1e-6 else np.array([1.0, 0, 0])

        # position désirée : orbite autour du joueur à distance préférée
        self.retarget -= dt
        if self.retarget <= 0:
            self.retarget = self.rng.uniform(2.0, 4.0)
            if self.rng.random() < 0.25:
                self.orbit_dir *= -1
            self.offset = self.rng.normal(size=3) * np.array([4.0, 1.5, 4.0])
        tangent = np.array([-flat[2], 0.0, flat[0]]) * self.orbit_dir
        pref = self.d["pref_dist"]
        desired = target - flat * pref + tangent * 8.0 + self.offset
        ground = world.max_height_near(desired[0], desired[2], 5.0)
        alt = self.alt
        desired[1] = max(target[1] + alt * 0.6, ground + 3.5, 4.0) if ground < 25 else max(ground + 4.0, target[1] + alt)

        # éclaireur : piqués agressifs vers le joueur
        if self.kind == "eclaireur":
            self.dive_cd -= dt
            if self.dive_cd <= 0 and self.dive <= 0 and dist < 45 and self.los:
                self.dive = 1.6
                self.dive_cd = self.rng.uniform(6, 11)
            if self.dive > 0:
                self.dive -= dt
                desired = target + np.array([0, 3.0, 0]) + tangent * 3.0

        # entrée en scène : descente rapide depuis l'altitude d'apparition
        speed = self.d["speed"] * (1.5 if self.dive > 0 else 1.0)
        if self.arrival > 0:
            self.arrival = max(0.0, self.arrival - dt * 0.4)
            speed *= 1.4

        to_d = desired - self.pos
        dd = float(np.linalg.norm(to_d))
        want = to_d / max(dd, 1e-6) * speed * min(1.0, dd / 6.0)

        # évitement d'obstacles par sondage devant
        vlen = np.linalg.norm(self.vel)
        if vlen > 0.5:
            look = self.vel / vlen
            t, n = world.raycast(self.pos, look, 4.0 + vlen * 0.6, ground=True)
            if t is not None:
                push = (1.0 - t / (4.0 + vlen * 0.6))
                want += (n * 8.0 + np.array([0, 10.0, 0])) * push
        # séparation entre drones
        for o in session.drones:
            if o is self or not o.alive:
                continue
            d = self.pos - o.pos
            dl = float(np.dot(d, d))
            if dl < 16.0 and dl > 1e-6:
                want += d / math.sqrt(dl) * (4.0 - math.sqrt(dl)) * 1.5

        steer = 2.2 if self.kind != "blinde" else 1.4
        self.vel += (want - self.vel) * min(1.0, dt * steer)
        self.wobble += dt
        bob = np.array([math.sin(self.wobble * 1.3), math.sin(self.wobble * 2.1) * 0.6, math.cos(self.wobble * 1.7)]) * 0.25
        self.pos += (self.vel + bob) * dt
        self.pos, hit = world.push_sphere(self.pos, self.radius)
        lim = world.half - 2.0
        self.pos[0] = min(lim, max(-lim, self.pos[0]))
        self.pos[2] = min(lim, max(-lim, self.pos[2]))
        self.pos[1] = min(self.pos[1], 95.0)

        # orientation : face au joueur, inclinaison selon la vitesse
        self.yaw = math.atan2(to[0], -to[2])
        right = np.array([math.cos(self.yaw), 0, math.sin(self.yaw)])
        fwd = np.array([math.sin(self.yaw), 0, -math.cos(self.yaw)])
        self.tilt_x += (-float(np.dot(self.vel, fwd)) * 0.04 - self.tilt_x) * min(1, dt * 4)
        self.tilt_z += (-float(np.dot(self.vel, right)) * 0.04 - self.tilt_z) * min(1, dt * 4)

        # ligne de vue (coûteuse : calculée à intervalle)
        self.los_timer -= dt
        if self.los_timer <= 0:
            self.los_timer = 0.25
            self.los = dist < self.d["fire_range"] and world.line_of_sight(self.pos, target)

        # tir
        self.fire_cd -= dt
        if self.burst_left > 0:
            self.burst_cd -= dt
            if self.burst_cd <= 0 and self.los:
                self._fire(session, target, dist)
                self.burst_left -= 1
                self.burst_cd = 0.18
        elif self.fire_cd <= 0 and self.los and self.arrival <= 0.2:
            self.burst_left = self.d["burst"]
            self.burst_cd = 0.0
            agg = 1.0 + 0.04 * session.waves.wave
            self.fire_cd = self.rng.uniform(0.8, 1.3) / (self.d["fire_rate"] * agg)

    def _fire(self, session, target, dist):
        player = session.player
        speed = self.d["proj_speed"]
        lead = min(1.0, 0.35 + 0.1 * session.waves.wave)
        t = dist / speed
        aim = target - np.array([0, 0.25, 0]) + player.vel * t * lead
        spread = 0.03 + 0.02 * (dist / 60.0)
        d = aim - self.pos
        d /= np.linalg.norm(d)
        d += self.rng.normal(size=3) * spread
        d /= np.linalg.norm(d)
        muzzle = self.pos + d * (self.radius + 0.3)
        session.spawn_projectile(muzzle, d * speed, self.d["damage"] * self.difficulty["damage"],
                                 self.d["color"], self.d.get("splash", 0.0), big=self.kind == "blinde")
