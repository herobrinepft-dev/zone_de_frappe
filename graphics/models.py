"""Modèles 3D du jeu.

Chaque modèle est construit par code (modélisation procédurale) puis exporté au
format OBJ dans assets/models. Au lancement, le jeu charge en priorité les
fichiers OBJ présents : on peut donc remplacer n'importe quel modèle par un
OBJ réalisé dans Blender (mêmes noms de matériaux via `usemtl`).
"""
import math
import numpy as np

from engine import mathutils as mu
from engine.resources import MODEL_DIR
from graphics.meshbuilder import MeshBuilder, transform_array
from graphics.materials import L
from graphics.obj_io import save_obj, load_obj

PAINT = L["paint"]


# ----------------------------------------------------------------------------
# Végétation
# ----------------------------------------------------------------------------
def build_tree(seed):
    rng = np.random.default_rng(seed)
    b = MeshBuilder()
    h = 3.2 + rng.random() * 1.5
    b.cylinder((0, 0, 0), 0.2, h, L["bark"], seg=10, radius_top=0.11, tile_u=1.0, tile_v=1.5)
    crown_y = h
    for i in range(3):
        a = rng.random() * 2 * math.pi
        tilt = 0.6 + rng.random() * 0.4
        length = 1.3 + rng.random() * 0.6
        sub = MeshBuilder()
        sub.cylinder((0, 0, 0), 0.08, length, L["bark"], seg=6, radius_top=0.03, caps=False)
        m = mu.translate(0, h * (0.65 + 0.1 * i), 0) @ mu.rot_y(a) @ mu.rot_z(tilt)
        b.add(sub.build(), m)
    n = 6 + rng.integers(0, 3)
    for i in range(n):
        a = i / n * 2 * math.pi + rng.random() * 0.5
        rr = 0.7 + rng.random() * 0.7
        cx, cz = math.cos(a) * rr, math.sin(a) * rr
        cy = crown_y + 0.2 + rng.random() * 1.4
        r = 1.1 + rng.random() * 0.6
        shade = 0.85 + rng.random() * 0.3
        b.sphere((cx, cy, cz), r, L["leaves"], seg_u=10, seg_v=7, noise=0.18, rng=rng,
                 scale=(1, 0.8, 1), color=(shade, shade, shade * 0.9), uv_scale=2.0)
    b.sphere((0, crown_y + 1.4, 0), 1.5, L["leaves"], seg_u=12, seg_v=8, noise=0.15, rng=rng,
             scale=(1, 0.85, 1), uv_scale=2.0)
    return b.build()


def build_grass_tuft(seed):
    rng = np.random.default_rng(seed)
    b = MeshBuilder()
    for i in range(3):
        a = i * math.pi / 3 + rng.random() * 0.3
        w = 0.35 + rng.random() * 0.15
        hgt = 0.35 + rng.random() * 0.25
        dx, dz = math.cos(a) * w, math.sin(a) * w
        shade = 0.85 + rng.random() * 0.3
        b.quad((-dx, 0, -dz), (dx, 0, dz), (dx, hgt, dz), (-dx, hgt, -dz),
               [(0, 0), (1, 0), (1, 1), (0, 1)], L["grass_blades"], (shade, shade, shade), normal=(0, 1, 0))
    return b.build()


def build_hedge(length):
    b = MeshBuilder()
    rng = np.random.default_rng(int(length * 10))
    n = max(2, int(length / 1.2))
    for i in range(n):
        x = -length / 2 + (i + 0.5) * length / n
        b.sphere((x, 0.55, 0), 0.75, L["leaves"], seg_u=8, seg_v=6, noise=0.2, rng=rng,
                 scale=(1.0, 0.8, 0.8), uv_scale=1.5)
    return b.build()


# ----------------------------------------------------------------------------
# Mobilier urbain
# ----------------------------------------------------------------------------
def build_lamppost():
    b = MeshBuilder()
    dark = (0.16, 0.17, 0.18)
    b.cylinder((0, 0, 0), 0.16, 0.7, PAINT, seg=12, color=dark, radius_top=0.11)
    b.cylinder((0, 0.7, 0), 0.08, 6.3, PAINT, seg=10, color=dark, radius_top=0.06)
    b.box((0, 6.7, -0.05), (1.6, 6.82, 0.05), PAINT, color=dark)
    b.box((1.2, 6.55, -0.22), (2.0, 6.85, 0.22), PAINT, color=dark)
    # diffuseur lumineux (émissif chaud)
    b.box((1.25, 6.52, -0.18), (1.95, 6.56, 0.18), L["emissive"], color=(1.0, 0.78, 0.5))
    return b.build()


