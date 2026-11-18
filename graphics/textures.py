"""Génération procédurale des textures PBR (albédo, normale, rugosité, métal).

Chaque générateur produit des cartes en coordonnées « mètres » afin que les
motifs (briques, fenêtres, dalles) aient des proportions réalistes. Les
résultats sont mis en cache en PNG dans assets/textures pour accélérer les
lancements suivants (et pour pouvoir être retouchés/remplacés).

Convention : la ligne 0 des tableaux correspond à v = 0 (bas de la texture).
"""
import numpy as np
import pygame

from engine.resources import TEX_DIR
from graphics.materials import MATERIALS

BASE_SIZE = 512


# ----------------------------------------------------------------------------
# Bruits tuilables
# ----------------------------------------------------------------------------
def value_noise(size, cells, rng):
    g = rng.random((cells, cells)).astype(np.float32)
    x = np.arange(size, dtype=np.float32) * cells / size
    i0 = np.floor(x).astype(np.int32)
    f = x - i0
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % cells
    i0 = i0 % cells
    a = g[i0][:, i0]
    b = g[i0][:, i1]
    c = g[i1][:, i0]
    d = g[i1][:, i1]
    fx = f[None, :]
    fy = f[:, None]
    top = a * (1 - fx) + b * fx
    bot = c * (1 - fx) + d * fx
    return top * (1 - fy) + bot * fy


def fbm(size, base, octaves, rng, persistence=0.5):
    total = np.zeros((size, size), np.float32)
    amp, norm = 1.0, 0.0
    cells = base
    for _ in range(octaves):
        cells_c = min(cells, size)
        total += value_noise(size, cells_c, rng) * amp
        norm += amp
        amp *= persistence
        cells *= 2
    return total / norm


def grain(size, rng):
    return rng.random((size, size)).astype(np.float32)


def rect(X, Y, x0, y0, x1, y1):
    return (X >= x0) & (X < x1) & (Y >= y0) & (Y < y1)


def mix(a, b, t):
    t = np.asarray(t, np.float32)
    if t.ndim == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def col(c, shape):
    return np.broadcast_to(np.array(c, np.float32), shape + (3,)).copy()


class Maps:
    """Conteneur des cartes d'un matériau."""

    def __init__(self, S):
        self.S = S
        self.rgb = np.zeros((S, S, 3), np.float32)
        self.alpha = np.ones((S, S), np.float32)
        self.height = np.full((S, S), 0.5, np.float32)
        self.rough = np.full((S, S), 0.5, np.float32)  # 0.5 = rugosité nominale
        self.metal = np.ones((S, S), np.float32)       # multiplicateur du métal nominal


def meters(S, w, h):
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    return (xx + 0.5) / S * w, (yy + 0.5) / S * h


# ----------------------------------------------------------------------------
# Générateurs
# ----------------------------------------------------------------------------
def gen_asphalt_base(S, rng, tone=0.2):
    m = Maps(S)
    n1 = fbm(S, 4, 6, rng)
    n2 = grain(S, rng)
    patches = fbm(S, 3, 3, rng)
    base = tone * (0.75 + 0.45 * n1) * (0.85 + 0.3 * n2)
    base *= np.where(patches > 0.62, 0.8, 1.0)
    m.rgb = np.stack([base * 1.0, base * 1.0, base * 1.04], -1)
    # fissures
    c = fbm(S, 6, 4, rng)
    crack = np.abs(c - 0.5) < 0.008
    m.rgb[crack] *= 0.45
    m.height = 0.5 + 0.25 * (n2 - 0.5) + 0.1 * n1
    m.height[crack] -= 0.3
    m.rough = 0.45 + 0.15 * n2
    # taches d'huile
    oil = fbm(S, 5, 3, rng) > 0.7
    m.rgb[oil] *= 0.65
    m.rough[oil] = 0.3
    return m


