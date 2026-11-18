"""Contrôleur du joueur : déplacement, saut, gravité, collisions, balancement de caméra."""
import math
import numpy as np

RADIUS = 0.35
HEIGHT = 1.8
CROUCH_HEIGHT = 1.15
STEP = 0.5
GRAVITY = 22.0
JUMP_VEL = 7.4
RUN_SPEED = 5.4
SPRINT_SPEED = 8.4
CROUCH_SPEED = 2.6
GROUND_ACCEL = 60.0
AIR_ACCEL = 9.0


class Player:
    def __init__(self, world, spawn):
        self.world = world
        self.pos = np.array(spawn, np.float64)   # position des pieds
        self.vel = np.zeros(3)
        self.on_ground = True
        self.crouch = False
        self.height = HEIGHT
        self.sprinting = False
        self.stamina = 1.0
        self.health = 100.0
        self.max_health = 100.0
        self.bob_phase = 0.0
        self.bob_amount = 0.0
        self.land_kick = 0.0
        self.land_vel = 0.0
        self.eye_smooth = self.pos[1] + HEIGHT - 0.12
        self.distance = 0.0
        self.events = []     # "step", "jump", "land"
        self.last_step_side = 0
        self.air_time = 0.0
        self.max_fall_speed = 0.0

    @property
    def eye(self):
        return np.array([self.pos[0], self.eye_smooth, self.pos[2]])

    @property
    def center(self):
        return self.pos + np.array([0.0, self.height * 0.5, 0.0])

    # ------------------------------------------------------------------
    def _blocked(self, p, height):
        w = self.world
        idx = w.query(p[0] - RADIUS, p[2] - RADIUS, p[0] + RADIUS, p[2] + RADIUS)
        if not len(idx):
            return False
        b = w.boxes[idx]
        over = (b[:, 0] < p[0] + RADIUS) & (b[:, 3] > p[0] - RADIUS) & \
               (b[:, 2] < p[2] + RADIUS) & (b[:, 5] > p[2] - RADIUS)
        vert = (b[:, 4] > p[1] + STEP) & (b[:, 1] < p[1] + height)
        return bool((over & vert).any())

    def _ceiling(self, p, height):
        w = self.world
        idx = w.query(p[0] - RADIUS, p[2] - RADIUS, p[0] + RADIUS, p[2] + RADIUS)
        if not len(idx):
            return None
        b = w.boxes[idx]
        over = (b[:, 0] < p[0] + RADIUS) & (b[:, 3] > p[0] - RADIUS) & \
               (b[:, 2] < p[2] + RADIUS) & (b[:, 5] > p[2] - RADIUS)
        hit = over & (b[:, 1] > p[1] + 0.3) & (b[:, 1] < p[1] + height)
        if hit.any():
            return float(b[hit, 1].min())
        return None

    def update(self, dt, move_x, move_z, jump, sprint, crouch, yaw):
        self.events.clear()
        # accroupi (vérifie qu'on peut se relever)
        if crouch:
            self.crouch = True
        elif self.crouch and self._ceiling(self.pos, HEIGHT) is None:
            self.crouch = False
        target_h = CROUCH_HEIGHT if self.crouch else HEIGHT
        self.height += (target_h - self.height) * min(1.0, dt * 12.0)

        moving = abs(move_x) + abs(move_z) > 0.01
        self.sprinting = sprint and moving and move_z > 0.1 and not self.crouch and self.stamina > 0.05
        if self.sprinting:
            self.stamina = max(0.0, self.stamina - dt * 0.16)
        else:
            self.stamina = min(1.0, self.stamina + dt * (0.22 if moving else 0.35))
        speed = SPRINT_SPEED if self.sprinting else (CROUCH_SPEED if self.crouch else RUN_SPEED)

        fwd = np.array([math.sin(yaw), 0.0, -math.cos(yaw)])
        right = np.array([math.cos(yaw), 0.0, math.sin(yaw)])
        wish = fwd * move_z + right * move_x
        n = np.linalg.norm(wish)
        if n > 1e-6:
            wish = wish / n * speed
        accel = GROUND_ACCEL if self.on_ground else AIR_ACCEL
        hv = self.vel[[0, 2]]
        target = wish[[0, 2]]
        diff = target - hv
        dl = np.linalg.norm(diff)
        step = accel * dt
        if dl > step:
            diff = diff / dl * step
        if not self.on_ground and n < 1e-6:
            diff *= 0.0  # conservation de l'élan en l'air
        hv = hv + diff
        self.vel[0], self.vel[2] = hv

        if jump and self.on_ground:
            self.vel[1] = JUMP_VEL
            self.on_ground = False
            self.events.append("jump")

        # déplacement horizontal, axe par axe (glissement le long des murs)
        old = self.pos.copy()
        for axis in (0, 2):
            np_ = self.pos.copy()
            np_[axis] += self.vel[axis] * dt
            if self._blocked(np_, self.height):
                self.vel[axis] = 0.0
            else:
                self.pos = np_
        lim = self.world.half - 0.6
        self.pos[0] = min(lim, max(-lim, self.pos[0]))
        self.pos[2] = min(lim, max(-lim, self.pos[2]))

        # vertical
        self.vel[1] -= GRAVITY * dt
        self.vel[1] = max(self.vel[1], -45.0)
        new_y = self.pos[1] + self.vel[1] * dt
        if self.vel[1] > 0:
            ceil = self._ceiling(self.pos, self.height + self.vel[1] * dt)
            if ceil is not None:
                new_y = min(new_y, ceil - self.height)
                self.vel[1] = 0.0
        ground = self.world.ground_height(self.pos[0], self.pos[2], max(self.pos[1], new_y), RADIUS * 0.95, STEP)
        was_ground = self.on_ground
        if new_y <= ground:
            if not was_ground and self.air_time > 0.15:
                self.land_vel = -min(self.vel[1], 0.0)
                self.land_kick = min(0.25, self.land_vel * 0.022)
                self.events.append("land")
            new_y = ground
            self.vel[1] = 0.0
            self.on_ground = True
        elif was_ground and self.vel[1] <= 0 and new_y - ground < STEP and new_y - ground > 0:
            # collé au sol en descendant une marche
            new_y = ground
            self.vel[1] = 0.0
        else:
            self.on_ground = False
        self.pos[1] = new_y
        self.air_time = 0.0 if self.on_ground else self.air_time + dt

        # distance parcourue et bruits de pas
        moved = math.hypot(self.pos[0] - old[0], self.pos[2] - old[2])
        self.distance += moved
        hs = math.hypot(self.vel[0], self.vel[2])
        if self.on_ground and hs > 0.5:
            freq = 1.0 + hs * 0.17
            prev = self.bob_phase
            self.bob_phase += dt * freq * math.pi * 2
            if int(prev / math.pi) != int(self.bob_phase / math.pi):
                self.events.append("step")
            self.bob_amount += (min(1.0, hs / SPRINT_SPEED) - self.bob_amount) * min(1, dt * 8)
        else:
            self.bob_amount += (0.0 - self.bob_amount) * min(1, dt * 6)

        # caméra : lissage de la hauteur des yeux (marches) + amortissement à l'atterrissage
        target_eye = self.pos[1] + self.height - 0.12
        if abs(target_eye - self.eye_smooth) > 1.2:
            self.eye_smooth = target_eye
        self.eye_smooth += (target_eye - self.eye_smooth) * min(1.0, dt * 18.0)
        self.land_kick = max(0.0, self.land_kick - dt * 0.9)

    def bob_offsets(self, enabled=True):
        """(vertical, latéral, roulis) du balancement de caméra."""
        if not enabled:
            return 0.0, 0.0, 0.0
        a = self.bob_amount
        v = math.sin(self.bob_phase * 2.0) * 0.045 * a - self.land_kick * math.sin(min(1.0, self.land_kick * 8) * math.pi)
        l = math.sin(self.bob_phase) * 0.035 * a
        r = math.sin(self.bob_phase) * 0.006 * a
        return v, l, r