def build_traffic_light():
    b = MeshBuilder()
    dark = (0.13, 0.14, 0.15)
    b.cylinder((0, 0, 0), 0.1, 4.6, PAINT, seg=10, color=dark)
    b.box((0, 4.4, -0.05), (3.2, 4.5, 0.05), PAINT, color=dark)
    b.box((2.85, 3.5, -0.18), (3.25, 4.45, 0.18), PAINT, color=(0.1, 0.1, 0.1))
    lights = [(4.25, (1.0, 0.12, 0.05)), (3.95, (0.25, 0.17, 0.02)), (3.65, (0.03, 0.18, 0.06))]
    for y, c in lights:
        b.cylinder((3.05, y, -0.19), 0.11, 0.02, L["emissive"], seg=12, color=c, axis="z")
    # second feu piéton sur le mât
    b.box((-0.15, 2.4, -0.15), (0.15, 3.0, 0.15), PAINT, color=(0.1, 0.1, 0.1))
    b.box((-0.1, 2.75, -0.16), (0.1, 2.92, -0.15), L["emissive"], color=(0.9, 0.15, 0.05))
    return b.build()


def build_bench():
    b = MeshBuilder()
    metal = (0.2, 0.21, 0.22)
    for x in (-0.8, 0.8):
        b.box((x - 0.04, 0, -0.25), (x + 0.04, 0.45, 0.25), PAINT, color=metal)
        b.box((x - 0.04, 0.45, 0.18), (x + 0.04, 0.95, 0.24), PAINT, color=metal)
    for i in range(4):
        z = -0.22 + i * 0.12
        b.box((-1.0, 0.45, z), (1.0, 0.49, z + 0.1), L["wood"], tile_u=2, tile_v=2, top_tile=2)
    for i in range(2):
        y = 0.62 + i * 0.16
        b.box((-1.0, y, 0.2), (1.0, y + 0.12, 0.24), L["wood"], tile_u=2, tile_v=2, top_tile=2)
    return b.build()


def build_bin():
    b = MeshBuilder()
    b.cylinder((0, 0, 0), 0.3, 0.95, PAINT, seg=14, color=(0.12, 0.25, 0.16))
    b.cylinder((0, 0.95, 0), 0.32, 0.06, PAINT, seg=14, color=(0.1, 0.1, 0.1))
    return b.build()


def build_hydrant():
    b = MeshBuilder()
    red = (0.7, 0.08, 0.05)
    b.cylinder((0, 0, 0), 0.16, 0.7, PAINT, seg=12, color=red)
    b.sphere((0, 0.7, 0), 0.16, PAINT, seg_u=12, seg_v=6, color=red)
    b.cylinder((0, 0.45, 0), 0.06, 0.4, L["brushed"], seg=8, axis="x")
    b.box((-0.25, 0.4, -0.06), (0.25, 0.5, 0.06), PAINT, color=red)
    return b.build()


def build_bollard():
    b = MeshBuilder()
    b.cylinder((0, 0, 0), 0.1, 0.9, PAINT, seg=10, color=(0.15, 0.15, 0.16))
    b.cylinder((0, 0.75, 0), 0.105, 0.06, L["emissive"], seg=10, color=(0.6, 0.4, 0.2), caps=False)
    return b.build()