def gen_road(S, rng):
    m = gen_asphalt_base(S, rng)
    X, Y = meters(S, 14.0, 12.0)
    wear = fbm(S, 8, 4, rng)
    edge = ((X > 0.55) & (X < 0.75)) | ((X > 13.25) & (X < 13.45))
    dash = (np.abs(X - 7.0) < 0.1) & (Y % 12.0 < 4.0)
    mark = (edge | dash) & (wear > 0.28)
    m.rgb[mark] = mix(m.rgb[mark], np.array([0.86, 0.85, 0.8], np.float32), 0.92)
    m.height[mark] += 0.15
    m.rough[mark] = 0.4
    # traces de pneus plus sombres et lisses
    tire = (np.abs(X - 3.5) < 0.9) | (np.abs(X - 10.5) < 0.9)
    m.rgb[tire] *= 0.9
    m.rough[tire] -= 0.08
    return m


def gen_asphalt(S, rng):
    return gen_asphalt_base(S, rng)


def gen_crosswalk(S, rng):
    m = gen_asphalt_base(S, rng)
    X, Y = meters(S, 14.0, 4.0)
    wear = fbm(S, 8, 4, rng)
    stripes = ((X % 1.0) < 0.5) & (Y > 0.5) & (Y < 3.5) & (X > 0.5) & (X < 13.5) & (wear > 0.25)
    m.rgb[stripes] = np.array([0.88, 0.88, 0.85], np.float32) * (0.9 + 0.1 * wear[stripes, None])
    m.height[stripes] += 0.15
    m.rough[stripes] = 0.4
    return m


def gen_sidewalk(S, rng):
    m = Maps(S)
    X, Y = meters(S, 4.0, 4.0)
    tile_i = np.floor(X).astype(int) + 4 * np.floor(Y).astype(int)
    tint = rng.random(16).astype(np.float32)[tile_i % 16]
    n = fbm(S, 8, 5, rng)
    g = grain(S, rng)
    base = 0.5 + 0.08 * tint + 0.12 * (n - 0.5) + 0.05 * (g - 0.5)
    m.rgb = np.stack([base, base * 0.98, base * 0.95], -1)
    fx, fy = X % 1.0, Y % 1.0
    gap = (fx < 0.02) | (fx > 0.98) | (fy < 0.02) | (fy > 0.98)
    m.rgb[gap] *= 0.45
    m.height = 0.6 + 0.1 * n
    m.height[gap] = 0.2
    stain = fbm(S, 4, 4, rng) > 0.68
    m.rgb[stain] *= 0.78
    m.rough = 0.5 + 0.1 * g
    return m


def gen_concrete(S, rng):
    m = Maps(S)
    n = fbm(S, 4, 6, rng)
    g = grain(S, rng)
    base = 0.52 + 0.18 * (n - 0.5) + 0.04 * (g - 0.5)
    m.rgb = np.stack([base, base * 0.99, base * 0.96], -1)
    streak = fbm(S, 2, 3, rng)
    m.rgb *= (0.88 + 0.12 * streak)[..., None]
    m.height = 0.5 + 0.2 * n + 0.05 * g
    m.rough = 0.5 + 0.1 * g
    return m


def window_layout(m, X, Y, rng, frame_col, glass_tint=(0.07, 0.09, 0.11), wx=(0.8, 2.2), wy=(0.9, 2.8),
                  sill=True):
    """Ajoute une grille de 4x2 fenêtres sur une tuile de 12 m x 6,4 m."""
    lx, ly = X % 3.0, Y % 3.2
    outer = rect(lx, ly, wx[0], wy[0], wx[1], wy[1])
    fw = 0.07
    inner = rect(lx, ly, wx[0] + fw, wy[0] + fw, wx[1] - fw, wy[1] - fw)
    # croisillon central
    mull = inner & (np.abs(lx - (wx[0] + wx[1]) / 2) < 0.03)
    glass = inner & ~mull
    frame = outer & ~glass
    if sill:
        s = rect(lx, ly, wx[0] - 0.1, wy[0] - 0.12, wx[1] + 0.1, wy[0])
        m.rgb[s] = np.array([0.62, 0.6, 0.56], np.float32)
        m.height[s] = 0.85
        lint = rect(lx, ly, wx[0] - 0.05, wy[1], wx[1] + 0.05, wy[1] + 0.14)
        m.rgb[lint] = np.array([0.58, 0.56, 0.52], np.float32)
        m.height[lint] = 0.7
    m.rgb[frame] = np.array(frame_col, np.float32)
    m.height[frame] = 0.45
    # vitrage : sombre, léger dégradé (le reflet du ciel est calculé par le shader)
    grad = (ly - wy[0]) / (wy[1] - wy[0])
    gl = np.array(glass_tint, np.float32)
    m.rgb[glass] = gl * (0.8 + 0.5 * grad[glass, None])
    m.height[glass] = 0.2
    m.alpha[:] = 0.0
    m.alpha[glass] = 1.0
    m.rough[glass] = 0.1
    return glass


