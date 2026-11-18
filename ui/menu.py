"""Menu principal : ACCUEIL, JOUER, ARMURERIE, OPÉRATIONS, PARAMÈTRES, STATISTIQUES, QUITTER."""
import math
import numpy as np
import pygame

from engine import mathutils as mu
from engine.camera import Camera
from graphics.renderer import FrameData, DrawItem
from graphics.atmosphere import Environment
from gameplay.data import (WEAPONS, WEAPON_ORDER, UPGRADES, FINISHES, BEAMS, OPERATIONS, DIFFICULTIES,
                           DIFFICULTY_ORDER, DRONES, level_from_xp)
from entities.drone import SHELL_TINT
from ui import theme as T
from ui.theme import S
from ui.widgets import Button, Selector
from ui.settings_panel import SettingsPanel

PAGES = ["ACCUEIL", "JOUER", "ARMURERIE", "OPÉRATIONS", "PARAMÈTRES", "STATISTIQUES", "QUITTER"]

TIPS = [
    "Les Éclaireurs piquent sur vous : décalez-vous latéralement au dernier moment.",
    "Les orbes ennemis sont lents : surveillez leur lueur et utilisez le décor.",
    "Le Blindé encaisse énormément : le FAUCON LR-7 est idéal pour le neutraliser.",
    "Enchaîner les neutralisations augmente votre multiplicateur de combo jusqu'à x5.",
    "Laissez refroidir votre émetteur : une surchauffe vous laisse sans défense.",
    "Pendant une capture de balise, les drones à proximité ralentissent la progression.",
    "Les kits de réparation largués par les drones disparaissent après 30 secondes.",
]


class StudioEnv:
    """Éclairage de présentoir pour l'armurerie."""

    def __init__(self):
        self.light_dir = mu.normalize(np.array([0.35, 0.85, 0.45]))
        self.true_sun = self.light_dir
        self.light_color = np.array([2.6, 2.45, 2.3])
        self.zenith = np.array([0.05, 0.06, 0.08])
        self.horizon = np.array([0.12, 0.09, 0.07])
        self.ground = np.array([0.03, 0.03, 0.03])
        self.night = 0.0
        self.wind = 0.0
        self.wetness = 0.0
        self.window_lights = 0.0
        self.ambient = 1.0
        self.lamp_glow = 1.0
        self.fog_color = np.zeros(3)
        self.fog_density = 0.0
        self.exposure = 1.25
        self.cloud_cover = 0.0
        self.lightning = 0.0