def build_car(seed=0):
    rng = np.random.default_rng(seed)
    b = MeshBuilder()
    w, l = 0.92, 2.25
    # carrosserie basse avec capot légèrement incliné
    b.box((-w, 0.3, -l), (w, 0.82, l), PAINT)
    b.quad((-w, 0.82, -l), (w, 0.82, -l), (w, 0.92, -1.0), (-w, 0.92, -1.0), [(0, 0), (1, 0), (1, 1), (0, 1)], PAINT)
    b.quad((-w, 0.82, l), (-w, 0.92, 1.3), (w, 0.92, 1.3), (w, 0.82, l), [(0, 0), (1, 0), (1, 1), (0, 1)], PAINT)
    for sx in (-w, w):
        b.quad((sx, 0.82, -l), (sx, 0.92, -1.0), (sx, 0.92, 1.3), (sx, 0.82, l), [(0, 0), (0, 1), (1, 1), (1, 0)], PAINT)
    # habitacle (vitres)
    cw, tw = 0.86, 0.72
    yb, yt = 0.92, 1.42
    zf0, zf1, zr0, zr1 = -1.0, -0.35, 1.3, 0.75
    g = L["glass"]
    b.quad((-cw, yb, zf0), (cw, yb, zf0), (tw, yt, zf1), (-tw, yt, zf1), [(0, 0), (1, 0), (1, 1), (0, 1)], g)
    b.quad((cw, yb, zr0), (-cw, yb, zr0), (-tw, yt, zr1), (tw, yt, zr1), [(0, 0), (1, 0), (1, 1), (0, 1)], g)
    b.quad((-cw, yb, zr0), (-cw, yb, zf0), (-tw, yt, zf1), (-tw, yt, zr1), [(0, 0), (1, 0), (1, 1), (0, 1)], g)
    b.quad((cw, yb, zf0), (cw, yb, zr0), (tw, yt, zr1), (tw, yt, zf1), [(0, 0), (1, 0), (1, 1), (0, 1)], g)
    b.quad((-tw, yt, zf1), (tw, yt, zf1), (tw, yt, zr1), (-tw, yt, zr1), [(0, 0), (1, 0), (1, 1), (0, 1)], PAINT)
    # montants de portes
    for sx in (-1, 1):
        b.box((sx * cw - 0.03, yb, 0.1), (sx * cw + 0.03, yt - 0.05, 0.18), PAINT)
    # pare-chocs, roues
    b.box((-w - 0.02, 0.28, -l - 0.08), (w + 0.02, 0.5, -l + 0.1), L["polymer"])
    b.box((-w - 0.02, 0.28, l - 0.1), (w + 0.02, 0.5, l + 0.08), L["polymer"])
    for sx in (-1, 1):
        for sz in (-1.45, 1.45):
            b.cylinder((sx * 0.8, 0.34, sz), 0.34, 0.24 * sx, L["rubber"], seg=14, axis="x")
            b.cylinder((sx * 1.045, 0.34, sz), 0.2, 0.01 * sx, L["brushed"], seg=10, axis="x")
    # phares et feux arrière (faiblement émissifs, garés)
    for sx in (-0.62, 0.62):
        b.box((sx - 0.2, 0.62, -l - 0.01), (sx + 0.2, 0.74, -l + 0.02), L["emissive"], color=(0.25, 0.24, 0.2))
        b.box((sx - 0.2, 0.64, l - 0.02), (sx + 0.2, 0.74, l + 0.01), L["emissive"], color=(0.35, 0.02, 0.01))
    # rétroviseurs
    for sx in (-1, 1):
        b.box((sx * 0.95 - 0.06, 0.95, -0.95), (sx * 0.95 + 0.06, 1.05, -0.8), PAINT)
    return b.build()


CAR_COLORS = [(0.55, 0.05, 0.04), (0.08, 0.15, 0.35), (0.85, 0.85, 0.85), (0.05, 0.05, 0.06),
              (0.35, 0.36, 0.38), (0.15, 0.3, 0.2), (0.6, 0.5, 0.25), (0.75, 0.75, 0.78)]


def build_container():
    b = MeshBuilder()
    b.box((-1.22, 0, -3.0), (1.22, 2.6, 3.0), L["container"], tile_u=2.4, tile_v=2.4, top_tile=2.4)
    for z in (-3.02, 3.0):
        b.box((-1.24, 0, z), (1.24, 2.62, z + 0.02), L["paint"], color=(0.4, 0.4, 0.4))
    return b.build()


def build_barrier():
    b = MeshBuilder()
    h = L["hazard"]
    b.box((-1.5, 0, -0.32), (1.5, 0.3, 0.32), h, tile_u=2, tile_v=1, top_tile=2)
    pts = [(-0.32, 0.3), (-0.12, 0.6), (-0.1, 0.95), (0.1, 0.95), (0.12, 0.6), (0.32, 0.3)]
    for i in range(len(pts) - 1):
        (z0, y0), (z1, y1) = pts[i], pts[i + 1]
        b.quad((-1.5, y0, z0), (1.5, y0, z0), (1.5, y1, z1), (-1.5, y1, z1),
               [(0, y0), (1.5, y0), (1.5, y1), (0, y1)], h)
    for x in (-1.5, 1.5):
        b.box((x - 0.001, 0, -0.32), (x + 0.001, 0.3, 0.32), h)
        b.quad((x, 0.3, -0.32), (x, 0.3, 0.32), (x, 0.95, 0.1), (x, 0.95, -0.1), [(0, 0), (1, 0), (1, 1), (0, 1)], h)
    return b.build()