def gen_brick(S, rng):
    m = Maps(S)
    X, Y = meters(S, 12.0, 6.4)
    bh, bw = 6.4 / 40, 12.0 / 30
    row = np.floor(Y / bh).astype(int)
    off = (row % 2) * bw * 0.5
    colx = np.floor((X + off) / bw).astype(int) % 30
    table = rng.random((40, 30)).astype(np.float32)
    v = table[row % 40, colx]
    n = fbm(S, 8, 4, rng)
    base = np.stack([0.48 + 0.12 * v, 0.22 + 0.06 * v, 0.16 + 0.04 * v], -1)
    base *= (0.85 + 0.25 * n)[..., None]
    fx = ((X + off) % bw) / bw
    fy = (Y % bh) / bh
    mortar = (fx < 0.05) | (fy < 0.1)
    m.rgb = base
    m.rgb[mortar] = np.array([0.55, 0.53, 0.5], np.float32) * (0.9 + 0.2 * n[mortar, None])
    m.height = 0.6 + 0.1 * n
    m.height[mortar] = 0.35
    m.rough = 0.5 + 0.1 * grain(S, rng)
    # bandeau horizontal entre les étages
    band = (Y % 3.2) < 0.18
    m.rgb[band] = np.array([0.6, 0.58, 0.54], np.float32)
    m.height[band] = 0.75
    window_layout(m, X, Y, rng, frame_col=(0.85, 0.85, 0.82))
    # salissures verticales
    dirt = fbm(S, 3, 3, rng)
    m.rgb *= (0.85 + 0.15 * dirt)[..., None]
    return m


def gen_glass_tower(S, rng):
    m = Maps(S)
    X, Y = meters(S, 12.0, 6.4)
    lx, ly = X % 1.5, Y % 3.2
    spandrel = (ly < 0.75)
    mullion_v = (lx < 0.06)
    mullion_h = (np.abs(ly - 0.75) < 0.04) | (ly > 3.16)
    frame = mullion_v | mullion_h
    pane_id = (np.floor(X / 1.5) + 8 * np.floor(Y / 3.2)).astype(int)
    pv = rng.random(64).astype(np.float32)[pane_id % 64]
    glass = ~spandrel & ~frame
    m.rgb[:] = np.array([0.1, 0.16, 0.2], np.float32)
    m.rgb *= (0.8 + 0.4 * pv)[..., None]
    m.rgb[spandrel] = np.array([0.12, 0.14, 0.16], np.float32)
    m.rgb[frame] = np.array([0.55, 0.58, 0.6], np.float32)
    m.height[:] = 0.4
    m.height[frame] = 0.7
    m.alpha[:] = 0.0
    m.alpha[glass] = 1.0
    m.rough[:] = 0.3
    m.rough[glass] = 0.05
    m.metal[:] = 1.0
    return m


def gen_panel(S, rng):
    m = Maps(S)
    X, Y = meters(S, 12.0, 6.4)
    n = fbm(S, 6, 5, rng)
    base = np.array([0.72, 0.66, 0.56], np.float32)
    m.rgb = base * (0.85 + 0.25 * n)[..., None]
    joint = ((X % 3.0) < 0.03) | ((Y % 1.6) < 0.03)
    m.rgb[joint] *= 0.6
    m.height = 0.55 + 0.1 * n
    m.height[joint] = 0.3
    m.rough = 0.5 + 0.08 * grain(S, rng)
    window_layout(m, X, Y, rng, frame_col=(0.3, 0.3, 0.32), glass_tint=(0.06, 0.08, 0.1),
                  wx=(0.4, 2.6), wy=(0.9, 2.6))
    dirt = fbm(S, 3, 3, rng)
    m.rgb *= (0.88 + 0.12 * dirt)[..., None]
    return m


