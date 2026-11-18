"""Panneau des paramètres (partagé entre le menu principal et le menu pause)."""
import pygame

from config.settings import QUALITY_LEVELS, RESOLUTIONS
from ui import theme as T
from ui.theme import S
from ui.widgets import Button, Slider, Toggle, Selector

TABS = ["GRAPHISMES", "CONTRÔLES", "AUDIO"]


class SettingsPanel:
    def __init__(self, app):
        self.app = app
        self.tab = 0
        self.widgets = []
        self.tab_buttons = []
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.pending_res = None
        self.pending_fs = None
        self.notice = ""
        self.notice_t = 0.0

    def build(self, rect):
        self.rect = pygame.Rect(rect)
        st = self.app.settings
        r = self.rect
        self.tab_buttons = []
        tw = (r.w - S(40)) // 3
        for i, name in enumerate(TABS):
            b = Button((r.x + S(20) + i * tw, r.y + S(20), tw - S(8), S(42)), name,
                       callback=lambda i=i: self._set_tab(i), style="ghost", size=18, selected=(i == self.tab))
            self.tab_buttons.append(b)
        x, w = r.x + S(20), r.w - S(40)
        y = r.y + S(84)
        rh, gap = S(48), S(8)
        ws = []

        def row():
            nonlocal y
            rr = (x, y, w, rh)
            y += rh + gap
            return rr

        if self.tab == 0:
            qi = QUALITY_LEVELS.index(st["quality"])
            ws.append(Selector(row(), "Qualité graphique", QUALITY_LEVELS, qi, self._quality))
            res_opts = [f"{a} x {b}" for a, b in RESOLUTIONS]
            cur = tuple(st["resolution"])
            ri = RESOLUTIONS.index(cur) if cur in RESOLUTIONS else 2
            ws.append(Selector(row(), "Résolution", res_opts, ri, self._res))
            ws.append(Toggle(row(), "Plein écran", st["fullscreen"], self._fs))
            ws.append(Toggle(row(), "Synchronisation verticale", st["vsync"], self._vsync))
            ws.append(Slider(row(), "Champ de vision", st["fov"], 65, 105, lambda v: self._set("fov", v),
                             fmt="{:.0f}°", step=1))
            ws.append(Slider(row(), "Luminosité", st["brightness"], 0.6, 1.6, lambda v: self._set("brightness", v),
                             fmt="{:.0%}", step=0.05))
            ws.append(Toggle(row(), "Effets météo et particules d'ambiance", st["weather_effects"],
                             lambda v: self._set("weather_effects", v)))
            ws.append(Toggle(row(), "Afficher les FPS", st["show_fps"], lambda v: self._set("show_fps", v)))
            ab = Button((x, y + S(6), S(300), S(46)), "APPLIQUER L'AFFICHAGE", self._apply_display, style="primary",
                        size=18)
            ws.append(ab)
        elif self.tab == 1:
            ws.append(Slider(row(), "Sensibilité de la souris", st["sensitivity"], 0.2, 3.0,
                             lambda v: self._set("sensitivity", v), fmt="{:.2f}", step=0.05))
            ws.append(Toggle(row(), "Inverser l'axe vertical", st["invert_y"], lambda v: self._set("invert_y", v)))
            ws.append(Toggle(row(), "Balancement de la caméra", st["head_bob"], lambda v: self._set("head_bob", v)))
            self.keys_y = y + S(10)
        else:
            ws.append(Slider(row(), "Volume général", st["master_volume"], 0, 1, self._vol("master_volume"), step=0.05))
            ws.append(Slider(row(), "Musique", st["music_volume"], 0, 1, self._vol("music_volume"), step=0.05))
            ws.append(Slider(row(), "Effets sonores", st["sfx_volume"], 0, 1, self._vol("sfx_volume"), step=0.05))
        self.widgets = ws

    def _set_tab(self, i):
        self.tab = i
        self.app.audio.play("ui_click", 0.6)
        self.build(self.rect)

    def _set(self, key, v):
        self.app.settings[key] = v
        self.app.settings.save()

    def _vol(self, key):
        def f(v):
            self._set(key, v)
            self.app.audio.refresh_volumes()
        return f

    def _vsync(self, v):
        self._set("vsync", v)
        self.app.request_display_change()

    def _quality(self, i):
        self._set("quality", QUALITY_LEVELS[i])
        self.app.apply_quality()
        self._notice(f"Qualité « {QUALITY_LEVELS[i]} » appliquée")

    def _res(self, i):
        self.pending_res = list(RESOLUTIONS[i])
        self._notice("Cliquez sur « Appliquer l'affichage » pour valider")

    def _fs(self, v):
        self.pending_fs = v
        self._notice("Cliquez sur « Appliquer l'affichage » pour valider")

    def _apply_display(self):
        st = self.app.settings
        res = self.pending_res or st["resolution"]
        fs = st["fullscreen"] if self.pending_fs is None else self.pending_fs
        st["resolution"] = list(res)
        st["fullscreen"] = fs
        st.save()
        self.pending_res = self.pending_fs = None
        self.app.request_display_change()
        self._notice("Affichage mis à jour")

    def _notice(self, txt):
        self.notice = txt
        self.notice_t = 3.0

    def update(self, dt, mouse):
        self.notice_t = max(0.0, self.notice_t - dt)
        for b in self.tab_buttons:
            b.update(dt, mouse)
        for w in self.widgets:
            if w.update(dt, mouse):
                self.app.audio.play("ui_hover", 0.4)

    def handle(self, ev):
        for b in self.tab_buttons:
            if b.handle(ev):
                return True
        for w in self.widgets:
            if w.handle(ev):
                if not isinstance(w, Slider):
                    self.app.audio.play("ui_click", 0.5)
                return True
        return False

    def draw(self, surf, alpha=1.0):
        T.panel(surf, self.rect, int(200 * alpha))
        for b in self.tab_buttons:
            b.draw(surf, alpha)
        for w in self.widgets:
            w.draw(surf, alpha)
        if self.tab == 1:
            keys = [("ZQSD / WASD", "Se déplacer"), ("Souris", "Viser"), ("Clic gauche", "Tirer"),
                    ("Clic droit", "Visée précise"), ("Maj", "Sprint"), ("Espace", "Sauter"),
                    ("Ctrl / C", "S'accroupir"), ("1 2 3", "Changer d'émetteur"), ("Échap", "Pause"),
                    ("F11", "Plein écran"), ("F12", "Capture d'écran")]
            y = self.keys_y
            T.text(surf, "COMMANDES", (self.rect.x + S(20), y), 18, T.ACCENT, bold=True, alpha=255 * alpha)
            y += S(32)
            col_w = (self.rect.w - S(40)) // 2
            for i, (k, d) in enumerate(keys):
                cx = self.rect.x + S(20) + (i % 2) * col_w
                cy = y + (i // 2) * S(34)
                kr = T.text(surf, k, (cx, cy), 17, T.WHITE, bold=True, alpha=255 * alpha)
                T.text(surf, d, (cx + S(150), cy), 17, T.MUTED, alpha=255 * alpha)
        if self.notice_t > 0:
            T.text(surf, self.notice, (self.rect.x + S(20), self.rect.bottom - S(30)), 17, T.ACCENT_2,
                   alpha=255 * min(1.0, self.notice_t) * alpha)