class MenuState:
    def __init__(self, app):
        self.app = app
        self.page = 0
        self.prev_page = 0
        self.page_t = 1.0
        self.t = 0.0
        self.fade_in = 0.0
        self.leaving = None
        self.leave_t = 0.0
        self.env = Environment()
        self._apply_operation_env()
        self.cam = Camera()
        self.settings_panel = SettingsPanel(app)
        self.nav = []
        self.page_widgets = []
        self.armory_sel = app.profile.data["weapon"]
        self.studio_env = StudioEnv()
        self.confirm_quit = False
        self.message = ""
        self.message_t = 0.0
        self.studio_k = 0.0
        self.weapon_spin = 0.0
        self.layout()
        self.patrol = [(18 + i * 9, 0.25 + i * 0.07, i * 2.1, k) for i, k in
                       enumerate(["eclaireur", "sentinelle", "eclaireur", "blinde", "eclaireur"])]

    # ------------------------------------------------------------------
    def enter(self):
        self.fade_in = 0.0
        self.leaving = None
        self.app.audio.play_music("music_menu", 2000)
        self.app.audio.stop_loops()
        self.app.set_mouse_captured(False)
        self.layout()

    def _apply_operation_env(self):
        op = next(o for o in OPERATIONS if o["id"] == self.app.profile.data["operation"])
        self.env.configure(op["hour"], op["clouds"], op["fog"], op["rain"])
        self.env.time_speed = 0.0

    def layout(self):
        W, H = self.app.size
        T.FONTS.set_scale(H)
        self.nav = []
        y = S(300)
        for i, name in enumerate(PAGES):
            b = Button((S(56), y, S(390), S(54)), name, callback=lambda i=i: self.goto(i), style="nav", size=28,
                       selected=(i == self.page))
            self.nav.append(b)
            y += S(60)
        self.content = pygame.Rect(S(520), S(150), W - S(520) - S(60), H - S(150) - S(90))
        self.build_page()

    def goto(self, i):
        if PAGES[i] == "QUITTER":
            self.confirm_quit = True
            self.build_page()
            self.app.audio.play("ui_click", 0.7)
            return
        if i == self.page:
            return
        self.prev_page = self.page
        self.page = i
        self.page_t = 0.0
        self.confirm_quit = False
        for k, b in enumerate(self.nav):
            b.selected = (k == i)
        self.app.audio.play("ui_click", 0.7)
        self.build_page()

    def flash(self, msg):
        self.message = msg
        self.message_t = 3.0

    # ------------------------------------------------------------------
    def build_page(self):
        c = self.content
        p = self.app.profile
        ws = []
        name = PAGES[self.page]
        if self.confirm_quit:
            mw, mh = S(520), S(230)
            W, H = self.app.size
            box = pygame.Rect(W // 2 - mw // 2, H // 2 - mh // 2, mw, mh)
            self.quit_box = box
            ws.append(Button((box.x + S(40), box.bottom - S(80), S(200), S(52)), "QUITTER", self.app.quit,
                             style="primary", size=20))
            ws.append(Button((box.right - S(240), box.bottom - S(80), S(200), S(52)), "ANNULER", self._cancel_quit,
                             style="ghost", size=20))
            self.page_widgets = ws
            return
        if name == "ACCUEIL":
            ws.append(Button((c.x + S(36), c.y + S(300), S(300), S(60)), "DÉPLOYER", self.start_game,
                             style="primary", size=24))
            ws.append(Button((c.x + S(352), c.y + S(300), S(240), S(60)), "CHANGER D'OPÉRATION",
                             lambda: self.goto(3), style="ghost", size=16))
        elif name == "JOUER":
            di = DIFFICULTY_ORDER.index(p.data["difficulty"])
            ws.append(Selector((c.x + S(30), c.y + S(250), S(620), S(52)), "Difficulté", DIFFICULTY_ORDER, di,
                               self._set_difficulty))
            ws.append(Button((c.x + S(30), c.bottom - S(100), S(380), S(66)), "DÉPLOYER", self.start_game,
                             style="primary", size=28))
            ws.append(Button((c.x + S(430), c.bottom - S(100), S(220), S(66)), "ARMURERIE", lambda: self.goto(2),
                             style="ghost", size=18))
        elif name == "ARMURERIE":
            self._build_armory(ws)
        elif name == "OPÉRATIONS":
            cw = (c.w - S(60) - S(20)) // 2
            ch = S(170)
            for i, op in enumerate(OPERATIONS):
                x = c.x + S(30) + (i % 2) * (cw + S(20))
                y = c.y + S(80) + (i // 2) * (ch + S(20))
                locked = p.level < op["level"]
                b = Button((x, y, cw, ch), "", callback=lambda op=op: self._select_op(op), style="card",
                           selected=(op["id"] == p.data["operation"]))
                b.enabled = True
                b.op = op
                b.locked = locked
                ws.append(b)
            y = c.y + S(80) + 2 * (ch + S(20)) + S(30)
            bw = (c.w - S(60) - S(40)) // 3
            for i, dn in enumerate(DIFFICULTY_ORDER):
                b = Button((c.x + S(30) + i * (bw + S(20)), y + S(40), bw, S(52)), dn.upper(),
                           callback=lambda dn=dn: self._set_difficulty(DIFFICULTY_ORDER.index(dn)),
                           style="ghost", size=18, selected=(dn == p.data["difficulty"]))
                ws.append(b)
            self.diff_y = y
        elif name == "PARAMÈTRES":
            self.settings_panel.build((c.x, c.y, min(c.w, S(900)), c.h))
        self.page_widgets = ws

    def _cancel_quit(self):
        self.confirm_quit = False
        self.app.audio.play("ui_back", 0.7)
        self.build_page()

    def _set_difficulty(self, i):
        self.app.profile.data["difficulty"] = DIFFICULTY_ORDER[i]
        self.app.profile.save()
        if PAGES[self.page] == "OPÉRATIONS":
            self.build_page()

    def _select_op(self, op):
        p = self.app.profile
        if p.level < op["level"]:
            self.flash(f"Opération verrouillée : niveau {op['level']} requis")
            self.app.audio.play("ui_back", 0.7)
            return
        p.data["operation"] = op["id"]
        p.save()
        self._apply_operation_env()
        self.app.audio.play("ui_confirm", 0.6)
        self.build_page()

    # ---------------- Armurerie -----------------------------------------
    def _build_armory(self, ws):
        c = self.content
        p = self.app.profile
        y = c.y + S(60)
        for wid in WEAPON_ORDER:
            b = Button((c.x, y, S(330), S(96)), "", callback=lambda wid=wid: self._select_weapon(wid),
                       style="card", selected=(wid == self.armory_sel))
            b.wid = wid
            ws.append(b)
            y += S(108)
        wid = self.armory_sel
        owned = wid in p.data["owned_weapons"]
        rx = c.right - S(470)
        ry = c.y + S(60)
        self.stats_rect = pygame.Rect(rx, ry, S(470), S(300))
        if owned:
            eq = p.data["weapon"] == wid
            b = Button((c.x, y + S(10), S(330), S(56)), "ÉQUIPÉ" if eq else "ÉQUIPER", lambda: self._equip(wid),
                       style="primary" if not eq else "ghost", size=20)
            b.enabled = not eq
            ws.append(b)
            uy = ry + S(320)
            for uid, u in UPGRADES.items():
                lvl = p.data["upgrades"][wid][uid]
                if lvl < 3:
                    cost = u["costs"][lvl]
                    lab = f"AMÉLIORER  •  {cost} CR"
                else:
                    lab = "MAXIMUM"
                b = Button((rx + S(250), uy, S(220), S(44)), lab, lambda uid=uid: self._upgrade(wid, uid),
                           style="ghost", size=15)
                b.enabled = lvl < 3
                b.upgrade = (uid, lvl)
                ws.append(b)
                uy += S(54)
        else:
            w = WEAPONS[wid]
            lab = f"ACHETER  •  {w['price']} CR" if p.level >= w["level"] else f"NIVEAU {w['level']} REQUIS"
            b = Button((c.x, y + S(10), S(330), S(56)), lab, lambda: self._buy_weapon(wid), style="primary", size=20)
            b.enabled = p.level >= w["level"]
            ws.append(b)
        # finitions et faisceaux
        sy = c.bottom - S(150)
        x = c.x
        for fid, fname, col, cost in FINISHES:
            b = Button((x, sy, S(54), S(54)), "", lambda fid=fid: self._finish(fid), style="card",
                       selected=(fid == p.data["finish"]))
            b.swatch = (col, fid in p.data["owned_finishes"], cost, fname)
            ws.append(b)
            x += S(64)
        x = c.right - 5 * S(64) + S(10)
        for bid, bname, col, cost in BEAMS:
            b = Button((x, sy, S(54), S(54)), "", lambda bid=bid: self._beam(bid), style="card",
                       selected=(bid == p.data["beam"]))
            b.swatch = (col, bid in p.data["owned_beams"], cost, bname)
            b.beam = True
            ws.append(b)
            x += S(64)

    def _select_weapon(self, wid):
        self.armory_sel = wid
        self.weapon_spin = 0.0
        self.build_page()

    def _equip(self, wid):
        self.app.profile.data["weapon"] = wid
        self.app.profile.save()
        self.app.audio.play("ui_confirm", 0.6)
        self.flash(f"{WEAPONS[wid]['name']} équipé")
        self.build_page()

    def _buy_weapon(self, wid):
        p = self.app.profile
        w = WEAPONS[wid]
        if p.level < w["level"]:
            self.flash(f"Niveau {w['level']} requis")
            return
        if not p.spend(w["price"]):
            self.flash("Crédits insuffisants")
            self.app.audio.play("ui_back", 0.7)
            return
        p.data["owned_weapons"].append(wid)
        p.data["weapon"] = wid
        p.save()
        self.app.audio.play("pickup", 0.7)
        self.flash(f"{w['name']} acquis et équipé")
        self.build_page()

    def _upgrade(self, wid, uid):
        p = self.app.profile
        lvl = p.data["upgrades"][wid][uid]
        if lvl >= 3:
            return
        cost = UPGRADES[uid]["costs"][lvl]
        if not p.spend(cost):
            self.flash("Crédits insuffisants")
            self.app.audio.play("ui_back", 0.7)
            return
        p.data["upgrades"][wid][uid] = lvl + 1
        p.save()
        self.app.audio.play("ui_confirm", 0.6)
        self.flash(f"{UPGRADES[uid]['name']} niveau {lvl + 1}")
        self.build_page()

    def _finish(self, fid):
        p = self.app.profile
        f = next(x for x in FINISHES if x[0] == fid)
        if fid not in p.data["owned_finishes"]:
            if not p.spend(f[3]):
                self.flash("Crédits insuffisants")
                self.app.audio.play("ui_back", 0.7)
                return
            p.data["owned_finishes"].append(fid)
            self.flash(f"Finition « {f[1]} » débloquée")
        p.data["finish"] = fid
        p.save()
        self.app.audio.play("ui_confirm", 0.5)
        self.build_page()

    def _beam(self, bid):
        p = self.app.profile
        b = next(x for x in BEAMS if x[0] == bid)
        if bid not in p.data["owned_beams"]:
            if not p.spend(b[3]):
                self.flash("Crédits insuffisants")
                self.app.audio.play("ui_back", 0.7)
                return
            p.data["owned_beams"].append(bid)
            self.flash(f"Faisceau « {b[1]} » débloqué")
        p.data["beam"] = bid
        p.save()
        self.app.audio.play("ui_confirm", 0.5)
        self.build_page()

    # ------------------------------------------------------------------
    def start_game(self):
        if self.leaving:
            return
        self.app.audio.play("ui_confirm", 0.8)
        self.leaving = "game"
        self.leave_t = 0.0

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            if self.confirm_quit:
                self._cancel_quit()
            elif self.page != 0:
                self.goto(0)
                self.app.audio.play("ui_back", 0.6)
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN and not self.confirm_quit:
            self.start_game()
            return
        if self.leaving:
            return
        if self.confirm_quit:
            for w in self.page_widgets:
                if w.handle(ev):
                    return
            return
        for b in self.nav:
            if b.handle(ev):
                return
        if PAGES[self.page] == "PARAMÈTRES":
            if self.settings_panel.handle(ev):
                return
        for w in list(self.page_widgets):
            if w.handle(ev):
                if not isinstance(w, Selector):
                    pass
                else:
                    self.app.audio.play("ui_click", 0.5)
                return

    def update(self, dt):
        self.t += dt
        self.fade_in = min(1.0, self.fade_in + dt * 1.2)
        self.page_t = min(1.0, self.page_t + dt * 3.2)
        self.message_t = max(0.0, self.message_t - dt)
        self.weapon_spin += dt
        mouse = pygame.mouse.get_pos()
        for b in self.nav:
            if b.update(dt, mouse):
                self.app.audio.play("ui_hover", 0.35)
        for w in self.page_widgets:
            if w.update(dt, mouse):
                self.app.audio.play("ui_hover", 0.35)
        if PAGES[self.page] == "PARAMÈTRES":
            self.settings_panel.update(dt, mouse)
        target = 1.0 if PAGES[self.page] == "ARMURERIE" and not self.confirm_quit else 0.0
        self.studio_k += (target - self.studio_k) * min(1.0, dt * 6)
        self.env.update(dt)
        if self.env.rain > 0 and np.random.random() < dt * 0.06:
            self.env.lightning = 1.0
            self.app.audio.play("thunder", 0.5, variants=2)
        if self.leaving:
            self.leave_t += dt
            if self.leave_t > 0.7:
                self.app.start_game()

    # ------------------------------------------------------------------
    def render(self):
        app = self.app
        W, H = app.size
        f = FrameData()
        f.time = self.t
        studio = self.studio_k > 0.5
        aspect = W / H
        if studio:
            f.studio = True
            f.env = self.studio_env
            wid = self.armory_sel
            p = app.profile
            fin = next(x for x in FINISHES if x[0] == p.data["finish"])
            beam = next(x for x in BEAMS if x[0] == p.data["beam"])
            eye = np.array([0.0, 0.55, 3.3])
            f.view = mu.look_at(eye, (0, -0.05, 0))
            proj = mu.perspective(34, aspect, 0.1, 100)
            c = self.content
            gap_l = c.x + S(340)
            gap_r = c.right - S(480)
            shift = ((gap_l + gap_r) / 2) / W * 2 - 1
            proj[0, 2] = -shift
            f.proj = proj
            f.cam_pos = eye
            f.cam_forward = mu.normalize(-eye)
            spin = self.weapon_spin * 0.6
            scale = {"pulsar": 1.3, "faucon": 0.88, "tempete": 1.35}[wid]
            center_z = {"pulsar": 0.14, "faucon": 0.27, "tempete": 0.13}[wid]
            m = mu.translate(0, 0.0 + 0.03 * math.sin(self.t * 1.5), 0) @ mu.rot_y(spin) @ mu.rot_z(0.08) @ \
                mu.scale(scale) @ mu.translate(0, -0.01, center_z)
            f.dynamic = [DrawItem(app.meshes["pedestal"], mu.translate(0, 0.85, 0), emis=(1, 0.6, 0.2), emis_scale=0.8),
                         DrawItem(app.meshes[f"weapon_{wid}"], m, tint=fin[2], emis=beam[2], emis_scale=0.9)]
            bc = np.array(beam[2])
            f.lights = [((1.5, 1.2, 1.8), 8.0, np.array([10.0, 6.0, 3.0])),
                        ((-1.8, 0.6, -1.0), 8.0, np.array([2.5, 5.0, 9.0])),
                        ((0, -0.6, 0.8), 3.0, bc * 3.0)]
            f.shadow_center = np.zeros(3)
        else:
            a = self.t * 0.035
            r = 150.0
            eye = np.array([math.cos(a) * r, 52.0 + 8 * math.sin(self.t * 0.05), math.sin(a) * r])
            target = np.array([math.cos(a + 0.9) * 40, 14.0, math.sin(a + 0.9) * 40])
            self.cam.pos = eye
            self.cam.look_at_point(target)
            self.cam.fov = 60
            f.view = self.cam.view()
            f.proj = mu.perspective(60, aspect, 0.5, 1700)
            f.cam_pos = eye
            f.cam_forward = self.cam.forward
            f.env = self.env
            f.static_chunks = app.static_chunks
            f.far_meshes = app.far_meshes
            lights = []
            items = []
            for (rad, spd, ph, kind) in self.patrol:
                ang = self.t * spd + ph
                pos = np.array([math.cos(ang) * (60 + rad), 40 + rad * 0.3 + math.sin(self.t + ph) * 2,
                                math.sin(ang) * (60 + rad)])
                yaw = -ang
                mm = mu.translate(*pos) @ mu.rot_y(yaw) @ mu.rot_z(0.15)
                col = DRONES[kind]["color"]
                items.append(DrawItem(app.meshes[f"drone_{kind}"], mm, tint=SHELL_TINT[kind], emis=col, emis_scale=1.0))
                lights.append((pos, 9.0, np.array(col) * 3))
            f.dynamic = items
            if self.env.night > 0.3:
                lights += [(np.array(l), 22.0, np.array([18.0, 12.0, 6.0])) for l in app.city.lamps]
            f.lights = lights
            f.shadow_center = np.array([target[0], 0, target[2]])
        fade = self.fade_in
        if self.leaving:
            fade *= max(0.0, 1.0 - self.leave_t / 0.6)
        f.fade = fade
        app.renderer.render(f)
        surf = app.ui_surface
        surf.fill((0, 0, 0, 0))
        self.draw_ui(surf, fade)
        app.renderer.draw_overlay(surf)

    # ------------------------------------------------------------------
    def draw_ui(self, surf, fade):
        app = self.app
        W, H = app.size
        p = app.profile
        alpha = min(1.0, self.fade_in * 1.5)
        # dégradé de lisibilité à gauche
        if not hasattr(self, "_grad") or self._grad.get_size() != (S(760), H):
            self._grad = T.gradient_h((S(760), H), (4, 6, 10, 225), (4, 6, 10, 0))
            self._grad_b = T.gradient_v((W, S(220)), (0, 0, 0, 0), (0, 0, 0, 170))
        surf.blit(self._grad, (0, 0))
        surf.blit(self._grad_b, (0, H - S(220)))
        # logo
        lx, ly = S(60), S(80)
        T.text(surf, "ZONE DE", (lx, ly), 40, T.ACCENT, bold=True, alpha=255 * alpha)
        T.text(surf, "FRAPPE", (lx - S(4), ly + S(38)), 96, T.WHITE, bold=True, shadow=True, alpha=255 * alpha)
        T.rect(surf, (*T.ACCENT, int(255 * alpha)), (lx, ly + S(146), S(70), S(4)))
        T.text(surf, "PROGRAMME D'ENTRAÎNEMENT TACTIQUE", (lx + S(84), ly + S(138)), 16, T.MUTED, bold=True,
               alpha=255 * alpha)
        for b in self.nav:
            b.draw(surf, alpha)
        # profil (haut droite)
        lvl, prog, need = level_from_xp(p.data["xp"])
        px = W - S(60)
        T.text(surf, f"NIVEAU {lvl}", (px, S(52)), 24, T.WHITE, bold=True, anchor="topright")
        T.bar(surf, (px - S(260), S(86), S(260), S(5)), prog, T.ACCENT)
        T.text(surf, f"{p.data['credits']:,} CR".replace(",", " "), (px - S(280), S(52)), 24, T.ACCENT_2, bold=True,
               anchor="topright")
        op = next(o for o in OPERATIONS if o["id"] == p.data["operation"])
        T.text(surf, f"Opération : {op['name']}  •  {p.data['difficulty']}", (px, S(100)), 16, T.MUTED,
               anchor="topright")
        # pied de page
        T.text(surf, "ZONE DE FRAPPE  v1.0  •  Simulation d'entraînement — drones fictifs", (S(60), H - S(40)), 14,
               T.DIM)
        T.text(surf, "ENTRÉE : déployer   •   ÉCHAP : retour   •   F11 : plein écran", (W - S(60), H - S(40)), 14,
               T.DIM, anchor="bottomright")
        # page courante avec transition (glissement + fondu)
        k = T.ease_out(self.page_t)
        off = int((1 - k) * S(60))
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        self._draw_page(layer)
        layer.set_alpha(int(255 * k * alpha))
        surf.blit(layer, (off, 0))
        if self.message_t > 0:
            T.text(surf, self.message, (W // 2 + S(200), H - S(70)), 20, T.ACCENT_2, bold=True, anchor="center",
                   shadow=True, alpha=255 * min(1.0, self.message_t))
        if self.confirm_quit:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 150))
            surf.blit(ov, (0, 0))
            box = self.quit_box
            T.panel(surf, box, 235, accent=True)
            T.text(surf, "QUITTER ZONE DE FRAPPE ?", (box.x + S(40), box.y + S(36)), 28, T.WHITE, bold=True)
            T.text(surf, "Votre progression est sauvegardée automatiquement.", (box.x + S(40), box.y + S(84)), 18,
                   T.MUTED)
            for w in self.page_widgets:
                w.draw(surf)

    def _draw_page(self, surf):
        if self.confirm_quit:
            return
        name = PAGES[self.page]
        c = self.content
        p = self.app.profile
        op = next(o for o in OPERATIONS if o["id"] == p.data["operation"])
        if name == "ACCUEIL":
            T.text(surf, "BIENVENUE, RECRUE", (c.x, c.y), 18, T.ACCENT, bold=True)
            T.text(surf, "La ville est à vous.", (c.x, c.y + S(26)), 52, T.WHITE, bold=True, shadow=True)
            box = pygame.Rect(c.x, c.y + S(110), S(640), S(280))
            T.panel(surf, box, 185, accent=True)
            T.text(surf, "OPÉRATION SÉLECTIONNÉE", (box.x + S(36), box.y + S(26)), 15, T.MUTED, bold=True)
            T.text(surf, op["name"], (box.x + S(36), box.y + S(50)), 38, T.WHITE, bold=True)
            T.text(surf, f"{op['time']}  •  {op['weather']}  •  {p.data['difficulty']}  •  10 vagues",
                   (box.x + S(36), box.y + S(102)), 18, T.ACCENT_2)
            self._wrap(surf, op["desc"], (box.x + S(36), box.y + S(140)), box.w - S(72), 18, T.TEXT)
            # dernière session
            lr = p.data.get("last_result")
            b2 = pygame.Rect(box.right + S(30), box.y, min(S(420), c.right - box.right - S(30)), S(280))
            if b2.w > S(260):
                T.panel(surf, b2, 170)
                T.text(surf, "DERNIÈRE SESSION", (b2.x + S(28), b2.y + S(26)), 15, T.MUTED, bold=True)
                if lr:
                    res = "VICTOIRE" if lr.get("victory") else "ÉCHEC"
                    T.text(surf, res, (b2.x + S(28), b2.y + S(52)), 32, T.GOOD if lr.get("victory") else T.BAD, bold=True)
                    rows = [("Score", f"{lr['score']:,}".replace(",", " ")), ("Vague atteinte", f"{lr['wave']} / 10"),
                            ("Drones neutralisés", str(lr["kills"])), ("Précision", f"{lr['accuracy']:.0%}")]
                    y = b2.y + S(110)
                    for k_, v in rows:
                        T.text(surf, k_, (b2.x + S(28), y), 17, T.MUTED)
                        T.text(surf, v, (b2.right - S(28), y), 17, T.WHITE, bold=True, anchor="topright")
                        y += S(36)
                else:
                    self._wrap(surf, "Aucune session enregistrée. Déployez-vous pour commencer votre entraînement.",
                               (b2.x + S(28), b2.y + S(60)), b2.w - S(56), 17, T.TEXT)
            tip = TIPS[int(self.t / 7) % len(TIPS)]
            ty = box.bottom + S(40)
            T.text(surf, "CONSEIL D'INSTRUCTEUR", (c.x, ty), 15, T.ACCENT, bold=True)
            self._wrap(surf, tip, (c.x, ty + S(26)), S(900), 19, T.TEXT)
            for wdg in self.page_widgets:
                wdg.draw(surf)
        elif name == "JOUER":
            T.text(surf, "DÉPLOIEMENT", (c.x, c.y), 18, T.ACCENT, bold=True)
            T.text(surf, op["name"], (c.x, c.y + S(26)), 52, T.WHITE, bold=True, shadow=True)
            T.text(surf, f"Heure locale {op['time']}  •  {op['weather']}  •  Centre-ville d'entraînement 420 x 420 m",
                   (c.x, c.y + S(96)), 18, T.ACCENT_2)
            self._wrap(surf, op["desc"] + " Dix vagues de drones fictifs vous attendent, avec missions d'élimination, "
                       "de défense de balise et de collecte de données.", (c.x, c.y + S(140)), S(800), 18, T.TEXT)
            T.text(surf, DIFFICULTIES[p.data["difficulty"]]["desc"], (c.x + S(30), c.y + S(312)), 16, T.MUTED)
            box = pygame.Rect(c.x + S(30), c.y + S(360), S(620), S(150))
            T.panel(surf, box, 170)
            w = WEAPONS[p.data["weapon"]]
            fin = next(x for x in FINISHES if x[0] == p.data["finish"])
            beam = next(x for x in BEAMS if x[0] == p.data["beam"])
            T.text(surf, "ÉQUIPEMENT", (box.x + S(24), box.y + S(20)), 15, T.MUTED, bold=True)
            T.text(surf, w["name"], (box.x + S(24), box.y + S(44)), 30, T.WHITE, bold=True)
            T.text(surf, f"{w['role']}  •  Finition {fin[1]}  •  Faisceau {beam[1]}", (box.x + S(24), box.y + S(88)),
                   17, T.TEXT)
            pygame.draw.rect(surf, tuple(int(x * 255) for x in fin[2]), (box.right - S(110), box.y + S(30), S(30), S(30)))
            pygame.draw.rect(surf, tuple(int(x * 255) for x in beam[2]), (box.right - S(70), box.y + S(30), S(30), S(30)))
            for wdg in self.page_widgets:
                wdg.draw(surf)
        elif name == "ARMURERIE":
            self._draw_armory(surf)
        elif name == "OPÉRATIONS":
            T.text(surf, "OPÉRATIONS", (c.x + S(30), c.y), 18, T.ACCENT, bold=True)
            T.text(surf, "Choisissez votre théâtre d'entraînement", (c.x + S(30), c.y + S(26)), 30, T.WHITE, bold=True)
            for b in self.page_widgets:
                b.draw(surf)
                if hasattr(b, "op"):
                    op_ = b.op
                    r = b.rect
                    T.text(surf, op_["name"], (r.x + S(24), r.y + S(20)), 26, T.WHITE if not b.locked else T.DIM,
                           bold=True)
                    T.text(surf, f"{op_['time']}  •  {op_['weather']}", (r.x + S(24), r.y + S(56)), 16, T.ACCENT_2)
                    self._wrap(surf, op_["desc"], (r.x + S(24), r.y + S(86)), r.w - S(48), 16,
                               T.TEXT if not b.locked else T.DIM)
                    if b.locked:
                        T.text(surf, f"VERROUILLÉ — NIVEAU {op_['level']}", (r.right - S(20), r.y + S(22)), 14, T.BAD,
                               bold=True, anchor="topright")
                    elif b.selected:
                        T.text(surf, "SÉLECTIONNÉE", (r.right - S(20), r.y + S(22)), 14, T.ACCENT, bold=True,
                               anchor="topright")
            T.text(surf, "DIFFICULTÉ", (c.x + S(30), self.diff_y), 18, T.ACCENT, bold=True)
            T.text(surf, DIFFICULTIES[p.data["difficulty"]]["desc"], (c.x + S(160), self.diff_y + S(2)), 16, T.MUTED)
        elif name == "PARAMÈTRES":
            T.text(surf, "PARAMÈTRES", (c.x, c.y - S(40)), 18, T.ACCENT, bold=True)
            self.settings_panel.draw(surf)
        elif name == "STATISTIQUES":
            self._draw_stats(surf)

    def _draw_armory(self, surf):
        c = self.content
        p = self.app.profile
        T.text(surf, "ARMURERIE", (c.x, c.y), 18, T.ACCENT, bold=True)
        T.text(surf, "Émetteurs d'entraînement", (c.x, c.y + S(22)), 26, T.WHITE, bold=True)
        wid = self.armory_sel
        for b in self.page_widgets:
            if hasattr(b, "wid"):
                b.draw(surf)
                w = WEAPONS[b.wid]
                r = b.rect
                owned = b.wid in p.data["owned_weapons"]
                T.text(surf, w["name"], (r.x + S(20), r.y + S(16)), 22, T.WHITE if owned else T.TEXT, bold=True)
                T.text(surf, w["role"], (r.x + S(20), r.y + S(46)), 15, T.MUTED)
                if p.data["weapon"] == b.wid:
                    st, col = "ÉQUIPÉ", T.ACCENT
                elif owned:
                    st, col = "POSSÉDÉ", T.GOOD
                elif p.level < w["level"]:
                    st, col = f"NIVEAU {w['level']}", T.BAD
                else:
                    st, col = f"{w['price']} CR", T.ACCENT_2
                T.text(surf, st, (r.x + S(20), r.y + S(68)), 14, col, bold=True)
        # statistiques (panneau droit)
        sr = self.stats_rect
        ph = S(505) if wid in p.data["owned_weapons"] else S(310)
        T.panel(surf, (sr.x - S(20), sr.y - S(20), sr.w + S(40), ph), 185)
        w = p.weapon_stats(wid) if wid in p.data["owned_weapons"] else WEAPONS[wid]
        T.text(surf, WEAPONS[wid]["name"], (sr.x, sr.y), 30, T.WHITE, bold=True)
        self._wrap(surf, WEAPONS[wid]["desc"], (sr.x, sr.y + S(42)), sr.w, 16, T.TEXT)
        stats = [("DÉGÂTS", min(1.0, w["damage"] * w["pellets"] / 130.0)),
                 ("CADENCE", min(1.0, w["rate"] / 10.0)),
                 ("PRÉCISION", 1.0 - min(1.0, w["spread"] / 0.06)),
                 ("PORTÉE", min(1.0, w["range"] / 320.0)),
                 ("DISSIPATION", min(1.0, w["cool"] / (w["heat"] * 10)))]
        y = sr.y + S(110)
        for name, v in stats:
            T.text(surf, name, (sr.x, y), 15, T.MUTED, bold=True)
            T.bar(surf, (sr.x + S(150), y + S(5), sr.w - S(150), S(8)), v, T.ACCENT, segments=10)
            y += S(34)
        if wid in p.data["owned_weapons"]:
            T.text(surf, "AMÉLIORATIONS", (sr.x, sr.y + S(290)), 15, T.ACCENT, bold=True)
            for b in self.page_widgets:
                if hasattr(b, "upgrade"):
                    uid, lvl = b.upgrade
                    u = UPGRADES[uid]
                    T.text(surf, u["name"], (sr.x, b.rect.y + S(2)), 17, T.WHITE, bold=True)
                    for k in range(3):
                        col = T.ACCENT if k < lvl else (255, 255, 255, 40)
                        T.rect(surf, col, (sr.x + k * S(26), b.rect.y + S(28), S(20), S(6)))
                    T.text(surf, u["desc"], (sr.x + S(90), b.rect.y + S(24)), 13, T.MUTED)
                    b.draw(surf)
        for b in self.page_widgets:
            if not hasattr(b, "wid") and not hasattr(b, "upgrade") and not hasattr(b, "swatch"):
                b.draw(surf)
        # nuanciers
        sy = c.bottom - S(150)
        T.text(surf, "FINITION", (c.x, sy - S(30)), 15, T.ACCENT, bold=True)
        T.text(surf, "COULEUR DU FAISCEAU", (c.right - 5 * S(64) + S(10), sy - S(30)), 15, T.ACCENT, bold=True)
        hover_info = None
        for b in self.page_widgets:
            if hasattr(b, "swatch"):
                col, owned, cost, nm = b.swatch
                b.draw(surf)
                inner = b.rect.inflate(-S(14), -S(14))
                pygame.draw.rect(surf, tuple(int(x * 255) for x in col), inner, border_radius=S(4))
                if not owned:
                    T.rect(surf, (0, 0, 0, 140), inner, S(4))
                    T.text(surf, "CR", inner.center, 13, T.WHITE, bold=True, anchor="center")
                if b.hovered:
                    hover_info = (b.rect, nm, owned, cost)
        if hover_info:
            r, nm, owned, cost = hover_info
            label = nm if owned else f"{nm}  •  {cost} CR"
            T.text(surf, label, (r.centerx, r.bottom + S(12)), 15, T.WHITE, bold=True, anchor="midtop", shadow=True)

    def _draw_stats(self, surf):
        c = self.content
        s = self.app.profile.data["stats"]
        T.text(surf, "STATISTIQUES", (c.x, c.y), 18, T.ACCENT, bold=True)
        T.text(surf, "Dossier de l'opérateur", (c.x, c.y + S(26)), 30, T.WHITE, bold=True)
        acc = s["hits"] / max(1, s["shots"])
        h, rem = divmod(int(s["time_played"]), 3600)
        m = rem // 60
        tiles = [("PARTIES", str(s["games"])), ("VICTOIRES", str(s["victories"])),
                 ("DRONES NEUTRALISÉS", str(s["drones"])), ("PRÉCISION", f"{acc:.0%}"),
                 ("MEILLEUR SCORE", f"{s['best_score']:,}".replace(",", " ")), ("MEILLEURE VAGUE", f"{s['best_wave']} / 10"),
                 ("TEMPS DE JEU", f"{h} h {m:02d}"), ("DISTANCE", f"{s['distance'] / 1000:.2f} km"),
                 ("MODULES RÉCUPÉRÉS", str(s["data_cores"])), ("BALISES CAPTURÉES", str(s["beacons"]))]
        cols = 5
        tw = (c.w - S(20) * (cols - 1)) // cols
        th = S(110)
        for i, (k, v) in enumerate(tiles):
            x = c.x + (i % cols) * (tw + S(20))
            y = c.y + S(90) + (i // cols) * (th + S(20))
            T.panel(surf, (x, y, tw, th), 175)
            T.text(surf, k, (x + S(20), y + S(20)), 14, T.MUTED, bold=True)
            T.text(surf, v, (x + S(20), y + S(46)), 34, T.WHITE, bold=True)
        y = c.y + S(90) + 2 * (th + S(20)) + S(20)
        T.text(surf, "NEUTRALISATIONS PAR TYPE", (c.x, y), 15, T.ACCENT, bold=True)
        kb = s["kills_by_type"]
        total = max(1, sum(kb.values()))
        y += S(36)
        for kind in ("eclaireur", "sentinelle", "blinde"):
            n = kb.get(kind, 0)
            T.text(surf, DRONES[kind]["name"], (c.x, y), 17, T.WHITE, bold=True)
            col = tuple(int(x * 255) for x in DRONES[kind]["color"])
            T.bar(surf, (c.x + S(200), y + S(6), S(500), S(10)), n / total, col)
            T.text(surf, str(n), (c.x + S(720), y), 17, T.TEXT)
            y += S(40)
        lvl, prog, need = level_from_xp(self.app.profile.data["xp"])
        y += S(20)
        T.text(surf, f"PROGRESSION — NIVEAU {lvl}", (c.x, y), 15, T.ACCENT, bold=True)
        T.bar(surf, (c.x, y + S(30), S(720), S(10)), prog, T.ACCENT)
        T.text(surf, f"{int(prog * need)} / {need} XP vers le niveau {lvl + 1}", (c.x, y + S(50)), 16, T.MUTED)

    def _wrap(self, surf, txt, pos, width, size, color):
        f = T.FONTS.get(size)
        words = txt.split()
        line = ""
        y = pos[1]
        for w in words:
            test = (line + " " + w).strip()
            if f.size(test)[0] > width and line:
                T.text(surf, line, (pos[0], y), size, color)
                y += int(f.get_linesize() * 1.1)
                line = w
            else:
                line = test
        if line:
            T.text(surf, line, (pos[0], y), size, color)
        return y