def build_ac_unit():
    b = MeshBuilder()
    b.box((-0.8, 0, -0.6), (0.8, 1.0, 0.6), L["brushed"], tile_u=1, tile_v=1)
    b.cylinder((0, 1.0, 0), 0.45, 0.04, L["polymer"], seg=16)
    b.box((-0.05, 1.04, -0.42), (0.05, 1.06, 0.42), L["brushed"])
    return b.build()


def build_water_tank():
    b = MeshBuilder()
    for (x, z) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        b.box((x * 0.9 - 0.08, 0, z * 0.9 - 0.08), (x * 0.9 + 0.08, 2.2, z * 0.9 + 0.08), PAINT, color=(0.2, 0.2, 0.2))
    b.cylinder((0, 2.2, 0), 1.3, 3.0, L["wood"], seg=18, tile_u=2, tile_v=2)
    b.cylinder((0, 5.2, 0), 1.4, 1.0, PAINT, seg=18, radius_top=0.05, color=(0.25, 0.22, 0.2))
    return b.build()


def build_monument():
    b = MeshBuilder()
    c = L["concrete"]
    b.box((-4, 0, -4), (4, 0.5, 4), L["plaza"], tile_u=4, tile_v=4, top_tile=4)
    b.box((-3, 0.5, -3), (3, 1.0, 3), c, tile_u=4, tile_v=4, top_tile=4)
    b.box((-1.2, 1.0, -1.2), (1.2, 2.5, 1.2), c, tile_u=4, tile_v=4)
    b.cylinder((0, 2.5, 0), 0.8, 9.0, c, seg=4, radius_top=0.2, tile_u=4, tile_v=4)
    b.cylinder((0, 1.02, 0), 2.6, 0.05, L["emissive"], seg=32, color=(1.0, 0.55, 0.15), caps=False)
    return b.build()


def build_fountain():
    b = MeshBuilder()
    b.cylinder((0, 0, 0), 5.0, 0.7, L["concrete"], seg=32, tile_u=4, tile_v=4)
    b.cylinder((0, 0.55, 0), 4.6, 0.02, L["glass"], seg=32)
    b.cylinder((0, 0.6, 0), 0.8, 1.6, L["concrete"], seg=16, tile_u=4, tile_v=4)
    b.cylinder((0, 2.2, 0), 1.8, 0.3, L["concrete"], seg=24, tile_u=4, tile_v=4)
    return b.build()


