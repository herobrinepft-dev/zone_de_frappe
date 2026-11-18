"""Thème visuel de l'interface : couleurs, polices, primitives de dessin."""
import math
import pygame

ACCENT = (255, 158, 40)
ACCENT_2 = (255, 196, 90)
CYAN = (90, 200, 255)
WHITE = (238, 240, 244)
TEXT = (214, 219, 228)
MUTED = (140, 148, 162)
DIM = (92, 99, 112)
PANEL = (12, 15, 21, 190)
PANEL_LIGHT = (28, 33, 44, 210)
GOOD = (90, 230, 120)
BAD = (255, 80, 60)
WARN = (255, 200, 60)

FONT_CANDIDATES = "bahnschrift,segoeui,arial"


class Fonts:
    def __init__(self):
        self.cache = {}
        self.text_cache = {}
        self.scale = 1.0

    def set_scale(self, h):
        s = max(0.6, h / 1080.0)
        if abs(s - self.scale) > 1e-3:
            self.scale = s
            self.cache.clear()
            self.text_cache.clear()

    def get(self, size, bold=False):
        px = max(8, int(size * self.scale))
        key = (px, bold)
        f = self.cache.get(key)
        if f is None:
            f = pygame.font.SysFont(FONT_CANDIDATES, px, bold=bold)
            self.cache[key] = f
        return f

    def render(self, text, size, color=TEXT, bold=False):
        key = (text, size, color, bold)
        s = self.text_cache.get(key)
        if s is None:
            s = self.get(size, bold).render(text, True, color[:3])
            if len(color) == 4:
                s.set_alpha(color[3])
            if len(self.text_cache) > 900:
                self.text_cache.clear()
            self.text_cache[key] = s
        return s


FONTS = Fonts()


def S(v):
    """Échelle d'une dimension en pixels de référence (1080p)."""
    return int(round(v * FONTS.scale))


def text(surf, txt, pos, size=24, color=TEXT, bold=False, anchor="topleft", shadow=False, alpha=None):
    img = FONTS.render(txt, size, color, bold)
    if alpha is not None and alpha < 255:
        img = img.copy()
        img.set_alpha(int(alpha))
    r = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if shadow:
        sh = FONTS.render(txt, size, (0, 0, 0), bold)
        sh = sh.copy()
        sh.set_alpha(140 if alpha is None else int(alpha * 0.55))
        surf.blit(sh, r.move(max(1, S(2)), max(1, S(2))))
    surf.blit(img, r)
    return r


def text_size(txt, size, bold=False):
    return FONTS.get(size, bold).size(txt)


def rect(surf, color, r, radius=0, width=0):
    """Rectangle avec alpha correctement mélangé."""
    r = pygame.Rect(r)
    if r.w <= 0 or r.h <= 0:
        return
    if len(color) == 4 and color[3] < 255:
        tmp = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(tmp, color, tmp.get_rect(), width, border_radius=radius)
        surf.blit(tmp, r.topleft)
    else:
        pygame.draw.rect(surf, color, r, width, border_radius=radius)


def panel(surf, r, alpha=190, radius=None, border=True, accent=False):
    r = pygame.Rect(r)
    radius = S(6) if radius is None else radius
    rect(surf, (10, 13, 19, alpha), r, radius)
    if border:
        rect(surf, (255, 255, 255, 28), r, radius, width=1)
    if accent:
        rect(surf, ACCENT, (r.x, r.y + S(10), S(3), r.h - S(20)))


def bar(surf, r, frac, color, back=(255, 255, 255, 30), radius=None, segments=0):
    r = pygame.Rect(r)
    radius = S(2) if radius is None else radius
    rect(surf, back, r, radius)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        rect(surf, color, (r.x, r.y, max(1, int(r.w * frac)), r.h), radius)
    if segments > 1:
        for i in range(1, segments):
            x = r.x + r.w * i // segments
            pygame.draw.line(surf, (8, 10, 14), (x, r.y), (x, r.bottom - 1), max(1, S(2)))


def gradient_h(size, c0, c1):
    w, h = size
    s = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
    for x in range(w):
        t = x / max(1, w - 1)
        c = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(4))
        pygame.draw.line(s, c, (x, 0), (x, h))
    return s


def gradient_v(size, c0, c1):
    w, h = size
    s = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(4))
        pygame.draw.line(s, c, (0, y), (w, y))
    return s


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return 3 * t * t - 2 * t * t * t


def arc(surf, color, center, radius, a0, a1, width):
    pts_o, pts_i = [], []
    n = max(6, int(abs(a1 - a0) * radius / 6))
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        pts_o.append((center[0] + math.cos(a) * radius, center[1] + math.sin(a) * radius))
        pts_i.append((center[0] + math.cos(a) * (radius - width), center[1] + math.sin(a) * (radius - width)))
    poly = pts_o + pts_i[::-1]
    if len(color) == 4:
        minx = int(min(p[0] for p in poly)) - 1
        miny = int(min(p[1] for p in poly)) - 1
        maxx = int(max(p[0] for p in poly)) + 2
        maxy = int(max(p[1] for p in poly)) + 2
        tmp = pygame.Surface((maxx - minx, maxy - miny), pygame.SRCALPHA)
        pygame.draw.polygon(tmp, color, [(x - minx, y - miny) for x, y in poly])
        surf.blit(tmp, (minx, miny))
    else:
        pygame.draw.polygon(surf, color, poly)
