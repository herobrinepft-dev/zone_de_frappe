"""État « en jeu » : entrées, caméra, rendu de la scène, HUD, pause et résultats."""
import math
import numpy as np
import pygame

from engine import mathutils as mu
from engine.camera import Camera
from graphics.renderer import FrameData, DrawItem
from graphics.atmosphere import Environment
from graphics.particles import WeatherFX
from graphics import models
from gameplay.session import GameSession
from gameplay.weapons import WeaponState
from gameplay.data import OPERATIONS, WEAPONS, WEAPON_ORDER, FINISHES, BEAMS
from entities.drone import SHELL_TINT
from audio.manager import AMBIENCE, RAIN, DRONE
from ui import theme as T
from ui.theme import S
from ui.widgets import Button
from ui.settings_panel import SettingsPanel

MOUSE_K = 0.0022
VM_SCALE = 0.62   # échelle de l'arme en vue subjective


class _NoKeys:
    def __getitem__(self, k):
        return False


NO_KEYS = _NoKeys()


class GameState:
    def __init__(self, app):
        self.app = app
        p = app.profile
        self.op = next(o for o in OPERATIONS if o["id"] == p.data["operation"])
        self.env = Environment()
        self.env.configure(self.op["hour"], self.op["clouds"], self.op["fog"], self.op["rain"])
        self.env.time_speed = 1.0 / 300.0
        self.session = GameSession(app.city, app.world, p, app.settings, app.audio, self.op)
        self.cam = Camera()
        self.cam.yaw = 0.0
        self.weather = WeatherFX()
        self.paused = False
        self.pause_settings = False
        self.pause_widgets = []
        self.result_widgets = []
        self.settings_panel = SettingsPanel(app)
        self.aim = 0.0
        self.sway = np.zeros(2)
        self.look_delta = np.zeros(2)
        self.t = 0.0
        self.fade = 0.0
        self.leaving = None
        self.leave_t = 0.0
        self.thunder_queue = []
        self.lightning_cd = 6.0
        self.sprint_k = 0.0
        self.recoil_pitch = 0.0
        self.switch_anim = 0.0
        self.trigger_prev = False
        self.muzzle_local = {k: np.array(models.weapon_muzzle(k)) for k in WEAPON_ORDER}
        self.rotors = {k: models.drone_rotors(k) for k in ("eclaireur", "sentinelle", "blinde")}
        self.rng = np.random.default_rng()
        self.death_t = 0.0

    # ------------------------------------------------------------------
    def enter(self):
        self.app.set_mouse_captured(True)
        self.app.audio.play_music("music_game", 2500)
        self.fade = 0.0
        self.layout()

    def layout(self):
        W, H = self.app.size
        T.FONTS.set_scale(H)
        cx = W // 2
        self.pause_widgets = [
            Button((cx - S(200), H // 2 - S(80), S(400), S(58)), "REPRENDRE", self.resume, style="primary", size=22),
            Button((cx - S(200), H // 2 - S(8), S(400), S(54)), "PARAMÈTRES", self.open_settings, style="ghost", size=20),
            Button((cx - S(200), H // 2 + S(60), S(400), S(54)), "ABANDONNER LA MISSION", self.abandon, style="ghost",
                   size=20),
        ]
        self.settings_panel.build((cx - S(450), S(120), S(900), H - S(260)))
        self.settings_back = Button((cx - S(150), H - S(120), S(300), S(52)), "RETOUR", self.close_settings,
                                    style="ghost", size=20)
        self.result_widgets = [
            Button((cx - S(330), H - S(170), S(310), S(62)), "REJOUER", self.replay, style="primary", size=22),
            Button((cx + S(20), H - S(170), S(310), S(62)), "MENU PRINCIPAL", self.to_menu, style="ghost", size=20),
        ]

    def resume(self):
        self.paused = False
        self.pause_settings = False
        self.app.set_mouse_captured(True)
        self.app.audio.pause_all(False)
        self.app.audio.play("ui_back", 0.6)

    def pause(self):
        if self.session.over:
            return
        self.paused = True
        self.app.set_mouse_captured(False)
        self.app.audio.pause_all(True)
        self.app.audio.play("ui_click", 0.6)

    def open_settings(self):
        self.pause_settings = True
        self.settings_panel.build(self.settings_panel.rect)
        self.app.audio.play("ui_click", 0.6)

    def close_settings(self):
        self.pause_settings = False
        self.app.audio.play("ui_back", 0.6)

    def abandon(self):
        self.paused = False
        self.app.audio.pause_all(False)
        self.session.banner = ["MISSION ABANDONNÉE", "Retour à la base", 0.0]
        self.session.finish(False)

    def replay(self):
        self.leaving = "replay"
        self.leave_t = 0.0
        self.app.audio.play("ui_confirm", 0.7)

    def to_menu(self):
        self.leaving = "menu"
        self.leave_t = 0.0
        self.app.audio.play("ui_click", 0.7)

    def switch_weapon(self, wid):
        p = self.app.profile
        s = self.session
        if wid not in p.data["owned_weapons"] or wid == s.weapon.id:
            return
        finish = next(f for f in FINISHES if f[0] == p.data["finish"])
        beam = next(b for b in BEAMS if b[0] == p.data["beam"])
        heat = s.weapon.heat
        s.weapon = WeaponState(wid, p.weapon_stats(wid), beam[2], finish[2])
        s.weapon.heat = heat * 0.5
        s.weapon.cooldown = 0.35
        self.switch_anim = 1.0
        self.app.audio.play("whoosh", 0.5)

    # ------------------------------------------------------------------
    def handle(self, ev):
        s = self.session
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                if s.over:
                    return
                if self.paused:
                    if self.pause_settings:
                        self.close_settings()
                    else:
                        self.resume()
                else:
                    self.pause()
                return
            if not self.paused and not s.over:
                if ev.key in (pygame.K_1, pygame.K_KP1):
                    self.switch_weapon("pulsar")
                elif ev.key in (pygame.K_2, pygame.K_KP2):
                    self.switch_weapon("faucon")
                elif ev.key in (pygame.K_3, pygame.K_KP3):
                    self.switch_weapon("tempete")
        if ev.type == pygame.MOUSEMOTION and not self.paused and not s.over and self.app.mouse_captured:
            self.look_delta += np.array(ev.rel, np.float64)
        if ev.type == pygame.MOUSEWHEEL and not self.paused and not s.over:
            owned = [w for w in WEAPON_ORDER if w in self.app.profile.data["owned_weapons"]]
            if len(owned) > 1:
                i = owned.index(s.weapon.id) if s.weapon.id in owned else 0
                self.switch_weapon(owned[(i - ev.y) % len(owned)])
        if self.paused:
            if self.pause_settings:
                if self.settings_panel.handle(ev):
                    return
                if self.settings_back.handle(ev):
                    return
            else:
                for w in self.pause_widgets:
                    if w.handle(ev):
                        return
        elif s.over and s.end_timer > 2.5 and not self.leaving:
            for w in self.result_widgets:
                if w.handle(ev):
                    return

    # ------------------------------------------------------------------
    def update(self, dt):
        app = self.app
        s = self.session
        self.fade = min(1.0, self.fade + dt * 1.0)
        if self.leaving:
            self.leave_t += dt
            if self.leave_t > 0.6:
                if self.leaving == "replay":
                    app.start_game()
                else:
                    app.to_menu()
            return
        mouse = pygame.mouse.get_pos()
        if self.paused:
            if self.pause_settings:
                self.settings_panel.update(dt, mouse)
                self.settings_back.update(dt, mouse)
            else:
                for w in self.pause_widgets:
                    if w.update(dt, mouse):
                        app.audio.play("ui_hover", 0.35)
            self.look_delta[:] = 0
            return
        self.t += dt
        st = app.settings
        keys = pygame.key.get_pressed() if app.autopilot is None else NO_KEYS
        vk = app.virtual_keys

        def k(*names):
            for n in names:
                if n in vk:
                    return True
            return False

        fwd = (keys[pygame.K_w] or keys[pygame.K_z] or keys[pygame.K_UP] or k("forward"))
        back = (keys[pygame.K_s] or keys[pygame.K_DOWN] or k("back"))
        left = (keys[pygame.K_a] or keys[pygame.K_q] or keys[pygame.K_LEFT] or k("left"))
        right = (keys[pygame.K_d] or keys[pygame.K_RIGHT] or k("right"))
        jump = keys[pygame.K_SPACE] or k("jump")
        sprint = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or k("sprint")
        crouch = keys[pygame.K_LCTRL] or keys[pygame.K_c] or k("crouch")
        mb = pygame.mouse.get_pressed(3) if app.mouse_captured else (False, False, False)
        trigger = mb[0] or k("fire")
        aiming = (mb[2] or k("aim")) and not s.over
        if s.over:
            fwd = back = left = right = jump = sprint = crouch = trigger = False

        # vue souris
        look = self.look_delta + np.array(app.virtual_look, np.float64)
        app.virtual_look = (0.0, 0.0)
        self.look_delta[:] = 0
        zoom = 1.0 + (s.weapon.s["zoom"] - 1.0) * self.aim
        sens = MOUSE_K * st["sensitivity"] / zoom
        self.cam.yaw += look[0] * sens
        dy = look[1] * sens * (-1 if st["invert_y"] else 1)
        self.cam.pitch = mu.clamp(self.cam.pitch - dy, -1.5, 1.5)
        self.sway += np.array([-look[0], look[1]]) * 0.00035
        self.sway *= max(0.0, 1.0 - dt * 9.0)
        self.sway = np.clip(self.sway, -0.05, 0.05)

        mx = (1 if right else 0) - (1 if left else 0)
        mz = (1 if fwd else 0) - (1 if back else 0)
        p = s.player
        p.update(dt, mx, mz, jump, sprint and not aiming, crouch, self.cam.yaw)
        for ev in p.events:
            if ev == "step":
                vol = 0.35 if not p.sprinting else 0.5
                if p.crouch:
                    vol = 0.15
                app.audio.play("step", vol, variants=4)
            elif ev == "jump":
                app.audio.play("jump", 0.5)
            elif ev == "land":
                app.audio.play("land", min(1.0, 0.3 + p.land_vel * 0.05))
        self.sprint_k += ((1.0 if p.sprinting else 0.0) - self.sprint_k) * min(1.0, dt * 8)
        self.aim += ((1.0 if aiming and not p.sprinting else 0.0) - self.aim) * min(1.0, dt * 12)
        self.switch_anim = max(0.0, self.switch_anim - dt * 3.0)

        # caméra
        bv, bl, br = p.bob_offsets(st["head_bob"])
        bob_k = 1.0 - self.aim * 0.8
        eye = p.eye.copy()
        eye[1] += bv * bob_k
        eye += self.cam.right * bl * bob_k
        shake = getattr(s, "shake", 0.0)
        if shake > 0:
            eye += self.rng.normal(size=3) * shake * 0.05
        if s.over and not s.result.get("victory", False):
            self.death_t = min(1.0, self.death_t + dt * 0.8)
            eye[1] -= self.death_t * 1.2
        self.cam.pos = eye
        strafe_roll = -mx * 0.012 * (1 - self.aim)
        self.cam.roll += (strafe_roll + br * bob_k + self.death_t * 0.35 - self.cam.roll) * min(1, dt * 8)
        base_fov = st["fov"] + 7.0 * self.sprint_k
        self.cam.fov = base_fov / zoom
        # recul
        w = s.weapon
        if w.kick > 0:
            k_ = min(w.kick, dt * 12 * max(w.kick, 0.02))
            self.cam.pitch = min(1.5, self.cam.pitch + k_)
            self.recoil_pitch += k_
            w.kick -= k_
        elif self.recoil_pitch > 0:
            r = min(self.recoil_pitch, dt * 0.12)
            self.cam.pitch -= r * 0.6
            self.recoil_pitch -= r

        # muzzle (monde) pour l'origine des faisceaux
        vm = self.viewmodel_matrix()
        ml = self.muzzle_local[w.id]
        s.muzzle_world = (vm @ np.array([*ml, 1.0]))[:3]

        # tir
        pressed = trigger and not self.trigger_prev
        self.trigger_prev = trigger
        if not s.over and self.sprint_k < 0.5 and self.switch_anim < 0.3:
            devs = w.try_fire(trigger, pressed, mx != 0 or mz != 0, self.aim > 0.5, self.rng)
            if devs:
                s.fire(self.cam, devs)
                app.audio.play(f"shot_{w.id}", 0.7)

        s.update(dt, self.cam)
        app.audio.set_listener(self.cam.pos, self.cam.right)

        # environnement
        self.env.update(dt)
        if self.env.rain > 0:
            self.lightning_cd -= dt
            if self.lightning_cd <= 0:
                self.lightning_cd = self.rng.uniform(9, 22)
                self.env.lightning = 1.0
                self.thunder_queue.append(self.rng.uniform(0.6, 2.5))
        for i in range(len(self.thunder_queue)):
            self.thunder_queue[i] -= dt
        if any(t <= 0 for t in self.thunder_queue):
            app.audio.play("thunder", 0.8, variants=2)
            self.thunder_queue = [t for t in self.thunder_queue if t > 0]
        self.weather.update(dt)

        # boucles audio
        amb = 0.45 * (1.0 - 0.4 * self.env.rain)
        app.audio.loop(AMBIENCE, "loop_city", amb)
        app.audio.loop(RAIN, "loop_rain", 0.7 * self.env.rain)
        nearest = min((np.linalg.norm(d.pos - self.cam.pos) for d in s.drones if d.alive), default=999.0)
        app.audio.loop(DRONE, "loop_drone", max(0.0, 1.0 - nearest / 45.0) * 0.55)
        if s.over and not getattr(self, "_ended", False):
            self._ended = True
            app.audio.stop_music(2500)

        if s.over and s.end_timer > 2.5:
            app.set_mouse_captured(False)
            for wdg in self.result_widgets:
                if wdg.update(dt, mouse):
                    app.audio.play("ui_hover", 0.35)

    def viewmodel_matrix(self):
        s = self.session
        w = s.weapon
        p = s.player
        st = w.s
        a = self.aim
        off = np.array(st["offset"]) * (1 - a) + np.array(st["ads_offset"]) * a
        bob_a = p.bob_amount * (1 - a * 0.85)
        bx = math.sin(p.bob_phase) * 0.012 * bob_a
        by = abs(math.cos(p.bob_phase)) * 0.012 * bob_a
        idle = math.sin(self.t * 1.3) * 0.002 * (1 - a)
        rec = w.recoil
        sk = self.sprint_k
        sw = self.switch_anim
        cam_m = np.linalg.inv(self.cam.view())
        m = cam_m @ mu.translate(off[0] + bx + self.sway[0] + 0.05 * sk, off[1] + by + idle + self.sway[1] - 0.04 * sk - 0.25 * sw,
                                 off[2] + 0.045 * rec * (1 - 0.5 * a))
        m = m @ mu.rot_y(0.55 * sk) @ mu.rot_x(-0.25 * sk + 0.06 * rec - 0.6 * sw) @ mu.rot_z(0.1 * sk)
        return m @ mu.scale(VM_SCALE)

    # ------------------------------------------------------------------
    def render(self):
        app = self.app
        s = self.session
        W, H = app.size
        f = FrameData()
        f.time = self.t
        f.env = self.env
        f.view = self.cam.view()
        f.proj = self.cam.proj(W / H)
        f.cam_pos = self.cam.pos.copy()
        f.cam_forward = self.cam.forward
        f.static_chunks = app.static_chunks
        f.far_meshes = app.far_meshes
        items = []
        for d in s.drones:
            body = mu.translate(*d.pos) @ mu.rot_y(-d.yaw) @ mu.rot_x(d.tilt_x) @ mu.rot_z(d.tilt_z)
            emis_scale = 1.0 if d.alive else 0.15
            items.append(DrawItem(app.meshes[f"drone_{d.kind}"], body, tint=d.tint, emis=d.light_color,
                                  emis_scale=emis_scale, flash=d.flash * 1.5))
            for i, (px, py, pz, rr) in enumerate(self.rotors[d.kind]):
                sgn = 1 if i % 2 == 0 else -1
                rm = body @ mu.translate(px, py, pz) @ mu.rot_y(d.rotor * sgn) @ mu.scale(rr * 0.92)
                items.append(DrawItem(app.meshes["rotor"], rm, shadow=False))
        for pk in s.pickups:
            m = mu.translate(*pk.pos) @ mu.rot_y(pk.yaw)
            items.append(DrawItem(app.meshes[pk.info["model"]], m, emis=(1, 1, 1), emis_scale=1.0))
        w = s.waves
        if w.beacon is not None and w.state == "active":
            pulse = 0.6 + 0.4 * math.sin(self.t * 4.0)
            items.append(DrawItem(app.meshes["beacon"], mu.translate(*w.beacon), emis_scale=0.6 + 0.6 * pulse))
            col = (1.0, 0.55, 0.15) if not w.player_in_zone() else (0.3, 1.0, 0.45)
            ring = mu.translate(w.beacon[0], w.beacon[1] + 0.05, w.beacon[2]) @ mu.scale(7.0, 1.0 + 3.0 * w.beacon_progress, 7.0)
            items.append(DrawItem(app.meshes["ring"], ring, emis=col, emis_scale=0.25 + 0.15 * pulse, shadow=False))
        f.dynamic = items
        # particules : effets + projectiles + météo
        parts = [s.particles.instances()]
        if s.projectiles:
            pr = np.zeros((len(s.projectiles) * 2, 12), np.float32)
            for i, p_ in enumerate(s.projectiles):
                c = p_.color
                pr[2 * i, 0:3] = p_.pos
                pr[2 * i, 6] = p_.size * 3.0
                pr[2 * i, 7:10] = c * 3.0
                pr[2 * i, 10] = 1.0
                pr[2 * i + 1, 0:3] = p_.pos
                pr[2 * i + 1, 3:6] = -p_.vel * 0.03
                pr[2 * i + 1, 6] = p_.size * 0.8
                pr[2 * i + 1, 7:10] = c * 8.0 + 2.0
                pr[2 * i + 1, 10] = 1.0
                pr[2 * i + 1, 11] = 2
            parts.append(pr)
        q = {"Bas": 0.4, "Moyen": 0.7}.get(app.settings["quality"], 1.0)
        parts.append(self.weather.instances(self.cam.pos, self.env, app.settings["weather_effects"], q))
        f.particles = np.concatenate(parts) if parts else None
        # éclairage dynamique
        lights = s.lights()
        if self.env.night > 0.3 or self.env.cloud_cover > 0.8:
            cp = self.cam.pos
            lamps = app.lamp_array
            d2 = np.sum((lamps - cp) ** 2, axis=1)
            for i in np.argsort(d2)[:14]:
                lights.append((lamps[i], 24.0, np.array([22.0, 15.0, 8.0]) * min(1.0, self.env.lamp_glow / 2.0)))
        f.lights = lights
        # arme en vue subjective
        if not (s.over and not s.result.get("victory", False)):
            wid = s.weapon.id
            vm = self.viewmodel_matrix()
            hide = self.aim > 0.9 and wid == "faucon"
            if not hide:
                f.viewmodel = [DrawItem(app.meshes[f"weapon_{wid}"], vm, tint=s.weapon.finish_color,
                                        emis=s.weapon.beam_color,
                                        emis_scale=0.6 + 1.2 * s.weapon.heat + (1.0 if s.weapon.overcharge > 0 else 0.0))]
            if s.weapon.muzzle_flash > 0:
                mf = np.zeros((2, 12), np.float32)
                c = s.weapon.beam_color
                mf[:, 0:3] = s.muzzle_world
                small = 0.45 if self.aim > 0.5 else 1.0
                mf[0, 6] = 0.07 * small
                mf[0, 7:10] = c * 5.0
                mf[0, 10] = 1.0
                mf[1, 6] = 0.025 * small
                mf[1, 7:10] = 8.0
                mf[1, 10] = 1.0
                f.vm_particles = mf
        f.damage = s.damage_flash
        hp = s.player.health / s.player.max_health
        f.low_health = max(0.0, (0.3 - hp) / 0.3) if not s.over or not s.result["victory"] else 0.0
        fade = self.fade
        if self.leaving:
            fade *= max(0.0, 1.0 - self.leave_t / 0.5)
        f.fade = fade
        app.renderer.render(f)
        self.last_vp = f.proj @ f.view

        surf = app.ui_surface
        surf.fill((0, 0, 0, 0))
        if not (s.over and s.end_timer > 2.5):
            app.hud.draw(surf, s, self.cam, self.last_vp, app.dt, app.fps, self.aim > 0.6)
        if self.paused:
            self._draw_pause(surf)
        elif s.over and s.end_timer > 2.5:
            self._draw_results(surf)
        app.renderer.draw_overlay(surf)

    def _draw_pause(self, surf):
        W, H = surf.get_size()
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((4, 6, 10, 170))
        surf.blit(ov, (0, 0))
        if self.pause_settings:
            T.text(surf, "PARAMÈTRES", (W // 2, S(60)), 34, T.WHITE, bold=True, anchor="midtop")
            self.settings_panel.draw(surf)
            self.settings_back.draw(surf)
            return
        T.text(surf, "PAUSE", (W // 2, H // 2 - S(200)), 64, T.WHITE, bold=True, anchor="midtop", shadow=True)
        T.text(surf, f"{self.op['name']}  •  Vague {max(1, self.session.waves.wave)} / 10  •  Score {self.session.score}",
               (W // 2, H // 2 - S(122)), 18, T.ACCENT_2, anchor="midtop")
        for w in self.pause_widgets:
            w.draw(surf)

    def _draw_results(self, surf):
        W, H = surf.get_size()
        s = self.session
        r = s.result
        k = T.ease_out((s.end_timer - 2.5) * 1.5)
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((4, 6, 10, int(200 * k)))
        surf.blit(ov, (0, 0))
        a = 255 * k
        y = int(S(110) - (1 - k) * S(30))
        title = "OPÉRATION RÉUSSIE" if r["victory"] else "FIN DE SIMULATION"
        T.text(surf, "RAPPORT DE MISSION", (W // 2, y), 18, T.ACCENT, bold=True, anchor="midtop", alpha=a)
        T.text(surf, title, (W // 2, y + S(30)), 60, T.GOOD if r["victory"] else T.WHITE, bold=True, anchor="midtop",
               shadow=True, alpha=a)
        T.text(surf, f"{r['operation']}  •  {r['difficulty']}", (W // 2, y + S(104)), 18, T.MUTED, anchor="midtop",
               alpha=a)
        box = pygame.Rect(W // 2 - S(420), y + S(150), S(840), S(400))
        T.panel(surf, box, int(200 * k), accent=True)
        mins, secs = divmod(int(r["time"]), 60)
        rows = [("Score final", f"{r['score']:,}".replace(",", " ")), ("Vague atteinte", f"{r['wave']} / 10"),
                ("Drones neutralisés", str(r["kills"])), ("Précision", f"{r['accuracy']:.0%}"),
                ("Durée", f"{mins:02d}:{secs:02d}"), ("Distance parcourue", f"{r['distance']:.0f} m"),
                ("Dégâts subis", f"{r['damage_taken']:.0f}"), ("Modules / balises", f"{r['data_cores']} / {r['beacons']}")]
        for i, (kk, v) in enumerate(rows):
            cx = box.x + S(40) + (i % 2) * S(400)
            cy = box.y + S(36) + (i // 2) * S(56)
            T.text(surf, kk, (cx, cy), 17, T.MUTED, alpha=a)
            T.text(surf, v, (cx + S(360), cy - S(4)), 26, T.WHITE, bold=True, anchor="topright", alpha=a)
        gy = box.y + S(280)
        T.rect(surf, (255, 255, 255, int(30 * k)), (box.x + S(40), gy - S(16), box.w - S(80), 1))
        T.text(surf, f"+{r['xp']} XP", (box.x + S(40), gy), 30, T.ACCENT, bold=True, alpha=a)
        T.text(surf, f"+{r['credits']} CR", (box.x + S(260), gy), 30, T.ACCENT_2, bold=True, alpha=a)
        if r.get("level_up"):
            T.text(surf, f"NOUVEAU NIVEAU : {r['new_level']}", (box.right - S(40), gy + S(4)), 24, T.GOOD, bold=True,
                   anchor="topright", alpha=a)
        T.text(surf, "Récompenses ajoutées à votre profil.", (box.x + S(40), gy + S(48)), 16, T.MUTED, alpha=a)
        for wdg in self.result_widgets:
            wdg.draw(surf, k)