# ----------------------------------------------------------------------------
# Drones d'entraînement (fictifs)
# ----------------------------------------------------------------------------
def build_drone(kind):
    b = MeshBuilder()
    shell = L["drone_shell"]
    if kind == "eclaireur":
        bs, arm = (0.42, 0.18, 0.5), 0.72
    elif kind == "sentinelle":
        bs, arm = (0.55, 0.26, 0.55), 0.85
    else:  # blinde
        bs, arm = (0.75, 0.38, 0.85), 1.05
    b.sphere((0, 0, 0), 1.0, shell, seg_u=20, seg_v=12, scale=bs, uv_scale=1.0)
    b.sphere((0, bs[1] * 0.55, 0.05), 1.0, L["glass"], seg_u=14, seg_v=8, scale=(bs[0] * 0.45, bs[1] * 0.7, bs[2] * 0.45))
    # oeil capteur (émissif, couleur par instance)
    b.sphere((0, -0.02, -bs[2] * 0.95), 0.09 * (bs[0] / 0.42), L["emissive"], seg_u=10, seg_v=6, scale=(1, 0.8, 0.6))
    b.cylinder((0, -0.02, -bs[2] * 0.9), 0.14 * (bs[0] / 0.42), 0.05, L["polymer"], seg=12, axis="z", caps=False)
    # bande lumineuse inférieure
    b.cylinder((0, -bs[1] * 0.55, 0), bs[0] * 0.72, 0.03, L["emissive"], seg=24, caps=False)
    rotors = []
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        dx, dz = math.cos(a), math.sin(a)
        sub = MeshBuilder()
        sub.box((0.0, -0.04, -0.05), (arm, 0.04, 0.05), L["polymer"])
        b.add(sub.build(), mu.rot_y(-a))
        px, pz = dx * arm, dz * arm
        # carénage du rotor (anneau)
        rr = 0.3 * (arm / 0.72)
        b.cylinder((px, -0.06, pz), rr, 0.1, shell, seg=18, caps=False)
        b.cylinder((px, -0.06, pz), rr * 0.93, 0.1, L["polymer"], seg=18, caps=False)
        b.cylinder((px, -0.1, pz), 0.07, 0.12, L["brushed"], seg=10)
        b.cylinder((px, -0.065, pz), rr, 0.012, L["emissive"], seg=18, caps=False)
        rotors.append((px, 0.03, pz, rr))
    if kind == "sentinelle":
        for sx in (-1, 1):
            b.cylinder((sx * bs[0] * 0.9, -0.12, -0.1), 0.07, 0.6, L["brushed"], seg=10, axis="z")
            b.cylinder((sx * bs[0] * 0.9, -0.12, -0.72), 0.05, 0.02, L["emissive"], seg=8, axis="z")
    if kind == "blinde":
        for sx in (-1, 1):
            sub = MeshBuilder()
            sub.box((-0.12, -0.25, -0.6), (0.12, 0.2, 0.6), L["container"], tile_u=1, tile_v=1)
            b.add(sub.build(), mu.translate(sx * bs[0] * 0.95, 0, 0) @ mu.rot_z(sx * 0.25), color=(0.35, 0.33, 0.3))
        b.box((-0.35, -bs[1] * 1.05, -0.35), (0.35, -bs[1] * 0.75, 0.35), L["polymer"])
        b.cylinder((0, -bs[1] * 1.0, -0.2), 0.12, 0.9, L["brushed"], seg=12, axis="z")
    # patins
    for sx in (-1, 1):
        b.box((sx * bs[0] * 0.55 - 0.02, -bs[1] - 0.18, -0.3), (sx * bs[0] * 0.55 + 0.02, -bs[1] - 0.14, 0.3), L["polymer"])
        b.box((sx * bs[0] * 0.55 - 0.02, -bs[1] - 0.16, -0.02), (sx * bs[0] * 0.55 + 0.02, -bs[1] * 0.6, 0.02), L["polymer"])
    return b.build(), rotors


def build_rotor():
    b = MeshBuilder()
    b.cylinder((0, -0.01, 0), 0.05, 0.04, L["brushed"], seg=8)
    for a in (0, math.pi):
        sub = MeshBuilder()
        sub.box((0.03, -0.006, -0.035), (1.0, 0.006, 0.035), L["polymer"])
        b.add(sub.build(), mu.rot_y(a) @ mu.rot_x(0.2))
    return b.build()


# ----------------------------------------------------------------------------
# Émetteurs d'impulsion (équipement fictif d'entraînement)
# Repère : x droite, y haut, -z vers l'avant. Origine = poignée.
# ----------------------------------------------------------------------------
def _holo_sight(b, y0, z0, z1):
    """Viseur holographique ouvert : socle, cadre et point de visée lumineux (on voit à travers)."""
    poly, emis = L["polymer"], L["emissive"]
    w, h, t = 0.024, 0.05, 0.004
    b.box((-w, y0, z0), (w, y0 + 0.008, z1), poly)                       # socle
    zf0, zf1 = z0, z0 + 0.012                                              # cadre avant
    b.box((-w, y0 + 0.008, zf0), (-w + t, y0 + h, zf1), poly)
    b.box((w - t, y0 + 0.008, zf0), (w, y0 + h, zf1), poly)
    b.box((-w, y0 + h - t, zf0), (w, y0 + h, zf1), poly)
    b.box((-w, y0 + 0.008, z1 - 0.01), (-w + t, y0 + h * 0.7, z1), poly)   # montants arrière
    b.box((w - t, y0 + 0.008, z1 - 0.01), (w, y0 + h * 0.7, z1), poly)
    cy = y0 + 0.008 + (h - 0.008) * 0.5
    b.box((-0.0018, cy - 0.0018, zf0 + 0.004), (0.0018, cy + 0.0018, zf0 + 0.0045), emis)


