"""Session de jeu : relie joueur, émetteur, drones, projectiles, objets, vagues et score."""
import math
import numpy as np

from gameplay.player import Player
from gameplay.weapons import WeaponState
from gameplay.waves import WaveDirector
from gameplay.data import DRONES, DIFFICULTIES, FINISHES, BEAMS, TOTAL_WAVES
from entities.projectile import Projectile
from entities.pickup import Pickup
from graphics.particles import ParticleSystem


class GameSession:
    def __init__(self, city, world, profile, settings, audio, operation):
        self.city = city
        self.world = world
        self.profile = profile
        self.settings = settings
        self.audio = audio
        self.operation = operation
        self.rng = np.random.default_rng()
        self.difficulty_name = profile.data["difficulty"]
        self.difficulty = DIFFICULTIES[self.difficulty_name]
        self.player = Player(world, city.player_spawn)
        wid = profile.data["weapon"]
        finish = next(f for f in FINISHES if f[0] == profile.data["finish"])
        beam = next(b for b in BEAMS if b[0] == profile.data["beam"])
        self.weapon = WeaponState(wid, profile.weapon_stats(wid), beam[2], finish[2])
        self.drones = []
        self.projectiles = []
        self.pickups = []
        self.particles = ParticleSystem(settings.preset["particles"])
        self.waves = WaveDirector(self, self.rng)
        self.score = 0
        self.combo = 1.0
        self.combo_timer = 0.0
        self.time = 0.0
        self.flash_lights = []        # (pos, rayon, couleur, durée, âge)
        self.messages = []            # notifications (texte, couleur, âge)
        self.feed = []                # fil d'éliminations
        self.damage_dirs = []         # (angle monde, âge)
        self.hitmarker = 0.0
        self.killmarker = 0.0
        self.damage_flash = 0.0
        self.banner = None            # (titre, sous-titre, âge)
        self.over = False
        self.result = None
        self.end_timer = 0.0
        self.stats = dict(kills=0, shots=0, hits=0, damage_taken=0.0, data_cores=0, beacons=0,
                          kills_by_type={k: 0 for k in DRONES})
        self.heartbeat_cd = 0.0

    # ------------------------------------------------------------------
    def audio_event(self, name, pos=None, vol=1.0, variants=0):
        if self.audio:
            self.audio.play(name, vol, pos, variants=variants)

    def notify(self, text, color=(1.0, 0.75, 0.3)):
        self.messages.append([text, color, 0.0])
        self.messages = self.messages[-5:]

    def add_score(self, base, label=None):
        pts = int(base * self.combo * self.difficulty["score"])
        self.score += pts
        if label:
            self.notify(f"+{pts}  {label}")
        return pts

    def on_wave_start(self, wave, mission):
        from gameplay.data import MISSION_TEXT
        self.banner = [f"VAGUE {wave} / {TOTAL_WAVES}", MISSION_TEXT[mission].upper(), 0.0]
        self.audio_event("wave_start", None, 0.9)

    def on_wave_clear(self, wave):
        bonus = 250 * wave
        self.add_score(bonus, f"VAGUE {wave} RÉUSSIE")
        self.banner = [f"VAGUE {wave} RÉUSSIE", "Kits de réparation déployés à proximité", 0.0]
        self.audio_event("wave_clear", None, 0.9)
        # réapprovisionnement : kits autour du joueur
        p = self.player.pos
        for k in range(2):
            a = self.rng.random() * 6.28
            pos = p + np.array([math.cos(a) * 6, 0, math.sin(a) * 6])
            pos[1] = self.world.ground_height(pos[0], pos[2], 50.0, 0.3, 0.0)
            if not self.world.inside_any(pos + np.array([0, 0.5, 0]), 0.3):
                self.pickups.append(Pickup("repair", pos, life=60.0))

    def on_victory(self):
        self.banner = ["OPÉRATION RÉUSSIE", "Toutes les vagues ont été neutralisées", 0.0]
        self.audio_event("victory", None, 1.0)
        self.finish(True)

    def emp_pulse(self):
        """Impulsion de fin de mission : neutralise les drones restants."""
        for d in self.drones:
            if d.alive:
                d.damage(1e6)
                self._on_kill(d, silent=True)
        self.queue_clear = True
        self.flash_lights.append([self.player.eye + np.array([0, 3, 0]), 60.0, np.array([2.0, 3.5, 6.0]), 0.6, 0.0])
        self.notify("IMPULSION IEM : zone sécurisée", (0.4, 0.8, 1.0))

    def spawn_projectile(self, pos, vel, dmg, color, splash=0.0, big=False):
        self.projectiles.append(Projectile(pos, vel, dmg, color, splash, big))
        self.audio_event("drone_shot", pos, 0.5)

    def player_hit(self, dmg, source_pos, src=None):
        if self.over:
            return
        p = self.player
        p.health = max(0.0, p.health - dmg)
        self.stats["damage_taken"] += dmg
        self.damage_flash = min(1.0, self.damage_flash + 0.35 + dmg / 40.0)
        d = np.asarray(source_pos) - p.pos
        self.damage_dirs.append([math.atan2(d[0], -d[2]), 0.0])
        self.audio_event("hurt", None, 0.8)
        self.combo = 1.0
        if p.health <= 0:
            self.banner = ["INTÉGRITÉ CRITIQUE", "Simulation interrompue", 0.0]
            self.audio_event("defeat", None, 1.0)
            self.finish(False)

    # ------------------------------------------------------------------
    def fire(self, cam, devs):
        w = self.weapon
        st = w.s
        fwd = cam.forward
        right = cam.right
        up = np.cross(right, fwd)
        muzzle = self.muzzle_world if hasattr(self, "muzzle_world") else cam.pos + fwd * 0.8
        self.stats["shots"] += 1
        any_hit = False
        for (dx, dy) in devs:
            d = fwd + right * dx + up * dy
            d /= np.linalg.norm(d)
            # drones (sphères)
            best_t, best_drone = st["range"], None
            for dr in self.drones:
                if not dr.alive:
                    continue
                oc = cam.pos - dr.pos
                b = float(np.dot(oc, d))
                c = float(np.dot(oc, oc)) - (dr.radius * 1.15) ** 2
                disc = b * b - c
                if disc < 0:
                    continue
                t = -b - math.sqrt(disc)
                if 0 < t < best_t:
                    best_t, best_drone = t, dr
            tw, n = self.world.raycast(cam.pos, d, st["range"])
            if tw is not None and tw < best_t:
                hit = cam.pos + d * tw
                self.particles.impact(hit, n, w.beam_color)
                end = hit
            elif best_drone is not None:
                end = cam.pos + d * best_t
                dmg = st["damage"] * (1.0 - 0.4 * max(0.0, best_t / st["range"] - 0.5))
                killed = best_drone.damage(dmg)
                self.particles.burst_sparks(end, -d, w.beam_color, n=8, speed=5)
                any_hit = True
                if killed:
                    self._on_kill(best_drone)
            else:
                end = cam.pos + d * min(st["range"], 250.0)
            self.particles.beam(muzzle, end, w.beam_color, width=st["beam_width"])
        if any_hit:
            self.stats["hits"] += 1
            self.hitmarker = 0.18
            self.audio_event("hitmarker", None, 0.6)
        self.flash_lights.append([muzzle.copy(), 7.0, w.beam_color * 6.0, 0.06, 0.0])

    def _on_kill(self, d, silent=False):
        info = DRONES[d.kind]
        self.stats["kills"] += 1
        self.stats["kills_by_type"][d.kind] += 1
        if not silent:
            self.combo_timer = 3.5
            pts = self.add_score(info["score"])
            self.combo = min(5.0, self.combo + 0.25)
            self.feed.append([f"{info['name']} neutralisé", pts, 0.0])
            self.feed = self.feed[-5:]
            self.killmarker = 0.35
            self.audio_event("kill", None, 0.7)
            # butin
            r = self.rng.random()
            if r < 0.14:
                self.pickups.append(Pickup("repair", self._drop_pos(d.pos), life=30.0))
            elif r < 0.2:
                self.pickups.append(Pickup("overcharge", self._drop_pos(d.pos), life=30.0))
        self.waves.wave_kills += 1

    def _drop_pos(self, p):
        x, z = float(p[0]), float(p[2])
        g = self.world.ground_height(x, z, float(p[1]), 0.3, 0.0)
        return np.array([x, g, z])

    def _explode(self, d):
        scale = {"eclaireur": 1.0, "sentinelle": 1.4, "blinde": 2.2}[d.kind]
        self.particles.explosion(d.pos, scale, (1.0, 0.55, 0.2))
        self.flash_lights.append([d.pos.copy(), 18.0 * scale, np.array([30.0, 14.0, 5.0]) * scale, 0.5, 0.0])
        self.audio_event("explosion", d.pos, 1.0, variants=2)
        dist = float(np.linalg.norm(d.pos - self.player.center))
        if dist < 3.0 * scale:
            self.player_hit(10.0 * (1 - dist / (3.0 * scale)), d.pos)
        self.shake = getattr(self, "shake", 0.0) + max(0.0, 0.5 - dist / 60.0)

    def finish(self, victory):
        if self.over:
            return
        self.over = True
        self.end_timer = 0.0
        st = self.stats
        acc = st["hits"] / max(1, st["shots"])
        xp = int(self.score * 0.6 + self.waves.wave * 150 + (1000 if victory else 0))
        credits = int(self.score / 12 + self.waves.wave * 40 + (600 if victory else 0))
        self.result = dict(victory=victory, score=self.score, wave=self.waves.wave, kills=st["kills"],
                           shots=st["shots"], hits=st["hits"], accuracy=acc, time=self.time,
                           distance=self.player.distance, damage_taken=st["damage_taken"],
                           data_cores=st["data_cores"], beacons=st["beacons"], xp=xp, credits=credits,
                           kills_by_type=dict(st["kills_by_type"]), operation=self.operation["name"],
                           difficulty=self.difficulty_name)
        self.result = self.profile.record_game(self.result)

    # ------------------------------------------------------------------
    def update(self, dt, cam):
        self.time += dt
        p = self.player
        w = self.weapon
        w.update(dt)
        for ev in w.events:
            if ev == "overheat":
                self.audio_event("overheat", None, 0.7)
                self.notify("SURCHAUFFE", (1.0, 0.35, 0.2))
            elif ev == "ready":
                self.audio_event("ready", None, 0.5)
        if not self.over:
            self.waves.update(dt)
        for d in self.drones:
            d.update(dt, self)
        for d in self.drones:
            if d.dead:
                self._explode(d)
        self.drones = [d for d in self.drones if not d.dead]
        for pr in self.projectiles:
            pr.update(dt, self)
        self.projectiles = [pr for pr in self.projectiles if not pr.dead]
        # objets
        for pk in self.pickups:
            pk.update(dt)
            if pk.collected:
                continue
            d = pk.pos - p.center
            if d[0] ** 2 + d[2] ** 2 < 1.7 ** 2 and abs(d[1]) < 1.8 and not self.over:
                self._collect(pk)
        self.pickups = [pk for pk in self.pickups if not pk.collected]
        self.particles.update(dt)
        # timers d'interface
        self.combo_timer -= dt
        if self.combo_timer <= 0:
            self.combo = max(1.0, self.combo - dt * 0.8)
        self.hitmarker = max(0.0, self.hitmarker - dt)
        self.killmarker = max(0.0, self.killmarker - dt)
        self.damage_flash = max(0.0, self.damage_flash - dt * 1.5)
        self.shake = max(0.0, getattr(self, "shake", 0.0) - dt * 1.5)
        for m in self.messages:
            m[2] += dt
        self.messages = [m for m in self.messages if m[2] < 3.0]
        for f in self.feed:
            f[2] += dt
        self.feed = [f for f in self.feed if f[2] < 4.0]
        for dd in self.damage_dirs:
            dd[1] += dt
        self.damage_dirs = [dd for dd in self.damage_dirs if dd[1] < 1.2]
        if self.banner:
            self.banner[2] += dt
            if self.banner[2] > 4.0 and not self.over:
                self.banner = None
        for fl in self.flash_lights:
            fl[4] += dt
        self.flash_lights = [fl for fl in self.flash_lights if fl[4] < fl[3]]
        if self.over:
            self.end_timer += dt
        # régénération lente hors combat
        if not self.over and p.health < p.max_health and self.waves.state == "intermission":
            p.health = min(p.max_health, p.health + dt * 4.0)
        # battements de coeur en intégrité critique
        if p.health < 30 and not self.over:
            self.heartbeat_cd -= dt
            if self.heartbeat_cd <= 0:
                self.heartbeat_cd = 0.9
                self.audio_event("heartbeat", None, 0.7)

    def _collect(self, pk):
        p = self.player
        pk.collected = True
        if pk.kind == "repair":
            if p.health >= p.max_health:
                pk.collected = False
                return
            p.health = min(p.max_health, p.health + 35)
            self.notify("+35 INTÉGRITÉ", (0.3, 1.0, 0.45))
            self.audio_event("pickup", None, 0.8)
        elif pk.kind == "overcharge":
            self.weapon.overcharge = 10.0
            self.weapon.heat = 0.0
            self.weapon.overheated = False
            self.notify("SURCHARGE : cadence accrue, sans chauffe", (1.0, 0.6, 0.15))
            self.audio_event("pickup", None, 0.8)
        else:
            self.stats["data_cores"] += 1
            self.add_score(250, "MODULE RÉCUPÉRÉ")
            self.audio_event("data", None, 0.9)
            self.particles.explosion(pk.pos, 0.4, (0.2, 0.8, 1.0))

    def lights(self):
        out = []
        for fl in self.flash_lights:
            k = 1.0 - fl[4] / fl[3]
            out.append((fl[0], fl[1], np.asarray(fl[2]) * k))
        for d in self.drones:
            if d.alive:
                out.append((d.pos - np.array([0, 0.4, 0]), 7.0 * d.d["scale"] + 2, np.array(d.light_color) * 2.5))
        for pr in self.projectiles:
            out.append((pr.pos, 6.0 if not pr.big else 10.0, pr.color * (5.0 if pr.big else 3.0)))
        if self.waves.beacon is not None and self.waves.state == "active":
            out.append((self.waves.beacon + np.array([0, 3.6, 0]), 14.0, np.array([8.0, 4.5, 1.2])))
        return out