def gen_dark_panel(S, rng):
    m = Maps(S)
    X, Y = meters(S, 12.0, 6.4)
    n = fbm(S, 6, 4, rng)
    m.rgb[:] = np.array([0.16, 0.17, 0.19], np.float32)
    m.rgb *= (0.9 + 0.2 * n)[..., None]
    joint = ((X % 1.5) < 0.02) | ((Y % 3.2) < 0.03)
    m.rgb[joint] *= 0.5
    m.height = 0.5 + 0.05 * n
    m.height[joint] = 0.3
    m.rough[:] = 0.45
    ly = Y % 3.2
    lx = X % 3.0
    ribbon = (ly > 1.0) & (ly < 2.7)
    mull = (lx < 0.05) | (np.abs(lx - 1.5) < 0.025)
    glass = ribbon & ~mull
    m.rgb[ribbon & mull] = np.array([0.35, 0.36, 0.38], np.float32)
    m.rgb[glass] = np.array([0.05, 0.07, 0.08], np.float32)
    m.alpha[:] = 0.0
    m.alpha[glass] = 1.0
    m.rough[glass] = 0.05
    m.height[glass] = 0.2
    return m


def gen_storefront(S, rng):
    m = Maps(S)
    X, Y = meters(S, 12.0, 4.5)
    n = fbm(S, 6, 4, rng)
    m.rgb[:] = np.array([0.25, 0.24, 0.23], np.float32)
    m.rgb *= (0.9 + 0.2 * n)[..., None]
    lx = X % 6.0
    win = rect(lx, Y, 0.3, 0.45, 4.2, 3.2)
    door = rect(lx, Y, 4.5, 0.0, 5.7, 2.6)
    door_glass = rect(lx, Y, 4.62, 0.12, 5.58, 2.48)
    frame = (win & ~rect(lx, Y, 0.38, 0.53, 4.12, 3.12)) | (win & (np.abs(lx - 2.25) < 0.03))
    glass = win & ~frame
    m.rgb[frame] = np.array([0.12, 0.12, 0.13], np.float32)
    m.rgb[door] = np.array([0.1, 0.1, 0.11], np.float32)
    m.rgb[glass | door_glass] = np.array([0.08, 0.1, 0.11], np.float32)
    base = Y < 0.45
    m.rgb[base] = np.array([0.4, 0.39, 0.37], np.float32)
    # bandeau d'enseigne
    sign = rect(X, Y, 0.0, 3.4, 12.0, 4.2)
    sign_col = np.array([[0.55, 0.12, 0.1], [0.1, 0.25, 0.45], [0.15, 0.35, 0.2], [0.6, 0.45, 0.1]], np.float32)
    idx = np.floor(X / 6.0).astype(int) % 2 + rng.integers(0, 3)
    m.rgb[sign] = sign_col[idx[sign] % 4] * (0.8 + 0.3 * n[sign, None])
    m.height[:] = 0.5
    m.height[glass | door_glass] = 0.25
    m.height[sign] = 0.8
    m.alpha[:] = 0.0
    m.alpha[glass | door_glass] = 1.0
    m.rough[glass | door_glass] = 0.05
    return m


def gen_roof(S, rng):
    m = Maps(S)
    g = grain(S, rng)
    n = fbm(S, 6, 5, rng)
    base = 0.2 + 0.1 * n + 0.08 * g
    m.rgb = np.stack([base, base * 0.98, base * 0.96], -1)
    m.height = 0.4 + 0.3 * g + 0.2 * n
    m.rough = 0.5 + 0.1 * g
    return m


def gen_grass(S, rng):
    m = Maps(S)
    n = fbm(S, 4, 6, rng)
    g = grain(S, rng)
    dry = fbm(S, 3, 3, rng)
    green = np.array([0.16, 0.3, 0.08], np.float32)
    yellow = np.array([0.35, 0.36, 0.14], np.float32)
    m.rgb = mix(green, yellow, np.clip(dry * 1.5 - 0.5, 0, 1))
    m.rgb *= (0.65 + 0.5 * n + 0.25 * g)[..., None]
    m.height = 0.4 + 0.4 * g
    m.rough = 0.55 + 0.05 * g
    return m