def _weapon_details(b, body_front, body_back, top, half_w):
    """Détails communs : pontet, détente, cellule d'énergie, bandes lumineuses, vis, rail."""
    poly, brushed, emis = L["polymer"], L["brushed"], L["emissive"]
    # pontet et détente
    b.box((-0.008, -0.075, -0.07), (0.008, -0.065, 0.02), brushed)
    b.box((-0.008, -0.075, -0.075), (0.008, 0.0, -0.065), brushed)
    b.box((-0.005, -0.05, -0.035), (0.005, 0.0, -0.025), poly)
    # cellule d'énergie latérale (lumineuse, couleur du faisceau)
    b.box((half_w, 0.03, body_front + 0.1), (half_w + 0.012, 0.08, body_front + 0.2), poly)
    b.box((half_w + 0.012, 0.045, body_front + 0.11), (half_w + 0.014, 0.065, body_front + 0.19), emis)
    # bandes lumineuses le long du corps
    for sx in (-1, 1):
        x = sx * (half_w + 0.001)
        b.box((min(x, x + sx * 0.002), top - 0.025, body_front + 0.02),
              (max(x, x + sx * 0.002), top - 0.018, body_back - 0.04), emis, color=(0.8, 0.8, 0.8))
    # vis / rivets
    for z in (body_front + 0.04, body_back - 0.03):
        for sx in (-1, 1):
            b.cylinder((sx * half_w, 0.02, z), 0.006, sx * 0.004, brushed, seg=6, axis="x")
    # rail supérieur cranté
    n = int((body_back - body_front - 0.1) / 0.02)
    for i in range(n):
        z = body_front + 0.05 + i * 0.02
        b.box((-0.018, top, z), (0.018, top + 0.008, z + 0.01), brushed)


def build_weapon(kind):
    b = MeshBuilder()
    poly, brushed, emis = L["polymer"], L["brushed"], L["emissive"]
    if kind == "pulsar":
        b.box((-0.035, 0.0, -0.32), (0.035, 0.11, 0.12), PAINT)                    # corps
        b.box((-0.03, 0.11, -0.28), (0.03, 0.125, 0.08), brushed)                 # rail
        b.box((-0.028, -0.16, 0.0), (0.028, 0.0, 0.07), poly)                      # poignée
        b.box((-0.025, -0.12, -0.2), (0.025, 0.0, -0.1), poly)                     # module énergie
        b.cylinder((0, 0.055, -0.32), 0.03, -0.26, poly, seg=12, axis="z")         # canon
        for i in range(4):
            b.cylinder((0, 0.055, -0.36 - i * 0.05), 0.037, -0.012, emis, seg=14, axis="z", caps=False)
        b.cylinder((0, 0.055, -0.58), 0.02, -0.03, brushed, seg=10, axis="z")
        b.box((-0.03, 0.02, 0.12), (0.03, 0.09, 0.32), PAINT)                      # crosse
        b.box((-0.032, -0.04, 0.26), (0.032, 0.09, 0.34), poly)
        _holo_sight(b, y0=0.125, z0=-0.08, z1=0.0)
        for i in range(5):                                                          # ailettes
            z = -0.25 + i * 0.03
            b.box((0.035, 0.02, z), (0.045, 0.09, z + 0.012), brushed)
            b.box((-0.045, 0.02, z), (-0.035, 0.09, z + 0.012), brushed)
        _weapon_details(b, body_front=-0.32, body_back=0.12, top=0.11, half_w=0.035)
        b.box((-0.03, 0.02, -0.46), (0.03, 0.09, -0.32), poly)                     # garde-main
        for i in range(3):
            z = -0.44 + i * 0.045
            b.box((-0.031, 0.04, z), (0.031, 0.07, z + 0.02), L["paint"])
        muzzle = (0.0, 0.055, -0.62)
    elif kind == "faucon":
        b.box((-0.032, 0.0, -0.4), (0.032, 0.1, 0.1), PAINT)
        b.box((-0.026, -0.17, -0.02), (0.026, 0.0, 0.05), poly)
        b.cylinder((0, 0.05, -0.4), 0.022, -0.5, brushed, seg=12, axis="z")
        b.cylinder((0, 0.05, -0.45), 0.034, -0.2, PAINT, seg=12, axis="z")
        for i in range(6):
            b.cylinder((0, 0.05, -0.68 - i * 0.03), 0.028, -0.008, emis, seg=12, axis="z", caps=False)
        b.cylinder((0, 0.05, -0.9), 0.032, -0.05, poly, seg=12, axis="z")
        b.cylinder((0, 0.16, -0.25), 0.032, 0.3, poly, seg=14, axis="z")      # lunette
        b.cylinder((0, 0.16, -0.255), 0.026, -0.006, L["glass"], seg=14, axis="z")
        b.box((-0.012, 0.1, -0.2), (0.012, 0.13, -0.15), poly)
        b.box((-0.012, 0.1, -0.02), (0.012, 0.13, 0.02), poly)
        b.box((-0.028, -0.02, 0.1), (0.028, 0.09, 0.4), PAINT)
        b.box((-0.03, -0.08, 0.32), (0.03, 0.09, 0.42), poly)
        b.box((-0.02, -0.1, -0.3), (0.02, 0.0, -0.18), emis, color=(0.6, 0.6, 0.6))
        _weapon_details(b, body_front=-0.4, body_back=0.1, top=0.1, half_w=0.032)
        muzzle = (0.0, 0.05, -0.96)
    else:  # tempete
        b.box((-0.05, -0.01, -0.3), (0.05, 0.12, 0.1), PAINT)
        b.box((-0.03, -0.17, -0.01), (0.03, 0.0, 0.06), poly)
        b.box((-0.03, -0.1, -0.26), (0.03, -0.01, -0.12), poly)                 # poignée avant
        for (x, y) in ((-0.025, 0.035), (0.025, 0.035), (0.0, 0.08)):
            b.cylinder((x, y, -0.3), 0.022, -0.24, brushed, seg=10, axis="z")
            b.cylinder((x, y, -0.535), 0.026, -0.015, emis, seg=10, axis="z")
        b.cylinder((0, 0.055, -0.3), 0.07, -0.12, PAINT, seg=16, axis="z", caps=False)
        b.cylinder((0, 0.055, -0.42), 0.072, -0.012, emis, seg=16, axis="z", caps=False)
        b.box((-0.045, 0.01, 0.1), (0.045, 0.1, 0.28), PAINT)
        b.box((-0.048, -0.05, 0.24), (0.048, 0.1, 0.3), poly)
        _holo_sight(b, y0=0.12, z0=-0.15, z1=-0.07)
        _weapon_details(b, body_front=-0.3, body_back=0.1, top=0.12, half_w=0.05)
        muzzle = (0.0, 0.055, -0.56)
    arr = b.build()
    arr[:, 6:8] *= 4.0   # détail de texture adapté à un objet tenu en main
    return arr, muzzle


