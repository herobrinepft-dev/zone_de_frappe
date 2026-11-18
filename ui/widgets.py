"""Widgets interactifs : boutons animés, curseurs, interrupteurs, sélecteurs."""
import pygame

from ui import theme as T
from ui.theme import S


class Widget:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.hover = 0.0
        self.hovered = False
        self.enabled = True
        self.visible = True

    def update(self, dt, mouse):
        was = self.hovered
        self.hovered = self.visible and self.enabled and self.rect.collidepoint(mouse)
        target = 1.0 if self.hovered else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 14.0)
        return self.hovered and not was

    def handle(self, ev):
        return False

    def draw(self, surf, alpha=1.0):
        pass


class Button(Widget):
    """Bouton avec barre d'accent animée, décalage du texte et lueur au survol."""

    def __init__(self, rect, label, callback=None, style="nav", sub=None, size=26, selected=False, icon=None):
        super().__init__(rect)
        self.label = label
        self.callback = callback
        self.style = style
        self.sub = sub
        self.size = size
        self.selected = selected
        self.press = 0.0
        self.icon = icon

    def update(self, dt, mouse):
        r = super().update(dt, mouse)
        self.press = max(0.0, self.press - dt * 5)
        return r

    def handle(self, ev):
        if not (self.visible and self.enabled):
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.press = 1.0
            if self.callback:
                self.callback()
            return True
        return False

    def draw(self, surf, alpha=1.0):
        if not self.visible:
            return
        r = self.rect
        h = self.hover
        a = int(255 * alpha)
        if self.style == "nav":
            sel = 1.0 if self.selected else 0.0
            k = max(h, sel)
            if k > 0.01:
                g = T.gradient_h((r.w, r.h), (255, 158, 40, int(70 * k * alpha)), (255, 158, 40, 0))
                surf.blit(g, r.topleft)
            bar_w = S(4)
            bh = int(r.h * (0.35 + 0.65 * k))
            T.rect(surf, (*T.ACCENT, int(255 * alpha * (0.35 + 0.65 * k))),
                   (r.x, r.centery - bh // 2, bar_w, bh))
            col = T.WHITE if k > 0.5 else T.TEXT
            if not self.enabled:
                col = T.DIM
            T.text(surf, self.label, (r.x + S(22) + S(14) * k, r.centery), self.size, col, bold=True,
                   anchor="midleft", alpha=a)
            if self.sub:
                T.text(surf, self.sub, (r.right - S(10), r.centery), 16, T.MUTED, anchor="midright", alpha=a * k)
        elif self.style == "primary":
            glow = int(60 + 120 * h)
            if not self.enabled:
                T.rect(surf, (255, 255, 255, int(22 * alpha)), r, S(4))
                T.rect(surf, (255, 255, 255, int(50 * alpha)), r, S(4), width=1)
                T.text(surf, self.label, r.center, self.size, T.DIM, bold=True, anchor="center", alpha=a)
                return
            T.rect(surf, (*T.ACCENT, int(min(255, (200 + 55 * h)) * alpha)), r, S(4))
            if h > 0.01:
                g = int(S(8) * h)
                T.rect(surf, (255, 220, 160, int(glow * alpha * 0.5)), r.inflate(g, g), S(6), width=max(1, S(2)))
            col = (20, 14, 6) if self.enabled else T.DIM
            T.text(surf, self.label, r.center, self.size, col, bold=True, anchor="center", alpha=a)
        elif self.style == "ghost":
            T.rect(surf, (255, 255, 255, int((18 + 40 * h) * alpha)), r, S(4))
            T.rect(surf, (*(T.ACCENT if self.selected else (255, 255, 255)), int((60 + 120 * h) * alpha)), r, S(4), width=1)
            col = T.WHITE if self.enabled else T.DIM
            T.text(surf, self.label, r.center, self.size, col, bold=True, anchor="center", alpha=a)
        elif self.style == "card":
            T.rect(surf, (14, 18, 26, int((200 + 30 * h) * alpha)), r, S(6))
            border = T.ACCENT if self.selected else (255, 255, 255)
            T.rect(surf, (*border, int((50 + 150 * max(h, 1.0 if self.selected else 0)) * alpha)), r, S(6), width=max(1, S(2)))
        if self.press > 0:
            T.rect(surf, (255, 255, 255, int(70 * self.press * alpha)), r, S(4))


class Slider(Widget):
    def __init__(self, rect, label, value, lo, hi, callback=None, fmt="{:.0%}", step=None):
        super().__init__(rect)
        self.label = label
        self.value = value
        self.lo, self.hi = lo, hi
        self.callback = callback
        self.fmt = fmt
        self.drag = False
        self.step = step

    @property
    def track(self):
        r = self.rect
        return pygame.Rect(r.x + int(r.w * 0.45), r.centery - S(3), int(r.w * 0.42), S(6))

    def _set_from(self, x):
        tr = self.track
        t = max(0.0, min(1.0, (x - tr.x) / tr.w))
        v = self.lo + (self.hi - self.lo) * t
        if self.step:
            v = round(v / self.step) * self.step
        if v != self.value:
            self.value = v
            if self.callback:
                self.callback(v)

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.drag = True
            self._set_from(ev.pos[0])
            return True
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.drag = False
        if ev.type == pygame.MOUSEMOTION and self.drag:
            self._set_from(ev.pos[0])
            return True
        return False

    def draw(self, surf, alpha=1.0):
        r = self.rect
        a = int(255 * alpha)
        T.rect(surf, (255, 255, 255, int((10 + 25 * self.hover) * alpha)), r, S(4))
        T.text(surf, self.label, (r.x + S(16), r.centery), 20, T.TEXT, anchor="midleft", alpha=a)
        tr = self.track
        t = (self.value - self.lo) / (self.hi - self.lo)
        T.bar(surf, tr, t, (*T.ACCENT, a), back=(255, 255, 255, int(40 * alpha)))
        kx = tr.x + int(tr.w * t)
        pygame.draw.circle(surf, (*T.WHITE, a), (kx, tr.centery), S(8) if self.hover > 0.5 or self.drag else S(6))
        T.text(surf, self.fmt.format(self.value), (r.right - S(14), r.centery), 20, T.WHITE, anchor="midright",
               bold=True, alpha=a)


class Toggle(Widget):
    def __init__(self, rect, label, value, callback=None):
        super().__init__(rect)
        self.label = label
        self.value = value
        self.callback = callback
        self.anim = 1.0 if value else 0.0

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            self.value = not self.value
            if self.callback:
                self.callback(self.value)
            return True
        return False

    def update(self, dt, mouse):
        r = super().update(dt, mouse)
        self.anim += ((1.0 if self.value else 0.0) - self.anim) * min(1.0, dt * 12)
        return r

    def draw(self, surf, alpha=1.0):
        r = self.rect
        a = int(255 * alpha)
        T.rect(surf, (255, 255, 255, int((10 + 25 * self.hover) * alpha)), r, S(4))
        T.text(surf, self.label, (r.x + S(16), r.centery), 20, T.TEXT, anchor="midleft", alpha=a)
        sw = pygame.Rect(0, 0, S(52), S(26))
        sw.midright = (r.right - S(14), r.centery)
        col = tuple(int(60 + (c - 60) * self.anim) for c in T.ACCENT)
        T.rect(surf, (*col, a), sw, sw.h // 2)
        kx = sw.x + sw.h // 2 + int((sw.w - sw.h) * self.anim)
        pygame.draw.circle(surf, (*T.WHITE, a), (kx, sw.centery), sw.h // 2 - S(3))
        T.text(surf, "ACTIVÉ" if self.value else "DÉSACTIVÉ", (sw.x - S(12), r.centery), 16, T.MUTED,
               anchor="midright", alpha=a)


class Selector(Widget):
    def __init__(self, rect, label, options, index, callback=None):
        super().__init__(rect)
        self.label = label
        self.options = options
        self.index = index
        self.callback = callback
        self.flash = 0.0

    @property
    def arrows(self):
        r = self.rect
        w = S(34)
        left = pygame.Rect(r.x + int(r.w * 0.45), r.y + S(6), w, r.h - S(12))
        right = pygame.Rect(r.right - S(14) - w, r.y + S(6), w, r.h - S(12))
        return left, right

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.rect.collidepoint(ev.pos):
            left, right = self.arrows
            d = -1 if ev.pos[0] < (left.right + right.x) / 2 else 1
            self.index = (self.index + d) % len(self.options)
            self.flash = 1.0
            if self.callback:
                self.callback(self.index)
            return True
        return False

    def update(self, dt, mouse):
        self.flash = max(0.0, self.flash - dt * 4)
        return super().update(dt, mouse)

    def draw(self, surf, alpha=1.0):
        r = self.rect
        a = int(255 * alpha)
        T.rect(surf, (255, 255, 255, int((10 + 25 * self.hover) * alpha)), r, S(4))
        T.text(surf, self.label, (r.x + S(16), r.centery), 20, T.TEXT, anchor="midleft", alpha=a)
        left, right = self.arrows
        for ar, ch in ((left, "<"), (right, ">")):
            T.rect(surf, (255, 255, 255, int(30 * alpha)), ar, S(3))
            T.text(surf, ch, ar.center, 20, T.ACCENT, bold=True, anchor="center", alpha=a)
        mid = ((left.right + right.x) // 2, r.centery)
        col = tuple(int(c + (255 - c) * self.flash) for c in T.WHITE)
        T.text(surf, str(self.options[self.index]), mid, 20, col, bold=True, anchor="center", alpha=a)