def gen_bark(S, rng):
    m = Maps(S)
    X, Y = meters(S, 1.0, 1.0)
    n = fbm(S, 4, 5, rng)
    stripes = value_noise(S, 32, rng)
    stripes = np.tile(stripes[S // 2:S // 2 + 1, :], (S, 1))
    r = 0.6 * stripes + 0.4 * n
    m.rgb = np.stack([0.27 * r + 0.08, 0.2 * r + 0.06, 0.14 * r + 0.04], -1)
    m.height = r
    m.rough[:] = 0.55
    return m


def gen_leaves(S, rng):
    m = Maps(S)
    n = fbm(S, 8, 4, rng)
    cluster = fbm(S, 16, 3, rng)
    g = grain(S, rng)
    shade = 0.6 + 0.6 * n
    c1 = np.array([0.2, 0.34, 0.09], np.float32)
    c2 = np.array([0.38, 0.46, 0.13], np.float32)
    m.rgb = mix(c1, c2, cluster) * shade[..., None]
    m.alpha = (cluster + 0.25 * g > 0.42).astype(np.float32)
    m.height = 0.3 + 0.5 * cluster
    m.rough[:] = 0.5
    return m


def gen_paint(S, rng):
    m = Maps(S)
    n = fbm(S, 8, 5, rng)
    m.rgb[:] = (0.92 + 0.06 * n)[..., None]
    scratch = fbm(S, 32, 2, rng)
    sc = np.abs(scratch - 0.5) < 0.006
    m.rgb[sc] *= 0.75
    m.height = 0.5 + 0.02 * n
    m.rough = 0.45 + 0.1 * n
    m.rough[sc] = 0.8
    return m


def gen_brushed(S, rng):
    m = Maps(S)
    lines = rng.random((S, 1)).astype(np.float32)
    lines = np.repeat(lines, S, axis=1)
    n = fbm(S, 4, 4, rng)
    v = 0.62 + 0.08 * lines + 0.06 * n
    m.rgb = np.stack([v, v, v * 1.02], -1)
    m.height = 0.5 + 0.05 * lines
    m.rough = 0.4 + 0.2 * lines
    return m


def gen_drone_shell(S, rng):
    m = Maps(S)
    X, Y = meters(S, 1.0, 1.0)
    n = fbm(S, 6, 4, rng)
    m.rgb[:] = (0.85 + 0.08 * n)[..., None]
    seam = ((X % 0.25) < 0.006) | ((Y % 0.5) < 0.006)
    m.rgb[seam] *= 0.35
    m.height[:] = 0.6
    m.height[seam] = 0.2
    # rivets / évents
    cx, cy = (X % 0.25) - 0.125, (Y % 0.5) - 0.06
    vent = (cx * cx + cy * cy) < 0.0006
    m.rgb[vent] *= 0.3
    m.height[vent] = 0.3
    m.rough = 0.4 + 0.15 * n
    return m


def gen_emissive(S, rng):
    m = Maps(S)
    m.rgb[:] = 1.0
    m.alpha[:] = 1.0
    m.rough[:] = 0.3
    return m


def gen_glass(S, rng):
    m = Maps(S)
    n = fbm(S, 4, 3, rng)
    m.rgb[:] = np.array([0.03, 0.04, 0.05], np.float32) * (0.9 + 0.2 * n)[..., None]
    m.rough[:] = 0.5
    return m


def gen_rubber(S, rng):
    m = Maps(S)
    g = grain(S, rng)
    m.rgb[:] = (0.05 + 0.02 * g)[..., None]
    m.height = 0.5 + 0.1 * g
    m.rough[:] = 0.55
    return m


def gen_wood(S, rng):
    m = Maps(S)
    X, Y = meters(S, 2.0, 2.0)
    plank = np.floor(Y / 0.25).astype(int)
    pv = rng.random(8).astype(np.float32)[plank % 8]
    grainv = value_noise(S, 16, rng)
    rings = np.sin((X * 6 + grainv * 8 + pv * 10)) * 0.5 + 0.5
    base = np.array([0.42, 0.27, 0.15], np.float32)
    m.rgb = base * (0.7 + 0.25 * rings + 0.2 * pv)[..., None]
    gap = (Y % 0.25) < 0.012
    m.rgb[gap] *= 0.4
    m.height = 0.5 + 0.1 * rings
    m.height[gap] = 0.1
    m.rough[:] = 0.5
    return m


def gen_dirt(S, rng):
    m = Maps(S)
    n = fbm(S, 4, 6, rng)
    g = grain(S, rng)
    m.rgb = np.stack([0.3 + 0.12 * n, 0.23 + 0.09 * n, 0.16 + 0.06 * n], -1) * (0.85 + 0.3 * g)[..., None]
    pebble = g > 0.97
    m.rgb[pebble] = 0.45
    m.height = 0.4 + 0.3 * n + 0.2 * g
    m.rough[:] = 0.55
    return m


def gen_hazard(S, rng):
    m = gen_concrete(S, rng)
    X, Y = meters(S, 2.0, 1.0)
    band = (Y > 0.55) & (Y < 0.8)
    diag = ((X + Y) % 0.4) < 0.2
    wear = fbm(S, 8, 3, rng) > 0.3
    m.rgb[band & diag & wear] = np.array([0.85, 0.65, 0.05], np.float32)
    m.rgb[band & ~diag & wear] = np.array([0.06, 0.06, 0.06], np.float32)
    m.rough[band] = 0.4
    return m


def gen_grass_blades(S, rng):
    m = Maps(S)
    X, Y = meters(S, 1.0, 1.0)
    m.alpha[:] = 0.0
    m.rgb[:] = np.array([0.18, 0.32, 0.08], np.float32)
    for _ in range(70):
        x0 = rng.random()
        h = 0.45 + 0.55 * rng.random()
        w = 0.008 + 0.01 * rng.random()
        lean = (rng.random() - 0.5) * 0.25
        t = Y / h
        cx = x0 + lean * t * t
        width = w * (1 - t)
        blade = (np.abs(((X - cx + 0.5) % 1.0) - 0.5) < width) & (Y < h)
        m.alpha[blade] = 1.0
        shade = 0.5 + 0.7 * t
        tint = np.array([0.16 + 0.1 * rng.random(), 0.3 + 0.08 * rng.random(), 0.07], np.float32)
        m.rgb[blade] = tint * shade[blade, None]
    m.rough[:] = 0.5
    return m


def gen_container(S, rng):
    m = Maps(S)
    X, Y = meters(S, 2.4, 2.4)
    ridge = 0.5 + 0.5 * np.sin(X / 0.3 * 2 * np.pi)
    n = fbm(S, 6, 4, rng)
    m.rgb[:] = (0.85 + 0.1 * ridge)[..., None] * (0.9 + 0.1 * n)[..., None]
    rust = fbm(S, 8, 4, rng)
    rmask = rust > 0.74
    m.rgb[rmask] = np.array([0.35, 0.18, 0.08], np.float32) * (0.8 + 0.4 * n[rmask, None])
    m.height = ridge
    m.rough = 0.45 + 0.1 * n
    m.rough[rmask] = 0.9
    m.metal = np.where(rmask, 0.0, 1.0).astype(np.float32)
    return m


def gen_plaza(S, rng):
    m = Maps(S)
    X, Y = meters(S, 4.0, 4.0)
    ti = (np.floor(X) + 4 * np.floor(Y)).astype(int)
    tv = rng.random(16).astype(np.float32)[ti % 16]
    checker = ((np.floor(X) + np.floor(Y)) % 2).astype(np.float32)
    n = fbm(S, 8, 4, rng)
    base = 0.55 + 0.1 * checker + 0.06 * tv + 0.06 * (n - 0.5)
    m.rgb = np.stack([base * 1.02, base, base * 0.95], -1)
    fx, fy = X % 1.0, Y % 1.0
    gap = (fx < 0.012) | (fy < 0.012)
    m.rgb[gap] *= 0.5
    m.height[:] = 0.6
    m.height[gap] = 0.25
    m.rough = 0.35 + 0.1 * n
    return m


def gen_awning(S, rng):
    m = Maps(S)
    X, Y = meters(S, 2.0, 2.0)
    stripe = ((X % 0.5) < 0.25)
    n = fbm(S, 8, 3, rng)
    m.rgb[:] = 0.9
    m.rgb[stripe] = 0.55
    m.rgb *= (0.9 + 0.1 * n)[..., None]
    m.height = 0.5 + 0.1 * n
    m.rough[:] = 0.6
    return m


def gen_polymer(S, rng):
    m = Maps(S)
    g = grain(S, rng)
    n = fbm(S, 16, 3, rng)
    m.rgb[:] = (0.13 + 0.03 * n + 0.015 * g)[..., None]
    m.height = 0.5 + 0.2 * g
    m.rough = 0.45 + 0.1 * g
    return m


def gen_hologram(S, rng):
    m = Maps(S)
    X, Y = meters(S, 1.0, 1.0)
    lines = 0.55 + 0.45 * ((Y * 40) % 1.0 < 0.5)
    m.rgb[:] = lines[..., None]
    m.alpha = lines
    return m


GENERATORS = {
    "road": gen_road, "asphalt": gen_asphalt, "crosswalk": gen_crosswalk, "sidewalk": gen_sidewalk,
    "concrete": gen_concrete, "brick": gen_brick, "glass_tower": gen_glass_tower, "panel": gen_panel,
    "dark_panel": gen_dark_panel, "storefront": gen_storefront, "roof": gen_roof, "grass": gen_grass,
    "bark": gen_bark, "leaves": gen_leaves, "paint": gen_paint, "brushed": gen_brushed,
    "drone_shell": gen_drone_shell, "emissive": gen_emissive, "glass": gen_glass, "rubber": gen_rubber,
    "wood": gen_wood, "dirt": gen_dirt, "hazard": gen_hazard, "grass_blades": gen_grass_blades,
    "container": gen_container, "plaza": gen_plaza, "awning": gen_awning, "polymer": gen_polymer,
    "hologram": gen_hologram,
}


def normal_from_height(h, strength):
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * strength
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * strength
    n = np.stack([-dx, -dy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def to_u8(x):
    return (np.clip(x, 0.0, 1.0) * 255 + 0.5).astype(np.uint8)


def generate_layer(name, S, seed):
    rng = np.random.default_rng(seed)
    m = GENERATORS[name](S, rng)
    rgb = np.clip(m.rgb, 0, 1)
    nrm = normal_from_height(np.clip(m.height, 0, 1), strength=S / 64.0)
    albedo = np.dstack([to_u8(rgb), to_u8(m.alpha)[..., None]])
    normal = np.dstack([to_u8(nrm[..., 0] * 0.5 + 0.5)[..., None], to_u8(nrm[..., 1] * 0.5 + 0.5)[..., None],
                        to_u8(m.rough)[..., None], to_u8(m.metal)[..., None]])
    return albedo, normal


def _save_png(arr, path):
    # on retourne verticalement pour que l'image soit lisible « à l'endroit »
    surf = pygame.image.frombuffer(np.ascontiguousarray(arr[::-1]).tobytes(), (arr.shape[1], arr.shape[0]), "RGBA")
    pygame.image.save(surf, str(path))


def _load_png(path, S):
    surf = pygame.image.load(str(path))
    if surf.get_bitsize() != 32:
        raise ValueError("format inattendu")
    if surf.get_size() != (S, S):
        surf = pygame.transform.smoothscale(surf, (S, S))
    data = pygame.image.tobytes(surf, "RGBA")
    return np.frombuffer(data, np.uint8).reshape(S, S, 4)[::-1]


def downsample(arr, S):
    f = arr.shape[0] // S
    if f <= 1:
        return arr
    a = arr.astype(np.float32).reshape(S, f, S, f, 4).mean(axis=(1, 3))
    return (a + 0.5).astype(np.uint8)


def load_all(size=BASE_SIZE, progress=None):
    """Renvoie deux tableaux (couches, S, S, 4) uint8 : albédo et normal/rugosité/métal."""
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    albedos, normals = [], []
    n = len(MATERIALS)
    for i, mat in enumerate(MATERIALS):
        name = mat[0]
        pa = TEX_DIR / f"{name}_albedo.png"
        pn = TEX_DIR / f"{name}_normal.png"
        a = nm = None
        if pa.exists() and pn.exists():
            try:
                a = _load_png(pa, BASE_SIZE)
                nm = _load_png(pn, BASE_SIZE)
            except Exception:
                a = nm = None
        if a is None:
            a, nm = generate_layer(name, BASE_SIZE, seed=1000 + i * 37)
            try:
                _save_png(a, pa)
                _save_png(nm, pn)
            except Exception:
                pass
        albedos.append(downsample(a, size))
        normals.append(downsample(nm, size))
        if progress:
            progress((i + 1) / n, f"Textures : {name}")
    return np.stack(albedos), np.stack(normals)
