"""Directeur de vagues et missions (élimination, défense de balise, collecte)."""
import math
import numpy as np

from gameplay.data import WAVE_PLAN, TOTAL_WAVES, MISSION_TEXT
from entities.drone import Drone
from entities.pickup import Pickup

INTERMISSION = 9.0


class WaveDirector:
    def __init__(self, session, rng):
        self.s = session
        self.rng = rng
        self.wave = 0
        self.state = "intermission"
        self.timer = 6.0
        self.queue = []
        self.spawn_cd = 0.0
        self.mission = None
        self.beacon = None          # position
        self.beacon_progress = 0.0
        self.beacon_tick = 0.0
        self.cores = []             # Pickup de type data
        self.cores_total = 0
        self.wave_kills = 0
        self.wave_total = 0
        self.wave_time = 0.0
        self.victory = False

    # ------------------------------------------------------------------
    @property
    def objective(self):
        if self.state == "intermission":
            if self.wave == 0:
                return "Préparez-vous : premier contact imminent", None
            return f"Vague {self.wave} terminée — réapprovisionnez-vous", None
        if self.state == "done":
            return "Opération terminée", None
        if self.mission == "elimination":
            alive = sum(1 for d in self.s.drones if d.alive)
            left = alive + len(self.queue)
            return f"Neutraliser les drones — {left} restant{'s' if left > 1 else ''}", \
                1.0 - left / max(1, self.wave_total)
        if self.mission == "defense":
            near = self.beacon is not None and self.player_in_zone()
            txt = "Capturer la balise — " + ("capture en cours" if near else "rejoignez la zone")
            return txt, self.beacon_progress
        got = self.cores_total - sum(1 for c in self.cores if not c.collected)
        return f"Récupérer les modules de données — {got}/{self.cores_total}", got / max(1, self.cores_total)

    def player_in_zone(self):
        p = self.s.player.pos
        return self.beacon is not None and (p[0] - self.beacon[0]) ** 2 + (p[2] - self.beacon[2]) ** 2 < 7.0 ** 2 \
            and p[1] < self.beacon[1] + 4.0

    def waypoints(self):
        out = []
        if self.state == "active":
            if self.mission == "defense" and self.beacon is not None:
                out.append((self.beacon + np.array([0, 4.5, 0]), "BALISE", (1.0, 0.6, 0.15)))
            if self.mission == "collecte":
                for c in self.cores:
                    if not c.collected:
                        out.append((c.pos + np.array([0, 0.8, 0]), "DONNÉES", (0.2, 0.8, 1.0)))
        return out

    # ------------------------------------------------------------------
    def start_wave(self):
        self.wave += 1
        plan = WAVE_PLAN[min(self.wave - 1, len(WAVE_PLAN) - 1)]
        self.mission = plan["mission"]
        mult = self.s.difficulty["count"]
        q = []
        for kind, n in plan["mix"].items():
            q += [kind] * max(1, int(round(n * mult)))
        self.rng.shuffle(q)
        self.queue = q
        self.wave_total = len(q)
        self.wave_kills = 0
        self.wave_time = 0.0
        self.spawn_cd = 1.0
        self.state = "active"
        self.beacon = None
        self.beacon_progress = 0.0
        self.cores = []
        city = self.s.city
        ppos = self.s.player.pos
        if self.mission == "defense":
            pts = [np.array(p) for p in city.beacon_points]
            cand = [p for p in pts if 35 < np.linalg.norm(p[[0, 2]] - ppos[[0, 2]]) < 130]
            if not cand:
                cand = pts
            self.beacon = cand[int(self.rng.integers(0, len(cand)))].astype(np.float64)
        elif self.mission == "collecte":
            pts = [np.array(p, np.float64) for p in city.street_points]
            self.rng.shuffle(pts)
            chosen = []
            for p in pts:
                if np.linalg.norm(p[[0, 2]] - ppos[[0, 2]]) < 30:
                    continue
                if all(np.linalg.norm(p[[0, 2]] - c[[0, 2]]) > 50 for c in chosen):
                    chosen.append(p)
                if len(chosen) == 3:
                    break
            for p in chosen:
                pk = Pickup("data", p)
                self.cores.append(pk)
                self.s.pickups.append(pk)
            self.cores_total = len(chosen)
        self.s.on_wave_start(self.wave, self.mission)

    def _spawn_point(self):
        half = self.s.world.half - 8
        ppos = self.s.player.pos
        for _ in range(20):
            side = int(self.rng.integers(0, 4))
            t = self.rng.uniform(-half, half)
            if side == 0:
                x, z = t, -half
            elif side == 1:
                x, z = t, half
            elif side == 2:
                x, z = -half, t
            else:
                x, z = half, t
            if self.rng.random() < 0.4 and self.s.city.rooftops:
                rx, ry, rz = self.s.city.rooftops[int(self.rng.integers(0, len(self.s.city.rooftops)))]
                x, z = rx, rz
            if math.hypot(x - ppos[0], z - ppos[2]) > 70:
                y = max(35.0, self.s.world.max_height_near(x, z, 6) + 6)
                return np.array([x, y + self.rng.uniform(0, 10), z])
        return np.array([half, 45.0, half])

    def update(self, dt):
        s = self.s
        if self.state == "done":
            return
        if self.state == "intermission":
            self.timer -= dt
            if self.timer <= 0:
                if self.wave >= TOTAL_WAVES:
                    self.state = "done"
                    self.victory = True
                    s.on_victory()
                else:
                    self.start_wave()
            return
        self.wave_time += dt
        alive = [d for d in s.drones if d.alive]
        cap = 4 + self.wave
        # missions à pression continue : renfort de la file tant que l'objectif n'est pas atteint
        if self.mission in ("defense", "collecte") and not self.queue and len(alive) < max(3, cap // 2):
            self.queue.append("eclaireur" if self.rng.random() < 0.7 else "sentinelle")
            self.wave_total += 1
        self.spawn_cd -= dt
        if self.queue and self.spawn_cd <= 0 and len(alive) < cap:
            kind = self.queue.pop()
            d = Drone(kind, self._spawn_point(), s.difficulty, self.rng)
            s.drones.append(d)
            self.spawn_cd = self.rng.uniform(1.0, 2.4) / (1 + 0.05 * self.wave)
        done = False
        if self.mission == "elimination":
            done = not self.queue and not alive
        elif self.mission == "defense":
            if self.player_in_zone():
                contested = sum(1 for d in alive if np.linalg.norm(d.pos - self.beacon) < 14)
                rate = 1.0 / 22.0 * (0.5 if contested else 1.0)
                self.beacon_progress = min(1.0, self.beacon_progress + rate * dt)
                self.beacon_tick -= dt
                if self.beacon_tick <= 0:
                    self.beacon_tick = 0.5
                    s.audio_event("beacon_tick", None, 0.6)
            else:
                self.beacon_progress = max(0.0, self.beacon_progress - dt / 60.0)
            done = self.beacon_progress >= 1.0
            if done:
                s.stats["beacons"] += 1
                s.add_score(800, "BALISE CAPTURÉE")
                s.audio_event("capture", None, 1.0)
        else:
            done = self.cores_total > 0 and all(c.collected for c in self.cores)
            if done:
                s.add_score(600, "DONNÉES SÉCURISÉES")
        if done:
            if self.mission != "elimination":
                s.emp_pulse()
            self.queue = []
            self.state = "intermission"
            self.timer = INTERMISSION
            s.on_wave_clear(self.wave)
