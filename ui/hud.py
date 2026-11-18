"""Interface en jeu (HUD) : discrète, lisible, entièrement transparente hors éléments."""
import math
import numpy as np
import pygame

from engine import mathutils as mu
from gameplay.data import TOTAL_WAVES, WEAPONS, WEAPON_ORDER
from ui import theme as T
from ui.theme import S


class Minimap:
    PX = 2.0  # pixels par mètre

    def __init__(self, city):
        half = city.half + 4
        self.half = half
        size = int(2 * half * self.PX)
        self.size = size
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        s.fill((22, 25, 30, 255))

        def to(x, z):
            return (int((x + half) * self.PX), int((z + half) * self.PX))

        from gameplay.city import N, road_c, ROAD
        for i in range(N):
            for j in range(N):
                x0, x1 = road_c(i) + ROAD / 2, road_c(i + 1) - ROAD / 2
                z0, z1 = road_c(j) + ROAD / 2, road_c(j + 1) - ROAD / 2
                a, b = to(x0, z0), to(x1, z1)
                pygame.draw.rect(s, (52, 56, 64), (a[0], a[1], b[0] - a[0], b[1] - a[1]))
        for (x0, z0, x1, z1) in city.parks:
            a, b = to(x0, z0), to(x1, z1)
            pygame.draw.rect(s, (44, 78, 46), (a[0], a[1], b[0] - a[0], b[1] - a[1]))
        for (x0, z0, x1, z1) in city.plazas:
            a, b = to(x0, z0), to(x1, z1)
            pygame.draw.rect(s, (88, 82, 70), (a[0], a[1], b[0] - a[0], b[1] - a[1]))
        for (x0, z0, x1, z1, h) in city.buildings:
            a, b = to(x0, z0), to(x1, z1)
            shade = int(min(140, 80 + h * 0.8))
            pygame.draw.rect(s, (shade - 10, shade, shade + 14), (a[0], a[1], b[0] - a[0], b[1] - a[1]))
            pygame.draw.rect(s, (shade + 30, shade + 40, shade + 55), (a[0], a[1], b[0] - a[0], b[1] - a[1]), 1)
        w = to(-city.half, -city.half)
        e = to(city.half, city.half)
        pygame.draw.rect(s, (255, 158, 40), (w[0], w[1], e[0] - w[0], e[1] - w[1]), 2)
        self.surf = s
        self.mask_cache = {}

    def mask(self, d):
        m = self.mask_cache.get(d)
        if m is None:
            m = pygame.Surface((d, d), pygame.SRCALPHA)
            m.fill((255, 255, 255, 0))
            pygame.draw.circle(m, (255, 255, 255, 255), (d // 2, d // 2), d // 2)
            self.mask_cache = {d: m}
        return m

    def draw(self, surf, center, diameter, pos, yaw, session, range_m=80.0):
        d = diameter
        px = self.PX
        crop = int(range_m * 2 * px * 1.45)
        cx = int((pos[0] + self.half) * px)
        cz = int((pos[2] + self.half) * px)
        area = pygame.Rect(cx - crop // 2, cz - crop // 2, crop, crop)
        sub = pygame.Surface((crop, crop), pygame.SRCALPHA)
        sub.fill((14, 16, 20, 255))
        sub.blit(self.surf, (0, 0), area)
        rot = pygame.transform.rotate(sub, math.degrees(yaw))
        rr = rot.get_rect()
        view = int(range_m * 2 * px)
        cut = pygame.Rect(0, 0, view, view)
        cut.center = rr.center
        piece = rot.subsurface(cut.clip(rr)).copy()
        piece = pygame.transform.smoothscale(piece, (d, d))
        piece.blit(self.mask(d), (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        piece.set_alpha(220)
        x0, y0 = center[0] - d // 2, center[1] - d // 2
        pygame.draw.circle(surf, (8, 10, 14, 200), center, d // 2 + S(5))
        surf.blit(piece, (x0, y0))
        pygame.draw.circle(surf, (255, 255, 255, 60), center, d // 2 + S(4), 1)
        scale = d / (range_m * 2)
        cy, sy = math.cos(yaw), math.sin(yaw)

        def to_screen(p, clamp=True):
            dx, dz = p[0] - pos[0], p[2] - pos[2]
            sx = dx * cy + dz * sy
            sz = -dx * sy + dz * cy
            v = np.array([sx, sz]) * scale
            ln = np.linalg.norm(v)
            edge = False
            lim = d / 2 - S(8)
            if ln > lim:
                if not clamp:
                    return None, False
                v = v / ln * lim
                edge = True
            return (int(center[0] + v[0]), int(center[1] + v[1])), edge

        # anneaux d'objectifs
        w = session.waves
        if w.beacon is not None and w.state == "active":
            pt, edge = to_screen(w.beacon)
            pygame.draw.circle(surf, (255, 160, 40), pt, max(3, int(7 * scale)) if not edge else S(5), 2)
        for pk in session.pickups:
            pt, edge = to_screen(pk.pos, clamp=pk.kind == "data")
            if pt:
                col = tuple(int(c * 255) for c in pk.info["color"])
                pygame.draw.rect(surf, col, (pt[0] - S(3), pt[1] - S(3), S(7), S(7)))
        for dr in session.drones:
            if not dr.alive:
                continue
            pt, edge = to_screen(dr.pos)
            col = (255, 70, 50) if dr.kind != "blinde" else (255, 190, 40)
            r = S(4) if dr.kind != "blinde" else S(6)
            if edge:
                pygame.draw.circle(surf, (*col, 150), pt, S(3))
            else:
                pygame.draw.circle(surf, col, pt, r)
                pygame.draw.circle(surf, (0, 0, 0), pt, r, 1)
        # joueur
        c = center
        pts = [(c[0], c[1] - S(9)), (c[0] - S(6), c[1] + S(6)), (c[0], c[1] + S(2)), (c[0] + S(6), c[1] + S(6))]
        pygame.draw.polygon(surf, T.WHITE, pts)
        # nord
        n_ang = -yaw
        nx = center[0] + math.sin(n_ang) * (d / 2 - S(2))
        ny = center[1] - math.cos(n_ang) * (d / 2 - S(2))
        pygame.draw.circle(surf, (10, 12, 16), (int(nx), int(ny)), S(10))
        T.text(surf, "N", (nx, ny), 14, T.ACCENT, bold=True, anchor="center")


class HUD:
    def __init__(self, app, city):
        self.app = app
        self.minimap = Minimap(city)
        self.score_disp = 0.0
        self.health_disp = 100.0
        self.health_lag = 100.0

    def draw(self, surf, session, cam, vp, dt, fps, aiming):
        W, H = surf.get_size()
        p = session.player
        w = session.weapon
        self.score_disp += (session.score - self.score_disp) * min(1.0, dt * 8)
        self.health_disp += (p.health - self.health_disp) * min(1.0, dt * 12)
        if self.health_lag > self.health_disp:
            self.health_lag = max(self.health_disp, self.health_lag - dt * 25)
        else:
            self.health_lag = self.health_disp

        self._waypoints(surf, session, cam, vp)
        self._crosshair(surf, session, aiming)
        self._damage_dirs(surf, session, cam)

        # ---- mini-carte + objectif --------------------------------------
        md = S(230)
        mc = (S(36) + md // 2, S(36) + md // 2)
        self.minimap.draw(surf, mc, md, p.pos, cam.yaw, session)
        ox, oy = S(26), S(36) + md + S(22)
        txt, prog = session.waves.objective
        ow = S(400)
        T.panel(surf, (ox, oy, ow, S(88) if prog is not None else S(64)), 170, accent=True)
        st = session.waves.state
        title = "OBJECTIF" if st == "active" else ("INTERVALLE" if st == "intermission" else "TERMINÉ")
        T.text(surf, title, (ox + S(18), oy + S(10)), 15, T.ACCENT, bold=True)
        tw = ow - S(36)
        f = T.FONTS.get(18)
        line = txt
        while f.size(line)[0] > tw and len(line) > 4:
            line = line[:-2]
        if line != txt:
            line = line.rstrip() + "…"
        T.text(surf, line, (ox + S(18), oy + S(32)), 18, T.WHITE)
        if prog is not None:
            T.bar(surf, (ox + S(18), oy + S(64), ow - S(36), S(6)), prog, T.ACCENT)
        if st == "intermission" and not session.over:
            t = max(0.0, session.waves.timer)
            T.text(surf, f"Prochaine vague dans {t:0.0f} s", (ox + S(18), oy + S(64 if prog is not None else 44) + S(28)),
                   16, T.MUTED)

        # ---- vague + chrono (haut centre) ----------------------------------
        cx = W // 2
        mins, secs = divmod(int(session.time), 60)
        T.panel(surf, (cx - S(130), S(20), S(260), S(64)), 150)
        T.text(surf, f"VAGUE {max(1, session.waves.wave)} / {TOTAL_WAVES}", (cx, S(28)), 22, T.WHITE, bold=True,
               anchor="midtop")
        alive = sum(1 for d in session.drones if d.alive)
        T.text(surf, f"{mins:02d}:{secs:02d}   •   {alive} drone{'s' if alive > 1 else ''} actif{'s' if alive > 1 else ''}",
               (cx, S(56)), 16, T.MUTED, anchor="midtop")

        # ---- score (haut droite) -----------------------------------------
        rx = W - S(36)
        T.text(surf, "SCORE", (rx, S(24)), 15, T.MUTED, bold=True, anchor="topright")
        T.text(surf, f"{int(self.score_disp):,}".replace(",", " "), (rx, S(40)), 44, T.WHITE, bold=True,
               anchor="topright", shadow=True)
        if session.combo > 1.01:
            col = T.ACCENT if session.combo < 3 else T.BAD
            T.text(surf, f"COMBO x{session.combo:.2f}", (rx, S(96)), 20, col, bold=True, anchor="topright")
            T.bar(surf, (rx - S(140), S(122), S(140), S(4)), max(0.0, session.combo_timer / 3.5), col)
        if self.app.settings["show_fps"]:
            T.text(surf, f"{fps:.0f} FPS", (W - S(12), H - S(12)), 14, T.DIM, anchor="bottomright")
        # fil d'éliminations
        fy = S(140)
        for txt_, pts, age in reversed(session.feed):
            a = 255 * min(1.0, (4.0 - age) * 2)
            r = T.text(surf, f"+{pts}", (rx, fy), 17, T.ACCENT, bold=True, anchor="topright", alpha=a)
            T.text(surf, txt_, (r.x - S(10), fy), 17, T.TEXT, anchor="topright", alpha=a)
            fy += S(26)

        # ---- intégrité (bas gauche) ----------------------------------------
        bx, by = S(36), H - S(110)
        T.panel(surf, (bx - S(10), by - S(14), S(380), S(96)), 160)
        T.text(surf, "INTÉGRITÉ", (bx + S(6), by - S(4)), 15, T.MUTED, bold=True)
        hp = self.health_disp / p.max_health
        col = T.GOOD if hp > 0.5 else (T.WARN if hp > 0.25 else T.BAD)
        T.text(surf, f"{int(math.ceil(p.health))}", (bx + S(354), by - S(12)), 40, T.WHITE, bold=True, anchor="topright")
        br = pygame.Rect(bx + S(6), by + S(30), S(270), S(14))
        T.rect(surf, (255, 255, 255, 25), br, S(2))
        T.rect(surf, (255, 255, 255, 120), (br.x, br.y, int(br.w * self.health_lag / p.max_health), br.h), S(2))
        T.bar(surf, br, hp, col, back=(0, 0, 0, 0), segments=10)
        T.bar(surf, (bx + S(6), by + S(52), S(270), S(4)), p.stamina, (120, 190, 255), back=(255, 255, 255, 20))
        if p.sprinting:
            T.text(surf, "SPRINT", (bx + S(282), by + S(46)), 13, (120, 190, 255), bold=True)

        # ---- émetteur (bas droite) ---------------------------------------
        wx = W - S(36)
        wy = H - S(124)
        T.panel(surf, (wx - S(360), wy - S(10), S(370), S(110)), 160)
        T.text(surf, w.s["name"], (wx - S(6), wy), 24, T.WHITE, bold=True, anchor="topright")
        T.text(surf, w.s["role"].upper(), (wx - S(6), wy + S(30)), 14, T.MUTED, anchor="topright")
        heat = w.heat
        hcol = (int(90 + 165 * heat), int(200 - 140 * heat), int(255 - 215 * heat))
        if w.overheated:
            hcol = T.BAD if int(session.time * 8) % 2 == 0 else (120, 30, 20)
        T.bar(surf, (wx - S(340), wy + S(58), S(334), S(8)), heat, hcol)
        lab = "SURCHAUFFE" if w.overheated else ("SURCHARGE" if w.overcharge > 0 else "CHALEUR")
        T.text(surf, lab, (wx - S(340), wy + S(72)), 13, T.BAD if w.overheated else (T.ACCENT if w.overcharge > 0 else T.MUTED), bold=True)
        owned = self.app.profile.data["owned_weapons"]
        sx = wx - S(6)
        for i, wid in reversed(list(enumerate(WEAPON_ORDER))):
            active = wid == w.id
            have = wid in owned
            col = T.ACCENT if active else (T.TEXT if have else T.DIM)
            r = T.text(surf, f"{i + 1}", (sx, wy + S(72)), 14, col, bold=True, anchor="topright")
            sx = r.x - S(14)

        # ---- notifications & bannière ---------------------------------------
        ny = int(H * 0.68)
        for txt_, colr, age in session.messages:
            a = 255 * min(1.0, (3.0 - age) * 2, age * 6)
            c = tuple(int(x * 255) for x in colr)
            T.text(surf, txt_, (W // 2, ny), 20, c, bold=True, anchor="center", shadow=True, alpha=a)
            ny += S(28)
        if session.banner:
            title, sub, age = session.banner
            k = T.ease_out(age * 2.5)
            fade = 1.0 if session.over else min(1.0, (4.0 - age) * 1.5)
            a = 255 * min(k, fade)
            y = int(H * 0.22 - (1 - k) * S(30))
            bw = S(620)
            g = T.gradient_h((bw // 2, S(92)), (0, 0, 0, 0), (0, 0, 0, int(160 * min(k, fade))))
            surf.blit(g, (W // 2 - bw // 2, y - S(14)))
            surf.blit(pygame.transform.flip(g, True, False), (W // 2, y - S(14)))
            T.rect(surf, (*T.ACCENT, int(a)), (W // 2 - int(S(140) * k), y - S(16), int(S(280) * k), S(3)))
            T.text(surf, title, (W // 2, y), 44, T.WHITE, bold=True, anchor="midtop", shadow=True, alpha=a)
            T.text(surf, sub, (W // 2, y + S(54)), 18, T.ACCENT_2, anchor="midtop", alpha=a)

    # ------------------------------------------------------------------
    def _crosshair(self, surf, session, aiming):
        W, H = surf.get_size()
        c = (W // 2, H // 2)
        w = session.weapon
        spread = w.current_spread * (0.45 if aiming else 1.0)
        gap = S(6) + int(spread * H * 1.6)
        ln = S(10)
        col = (255, 255, 255, 220) if not w.overheated else (255, 90, 60, 200)
        th = max(1, S(2))
        if not (aiming and w.id == "faucon"):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a = (c[0] + dx * gap, c[1] + dy * gap)
                b = (c[0] + dx * (gap + ln), c[1] + dy * (gap + ln))
                pygame.draw.line(surf, (0, 0, 0, 120), (a[0] + 1, a[1] + 1), (b[0] + 1, b[1] + 1), th)
                pygame.draw.line(surf, col, a, b, th)
        pygame.draw.circle(surf, col, c, max(1, S(2)))
        if aiming and w.id == "faucon":
            r = int(H * 0.36)
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 235))
            pygame.draw.circle(ov, (0, 0, 0, 0), c, r)
            surf.blit(ov, (0, 0))
            pygame.draw.circle(surf, (0, 0, 0, 255), c, r, S(6))
            pygame.draw.line(surf, (0, 0, 0, 200), (c[0] - r, c[1]), (c[0] - S(20), c[1]), th)
            pygame.draw.line(surf, (0, 0, 0, 200), (c[0] + S(20), c[1]), (c[0] + r, c[1]), th)
            pygame.draw.line(surf, (0, 0, 0, 200), (c[0], c[1] + S(20)), (c[0], c[1] + r), th)
            pygame.draw.circle(surf, (255, 80, 40), c, S(3))
        if session.hitmarker > 0:
            k = session.hitmarker / 0.18
            g = S(8)
            l2 = S(8) + int(S(6) * k)
            colh = (255, 255, 255, int(255 * k)) if session.killmarker <= 0 else (255, 70, 50, 255)
            for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                pygame.draw.line(surf, colh, (c[0] + sx * g, c[1] + sy * g), (c[0] + sx * l2, c[1] + sy * l2), max(2, S(3)))

    def _damage_dirs(self, surf, session, cam):
        W, H = surf.get_size()
        c = (W // 2, H // 2)
        for ang, age in session.damage_dirs:
            rel = ang - cam.yaw
            a = 1.0 - age / 1.2
            mid = rel - math.pi / 2
            T.arc(surf, (255, 50, 30, int(200 * a)), c, S(150), mid - 0.35, mid + 0.35, S(10))

    def _waypoints(self, surf, session, cam, vp):
        W, H = surf.get_size()
        for pos, label, col in session.waves.waypoints():
            x, y, front = mu.project(vp, pos, W, H)
            dist = float(np.linalg.norm(np.asarray(pos) - cam.pos))
            margin = S(60)
            on = front and margin < x < W - margin and margin < y < H - margin
            c = tuple(int(v * 255) for v in col)
            if not on:
                dx, dy = x - W / 2, y - H / 2
                if not front:
                    dx, dy = -dx, -dy
                    if abs(dx) < 1 and abs(dy) < 1:
                        dy = 1
                s = min((W / 2 - margin) / max(abs(dx), 1e-3), (H / 2 - margin) / max(abs(dy), 1e-3))
                x, y = W / 2 + dx * s, H / 2 + dy * s
                ang = math.atan2(dy, dx)
                tip = (x + math.cos(ang) * S(18), y + math.sin(ang) * S(18))
                l = (x + math.cos(ang + 2.5) * S(10), y + math.sin(ang + 2.5) * S(10))
                r = (x + math.cos(ang - 2.5) * S(10), y + math.sin(ang - 2.5) * S(10))
                pygame.draw.polygon(surf, c, [tip, l, r])
            pygame.draw.circle(surf, (*c, 60), (int(x), int(y)), S(14))
            pygame.draw.circle(surf, c, (int(x), int(y)), S(14), max(1, S(2)))
            pygame.draw.circle(surf, c, (int(x), int(y)), S(4))
            T.text(surf, label, (x, y - S(22)), 15, c, bold=True, anchor="midbottom", shadow=True)
            T.text(surf, f"{dist:.0f} m", (x, y + S(20)), 14, T.WHITE, anchor="midtop", shadow=True)