# ----------------------------------------------------------------------------
# Objets de mission
# ----------------------------------------------------------------------------
def build_repair_kit():
    b = MeshBuilder()
    b.box((-0.3, -0.2, -0.22), (0.3, 0.2, 0.22), PAINT, color=(0.9, 0.9, 0.88))
    b.box((-0.06, -0.15, -0.23), (0.06, 0.15, -0.22), L["emissive"], color=(0.2, 1.0, 0.35))
    b.box((-0.18, -0.04, -0.23), (0.18, 0.04, -0.22), L["emissive"], color=(0.2, 1.0, 0.35))
    b.box((-0.06, -0.15, 0.22), (0.06, 0.15, 0.23), L["emissive"], color=(0.2, 1.0, 0.35))
    b.box((-0.18, -0.04, 0.22), (0.18, 0.04, 0.23), L["emissive"], color=(0.2, 1.0, 0.35))
    b.box((-0.1, 0.2, -0.03), (0.1, 0.26, 0.03), L["polymer"])
    return b.build()


def build_overcharge():
    b = MeshBuilder()
    b.sphere((0, 0, 0), 0.28, L["emissive"], seg_u=4, seg_v=2, color=(1.0, 0.5, 0.1), scale=(1, 1.4, 1))
    b.cylinder((0, -0.02, 0), 0.4, 0.04, L["brushed"], seg=20, caps=False)
    return b.build()


def build_data_core():
    b = MeshBuilder()
    b.cylinder((0, -0.4, 0), 0.18, 0.8, L["brushed"], seg=12)
    for i in range(3):
        b.cylinder((0, -0.3 + i * 0.25, 0), 0.2, 0.05, L["emissive"], seg=12, color=(0.2, 0.8, 1.0), caps=False)
    b.cylinder((0, 0.4, 0), 0.22, 0.08, L["polymer"], seg=12)
    b.cylinder((0, -0.48, 0), 0.22, 0.08, L["polymer"], seg=12)
    return b.build()


def build_beacon():
    b = MeshBuilder()
    b.cylinder((0, 0, 0), 1.2, 0.3, L["brushed"], seg=24)
    b.cylinder((0, 0.3, 0), 0.25, 3.0, L["polymer"], seg=12, radius_top=0.15)
    b.cylinder((0, 3.3, 0), 0.35, 0.5, L["emissive"], seg=12, color=(1.0, 0.6, 0.15))
    for i in range(3):
        a = i * 2 * math.pi / 3
        sub = MeshBuilder()
        sub.box((0, 0, -0.05), (1.1, 0.12, 0.05), L["brushed"])
        b.add(sub.build(), mu.translate(0, 0.25, 0) @ mu.rot_y(a))
    return b.build()


def build_ring():
    """Anneau holographique au sol (zone de capture), rayon 1."""
    b = MeshBuilder()
    b.cylinder((0, 0, 0), 1.0, 0.25, L["hologram"], seg=48, caps=False)
    return b.build()


def build_pedestal():
    b = MeshBuilder()
    b.cylinder((0, -3.0, 0), 14.0, 0.02, L["plaza"], seg=48, tile_u=4, tile_v=4)
    b.cylinder((0, -3.0, 0), 1.6, 1.5, L["dark_panel"], seg=40, radius_top=1.4, tile_u=12, tile_v=6.4,
               cap_layer=L["polymer"])
    b.cylinder((0, -1.5, 0), 1.45, 0.08, L["brushed"], seg=40)
    b.cylinder((0, -1.43, 0), 1.46, 0.02, L["emissive"], seg=40, caps=False, color=(1.0, 0.6, 0.15))
    for i in range(8):
        a = i * math.pi / 4
        sub = MeshBuilder()
        sub.box((-0.1, 0, 3.6), (0.1, 6.0, 3.8), L["dark_panel"], tile_u=12, tile_v=6.4)
        sub.box((-0.02, 0.2, 3.58), (0.02, 5.8, 3.6), L["emissive"], color=(0.9, 0.5, 0.15))
        b.add(sub.build(), mu.translate(0, -3.0, 0) @ mu.rot_y(a))
    return b.build()


# ----------------------------------------------------------------------------
# Bibliothèque : chargement OBJ prioritaire + export
# ----------------------------------------------------------------------------
_BUILDERS = {
    "tree_0": lambda: build_tree(11), "tree_1": lambda: build_tree(23), "tree_2": lambda: build_tree(37),
    "tree_3": lambda: build_tree(51),
    "grass_0": lambda: build_grass_tuft(1), "grass_1": lambda: build_grass_tuft(2),
    "hedge": lambda: build_hedge(6.0),
    "lamppost": build_lamppost, "traffic_light": build_traffic_light, "bench": build_bench,
    "bin": build_bin, "hydrant": build_hydrant, "bollard": build_bollard, "car": build_car,
    "container": build_container, "barrier": build_barrier, "ac_unit": build_ac_unit,
    "water_tank": build_water_tank, "monument": build_monument, "fountain": build_fountain,
    "drone_eclaireur": lambda: build_drone("eclaireur")[0],
    "drone_sentinelle": lambda: build_drone("sentinelle")[0],
    "drone_blinde": lambda: build_drone("blinde")[0],
    "rotor": build_rotor,
    "weapon_pulsar": lambda: build_weapon("pulsar")[0],
    "weapon_faucon": lambda: build_weapon("faucon")[0],
    "weapon_tempete": lambda: build_weapon("tempete")[0],
    "repair_kit": build_repair_kit, "overcharge": build_overcharge, "data_core": build_data_core,
    "beacon": build_beacon, "ring": build_ring, "pedestal": build_pedestal,
}

_cache = {}


def get(name):
    if name in _cache:
        return _cache[name]
    path = MODEL_DIR / f"{name}.obj"
    arr = None
    if path.exists():
        try:
            arr = load_obj(path)
        except Exception:
            arr = None
    if arr is None or len(arr) == 0:
        arr = _BUILDERS[name]()
        try:
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            save_obj(arr, path, name)
        except OSError:
            pass
    _cache[name] = arr
    return arr


def drone_rotors(kind):
    return build_drone(kind)[1]


def weapon_muzzle(kind):
    return build_weapon(kind)[1]


def all_names():
    return list(_BUILDERS.keys())
