"""Génération de la ville d'entraînement (géométrie, collisions, points d'intérêt).

Grille de 7 x 7 îlots séparés par des avenues de 14 m. Chaque îlot reçoit des
trottoirs, du mobilier urbain, puis un contenu : immeubles (1, 2 ou 4
bâtiments), parc, place centrale ou chantier de conteneurs.
"""
import math
import numpy as np

from engine import mathutils as mu
from graphics.meshbuilder import MeshBuilder
from graphics.materials import L
from graphics import models

N = 7
CELL = 58.0
ROAD = 14.0
HALF = N * CELL / 2.0          # 203
SIDEWALK = 3.0
CURB = 0.15
WALL = HALF + ROAD / 2 + 1.0   # 211
CHUNKS = 8
CHUNK_SIZE = 2 * (WALL + 4) / CHUNKS


def road_c(k):
    return -HALF + k * CELL


class CityData:
    def __init__(self):
        self.chunks = {}
        self.far = MeshBuilder()
        self.boxes = []
        self.lamps = []          # positions des têtes de lampadaires
        self.buildings = []      # (x0, z0, x1, z1, hauteur)
        self.parks = []
        self.plazas = []
        self.intersections = []
        self.street_points = []
        self.beacon_points = []
        self.rooftops = []
        self.player_spawn = (0.0, CURB, 26.0)
        self.half = WALL

    def chunk(self, x, z):
        i = int(min(CHUNKS - 1, max(0, (x + WALL + 4) // CHUNK_SIZE)))
        j = int(min(CHUNKS - 1, max(0, (z + WALL + 4) // CHUNK_SIZE)))
        if (i, j) not in self.chunks:
            self.chunks[(i, j)] = MeshBuilder()
        return self.chunks[(i, j)]

    def add_box_collider(self, x0, y0, z0, x1, y1, z1):
        self.boxes.append((min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1)))

    def place(self, name, x, y, z, yaw=0.0, s=1.0, color=None, color_layers=None):
        m = mu.translate(x, y, z) @ mu.rot_y(yaw) @ mu.scale(s)
        self.chunk(x, z).add(models.get(name), m, color, color_layers)


def generate(seed=7, progress=None):
    rng = np.random.default_rng(seed)
    city = CityData()

    def prog(f, msg):
        if progress:
            progress(f, msg)

    # ---- sol lointain & mur d'enceinte ---------------------------------------
    far = city.far
    far.quad((-1600, -0.03, 1600), (1600, -0.03, 1600), (1600, -0.03, -1600), (-1600, -0.03, -1600),
             [(-200, 200), (200, 200), (200, -200), (-200, -200)], L["asphalt"])
    _skyline(city, rng)
    for side in range(4):
        for k in range(N):
            a = -WALL + k * (2 * WALL / N)
            b = a + 2 * WALL / N
            if side == 0:
                mn, mx = (a, 0, -WALL - 1.0), (b, 7.0, -WALL)
            elif side == 1:
                mn, mx = (a, 0, WALL), (b, 7.0, WALL + 1.0)
            elif side == 2:
                mn, mx = (-WALL - 1.0, 0, a), (-WALL, 7.0, b)
            else:
                mn, mx = (WALL, 0, a), (WALL + 1.0, 7.0, b)
            cx, cz = (mn[0] + mx[0]) / 2, (mn[2] + mx[2]) / 2
            ch = city.chunk(cx, cz)
            ch.box(mn, (mx[0], 1.2, mx[2]), L["hazard"], tile_u=2.0, tile_v=1.2)
            ch.box((mn[0], 1.2, mn[2]), mx, L["concrete"], tile_u=4, tile_v=4, top_tile=4)
            city.add_box_collider(*mn, *mx)
    # mur virtuel haut (empêche les drones et le joueur de sortir)
    prog(0.1, "Routes")

    # ---- routes ---------------------------------------------------------------
    for k in range(N + 1):
        c = road_c(k)
        for i in range(N):
            a = road_c(i) + ROAD / 2
            b = road_c(i + 1) - ROAD / 2
            # route orientée selon X (z = c)
            _road_segment(city, c, a, b, along_x=True)
            _road_segment(city, c, a, b, along_x=False)
        for i in range(N + 1):
            x = road_c(i)
            ch = city.chunk(x, c)
            ch.quad((x - 7, 0, c + 7), (x + 7, 0, c + 7), (x + 7, 0, c - 7), (x - 7, 0, c - 7),
                    [((x - 7) / 8, (c + 7) / 8), ((x + 7) / 8, (c + 7) / 8), ((x + 7) / 8, (c - 7) / 8),
                     ((x - 7) / 8, (c - 7) / 8)], L["asphalt"])
            city.intersections.append((x, c))
            if 0 < i < N and 0 < k < N:
                city.beacon_points.append((x, 0.0, c))

    # ---- choix des contenus d'îlots -------------------------------------------
    lots = [(i, j) for i in range(N) for j in range(N)]
    kinds = {lot: "buildings" for lot in lots}
    kinds[(3, 3)] = "plaza"
    candidates = [l for l in lots if max(abs(l[0] - 3), abs(l[1] - 3)) >= 2]
    rng.shuffle(candidates)
    for l in candidates[:3]:
        kinds[l] = "park"
    for l in candidates[3:4]:
        kinds[l] = "yard"
    near = [l for l in lots if max(abs(l[0] - 3), abs(l[1] - 3)) == 1]
    rng.shuffle(near)
    kinds[near[0]] = "park"

    for n_lot, (i, j) in enumerate(lots):
        x0 = road_c(i) + ROAD / 2
        x1 = road_c(i + 1) - ROAD / 2
        z0 = road_c(j) + ROAD / 2
        z1 = road_c(j + 1) - ROAD / 2
        kind = kinds[(i, j)]
        _block_base(city, rng, x0, z0, x1, z1, kind)
        ix0, iz0, ix1, iz1 = x0 + SIDEWALK, z0 + SIDEWALK, x1 - SIDEWALK, z1 - SIDEWALK
        dist = max(abs(i - 3), abs(j - 3)) / 3.0
        if kind == "buildings":
            _buildings(city, rng, ix0, iz0, ix1, iz1, dist)
        elif kind == "park":
            _park(city, rng, ix0, iz0, ix1, iz1)
        elif kind == "plaza":
            _plaza(city, rng, ix0, iz0, ix1, iz1)
        else:
            _yard(city, rng, ix0, iz0, ix1, iz1)
        prog(0.15 + 0.8 * (n_lot + 1) / len(lots), "Quartiers")

    # voitures garées et abandonnées
    _cars(city, rng)
    prog(1.0, "Ville prête")
    return city


# ----------------------------------------------------------------------------
def _road_segment(city, c, a, b, along_x):
    cw = 4.0
    if along_x:
        ch = city.chunk((a + b) / 2, c)
        u0, u1 = 0.0, 1.0
        # tronçon principal
        xa, xb = a + cw, b - cw
        ch.quad((xa, 0, c + 7), (xb, 0, c + 7), (xb, 0, c - 7), (xa, 0, c - 7),
                [(u1, xa / 12), (u1, xb / 12), (u0, xb / 12), (u0, xa / 12)], L["road"])
        for (s, e) in ((a, a + cw), (b - cw, b)):
            ch.quad((s, 0, c + 7), (e, 0, c + 7), (e, 0, c - 7), (s, 0, c - 7),
                    [(1, 0), (1, 1), (0, 1), (0, 0)], L["crosswalk"])
    else:
        ch = city.chunk(c, (a + b) / 2)
        za, zb = a + cw, b - cw
        ch.quad((c - 7, 0, za), (c - 7, 0, zb), (c + 7, 0, zb), (c + 7, 0, za),
                [(0, za / 12), (0, zb / 12), (1, zb / 12), (1, za / 12)], L["road"])
        for (s, e) in ((a, a + cw), (b - cw, b)):
            ch.quad((c - 7, 0, s), (c - 7, 0, e), (c + 7, 0, e), (c + 7, 0, s),
                    [(0, 0), (0, 1), (1, 1), (1, 0)], L["crosswalk"])


def _block_base(city, rng, x0, z0, x1, z1, kind):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    ch = city.chunk(cx, cz)
    # dalle du trottoir (bordure en béton)
    ch.box((x0, -0.05, z0), (x1, CURB, z1), L["concrete"], top_layer=L["sidewalk"], tile_u=4, tile_v=4,
           top_tile=4, faces="xXzZY")
    city.add_box_collider(x0, -0.05, z0, x1, CURB, z1)
    # mobilier le long des 4 côtés
    sides = [((x0, z0), (x1, z0), (0, -1)), ((x1, z0), (x1, z1), (1, 0)),
             ((x1, z1), (x0, z1), (0, 1)), ((x0, z1), (x0, z0), (-1, 0))]
    has_trees = kind in ("buildings", "plaza") and rng.random() < 0.7
    for (pa, pb, nrm) in sides:
        length = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        dx, dz = (pb[0] - pa[0]) / length, (pb[1] - pa[1]) / length
        inward = 0.9
        n_l = int(length // 22)
        for k in range(n_l):
            t = (k + 0.5) * length / n_l
            px = pa[0] + dx * t - nrm[0] * inward
            pz = pa[1] + dz * t - nrm[1] * inward
            # le bras du lampadaire (axe +X local) pointe vers la route
            yaw = -math.atan2(nrm[1], nrm[0])
            city.place("lamppost", px, CURB, pz, yaw)
            city.add_box_collider(px - 0.2, 0, pz - 0.2, px + 0.2, 7.0, pz + 0.2)
            hx, hz = px + nrm[0] * 1.6, pz + nrm[1] * 1.6
            city.lamps.append((hx, 6.3, hz))
        if has_trees:
            n_t = int(length // 15)
            for k in range(n_t):
                t = (k + 0.25) * length / n_t + 2.0
                if t > length - 3:
                    continue
                px = pa[0] + dx * t - nrm[0] * 1.3
                pz = pa[1] + dz * t - nrm[1] * 1.3
                ch2 = city.chunk(px, pz)
                ch2.box((px - 0.7, CURB, pz - 0.7), (px + 0.7, CURB + 0.03, pz + 0.7), L["dirt"], faces="Y", top_tile=2)
                city.place(f"tree_{rng.integers(0, 4)}", px, CURB, pz, rng.random() * 6.28, 0.8 + rng.random() * 0.35)
                city.add_box_collider(px - 0.25, 0, pz - 0.25, px + 0.25, 4.0, pz + 0.25)
        # bancs, poubelles, bornes à incendie
        for k in range(int(length // 12)):
            if rng.random() < 0.35:
                t = 4 + rng.random() * (length - 8)
                px = pa[0] + dx * t - nrm[0] * 1.0
                pz = pa[1] + dz * t - nrm[1] * 1.0
                r = rng.random()
                if r < 0.4:
                    city.place("bin", px, CURB, pz)
                    city.add_box_collider(px - 0.3, 0, pz - 0.3, px + 0.3, 1.0, pz + 0.3)
                elif r < 0.65:
                    city.place("hydrant", px, CURB, pz, rng.random() * 6.28)
                    city.add_box_collider(px - 0.2, 0, pz - 0.2, px + 0.2, 0.85, pz + 0.2)
                else:
                    yaw = math.atan2(-nrm[0], -nrm[1])
                    city.place("bench", px - nrm[0] * 0.6, CURB, pz - nrm[1] * 0.6, yaw)
        city.street_points.append((pa[0] + dx * length * 0.5 - nrm[0] * 1.5, CURB, pa[1] + dz * length * 0.5 - nrm[1] * 1.5))
    # feux tricolores aux coins
    corners = [(x0, z0, -1, -1), (x1, z0, 1, -1), (x1, z1, 1, 1), (x0, z1, -1, 1)]
    for (px, pz, sx, sz) in corners:
        if rng.random() < 0.5:
            ppx, ppz = px - sx * 0.8, pz - sz * 0.8
            yaw = -math.atan2(0, sx) if rng.random() < 0.5 else -math.atan2(sz, 0)
            city.place("traffic_light", ppx, CURB, ppz, yaw)
            city.add_box_collider(ppx - 0.15, 0, ppz - 0.15, ppx + 0.15, 4.7, ppz + 0.15)
        for b in range(2):
            bz = pz - sz * (2.0 + b * 1.4)
            city.place("bollard", px - sx * 0.35, CURB, bz)
            city.place("bollard", px - sx * (2.0 + b * 1.4), CURB, pz - sz * 0.35)


def _facade_layer(rng, height):
    if height > 45:
        return rng.choice([L["glass_tower"], L["dark_panel"], L["glass_tower"]])
    if height > 25:
        return rng.choice([L["panel"], L["dark_panel"], L["glass_tower"], L["brick"]])
    return rng.choice([L["brick"], L["brick"], L["panel"], L["dark_panel"]])


def _buildings(city, rng, x0, z0, x1, z1, dist):
    w = x1 - x0  # 38
    pattern = rng.choice(["single", "halves", "quads", "quads", "halves"])
    plots = []
    if pattern == "single":
        plots.append((x0 + 1, z0 + 1, x1 - 1, z1 - 1))
    elif pattern == "halves":
        if rng.random() < 0.5:
            plots += [(x0, z0, x0 + 18, z1 - 2), (x0 + 20, z0 + 2, x1, z1)]
        else:
            plots += [(x0, z0, x1 - 2, z0 + 18), (x0 + 2, z0 + 20, x1, z1)]
    else:
        plots += [(x0, z0, x0 + 18, z0 + 18), (x0 + 20, z0, x1, z0 + 18),
                  (x0, z0 + 20, x0 + 18, z1), (x0 + 20, z0 + 20, x1, z1)]
    # sol de cour / ruelles
    ch = city.chunk((x0 + x1) / 2, (z0 + z1) / 2)
    ch.box((x0, CURB, z0), (x1, CURB + 0.01, z1), L["concrete"], faces="Y", top_tile=4)
    for (a0, b0, a1, b1) in plots:
        max_f = int(4 + 18 * (1 - dist) ** 1.5)
        floors = int(rng.integers(3, max(4, max_f) + 1))
        if pattern == "single":
            floors = max(floors, 6)
        _building(city, rng, a0, b0, a1, b1, floors)


def _building(city, rng, x0, z0, x1, z1, floors):
    ch = city.chunk((x0 + x1) / 2, (z0 + z1) / 2)
    tint = 0.85 + rng.random(3) * 0.2
    tint = tuple(float(t) for t in (tint * (0.95 + 0.1 * rng.random())))
    base = CURB
    height = 4.5 + floors * 3.2
    layer = _facade_layer(rng, height)
    store = rng.random() < (0.8 if layer != L["glass_tower"] else 0.35)
    top = base + (4.35 if store else 0.0) + floors * 3.2
    if store:
        ch.box((x0 - 0.12, base, z0 - 0.12), (x1 + 0.12, 4.5, z1 + 0.12), L["storefront"], tile_u=12, tile_v=4.35,
               v_origin=base, faces="xXzZ", color=tint, u_center=True)
        ch.box((x0 - 0.4, 4.5, z0 - 0.4), (x1 + 0.4, 4.8, z1 + 0.4), L["concrete"], tile_u=4, tile_v=4,
               top_tile=4, color=(0.8, 0.8, 0.8))
        ch.box((x0, 4.8, z0), (x1, top, z1), layer, top_layer=L["roof"], tile_u=12, tile_v=6.4,
               v_origin=4.8, top_tile=6, color=tint, faces="xXzZY", u_center=True)
        # auvents au-dessus des vitrines
        for face in range(4):
            if rng.random() < 0.55:
                _awnings(city, rng, x0, z0, x1, z1, face)
    else:
        ch.box((x0, base, z0), (x1, top, z1), layer, top_layer=L["roof"], tile_u=12, tile_v=6.4,
               v_origin=base, top_tile=6, color=tint, faces="xXzZY", u_center=True)
    # corniche + acrotère
    ch.box((x0 - 0.35, top, z0 - 0.35), (x1 + 0.35, top + 0.5, z1 + 0.35), L["concrete"], tile_u=4, tile_v=4,
           faces="xXzZy", color=(0.75, 0.74, 0.72))
    par = 0.3
    for (a, b) in (((x0 - 0.35, z0 - 0.35), (x1 + 0.35, z0 - 0.35 + par)), ((x0 - 0.35, z1 + 0.35 - par), (x1 + 0.35, z1 + 0.35)),
                   ((x0 - 0.35, z0 - 0.35), (x0 - 0.35 + par, z1 + 0.35)), ((x1 + 0.35 - par, z0 - 0.35), (x1 + 0.35, z1 + 0.35))):
        ch.box((a[0], top + 0.5, a[1]), (b[0], top + 1.3, b[1]), L["concrete"], tile_u=4, tile_v=4, top_tile=4,
               color=(0.7, 0.7, 0.68))
    ch.box((x0, top, z0), (x1, top + 0.52, z1), L["roof"], faces="Y", top_tile=6)
    total_top = top + 0.5
    # tour en retrait pour les grands immeubles
    if floors > 10 and rng.random() < 0.6 and (x1 - x0) > 14:
        ins = 3.0
        extra = int(rng.integers(3, 9))
        tx0, tz0, tx1, tz1 = x0 + ins, z0 + ins, x1 - ins, z1 - ins
        ttop = total_top + extra * 3.2
        lay2 = layer if rng.random() < 0.6 else L["glass_tower"]
        ch.box((tx0, total_top, tz0), (tx1, ttop, tz1), lay2, top_layer=L["roof"], tile_u=12, tile_v=6.4,
               v_origin=total_top, top_tile=6, color=tint, faces="xXzZY", u_center=True)
        ch.box((tx0 - 0.25, ttop, tz0 - 0.25), (tx1 + 0.25, ttop + 0.6, tz1 + 0.25), L["concrete"], tile_u=4,
               tile_v=4, top_tile=4, color=(0.75, 0.74, 0.72))
        city.add_box_collider(tx0, total_top, tz0, tx1, ttop + 0.6, tz1)
        # antenne avec balise rouge
        ax, az = (tx0 + tx1) / 2, (tz0 + tz1) / 2
        ch.cylinder((ax, ttop + 0.6, az), 0.12, 9.0, L["brushed"], seg=8, radius_top=0.05)
        ch.sphere((ax, ttop + 9.7, az), 0.25, L["emissive"], seg_u=8, seg_v=5, color=(1.0, 0.05, 0.02))
        city.rooftops.append((ax, ttop + 0.6, az))
        roof_props_top = total_top
    else:
        roof_props_top = total_top
    city.add_box_collider(x0 - 0.12, 0, z0 - 0.12, x1 + 0.12, total_top, z1 + 0.12)
    # équipements de toit
    for _ in range(int(rng.integers(1, 4))):
        px = rng.uniform(x0 + 2, x1 - 2)
        pz = rng.uniform(z0 + 2, z1 - 2)
        if floors > 10 and (x1 - x0) > 14 and x0 + 3 < px < x1 - 3 and z0 + 3 < pz < z1 - 3:
            continue
        city.place("ac_unit", px, roof_props_top, pz, rng.random() * 6.28)
    if layer == L["brick"] and rng.random() < 0.5 and floors < 10:
        px = rng.uniform(x0 + 3, x1 - 3)
        pz = rng.uniform(z0 + 3, z1 - 3)
        city.place("water_tank", px, roof_props_top, pz)
    city.buildings.append((x0, z0, x1, z1, total_top))
    city.rooftops.append(((x0 + x1) / 2, total_top, (z0 + z1) / 2))


AWNING_COLORS = [(0.7, 0.12, 0.08), (0.12, 0.35, 0.2), (0.15, 0.25, 0.55), (0.75, 0.55, 0.15), (0.3, 0.3, 0.3)]


def _awnings(city, rng, x0, z0, x1, z1, face):
    color = AWNING_COLORS[int(rng.integers(0, len(AWNING_COLORS)))]
    out = 1.3
    if face in (0, 2):
        length = x1 - x0
        z = z0 - 0.12 if face == 0 else z1 + 0.12
        s = -1 if face == 0 else 1
        margin = ((length % 3.0) * 0.5)
        x = x0 + margin
        while x + 6 <= x1 + 0.01:
            a, b = x + 0.3, x + 4.2
            if face == 2:
                a, b = x1 - (x - x0) - 4.2, x1 - (x - x0) - 0.3
            ch = city.chunk((a + b) / 2, z)
            ch.quad((a, 3.45, z), (b, 3.45, z), (b, 2.85, z + s * out), (a, 2.85, z + s * out),
                    [(0, 0), (2, 0), (2, 0.7), (0, 0.7)], L["awning"], color)
            x += 6
    else:
        length = z1 - z0
        x = x0 - 0.12 if face == 3 else x1 + 0.12
        s = -1 if face == 3 else 1
        margin = ((length % 3.0) * 0.5)
        z = z0 + margin
        while z + 6 <= z1 + 0.01:
            a, b = z + 0.3, z + 4.2
            if face == 1:
                a, b = z1 - (z - z0) - 4.2, z1 - (z - z0) - 0.3
            ch = city.chunk(x, (a + b) / 2)
            ch.quad((x, 3.45, a), (x, 3.45, b), (x + s * out, 2.85, b), (x + s * out, 2.85, a),
                    [(0, 0), (2, 0), (2, 0.7), (0, 0.7)], L["awning"], color)
            z += 6


def _park(city, rng, x0, z0, x1, z1):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    ch = city.chunk(cx, cz)
    ch.box((x0, CURB, z0), (x1, CURB + 0.08, z1), L["concrete"], top_layer=L["grass"], top_tile=6, tile_u=4, tile_v=4)
    city.add_box_collider(x0, 0, z0, x1, CURB + 0.08, z1)
    py = CURB + 0.09
    pw = 1.6
    ch.box((cx - pw, CURB, z0), (cx + pw, py, z1), L["plaza"], faces="Y", top_tile=4)
    ch.box((x0, CURB, cz - pw), (x1, py, cz + pw), L["plaza"], faces="Y", top_tile=4)
    city.parks.append((x0, z0, x1, z1))
    has_fountain = rng.random() < 0.6
    if has_fountain:
        ch.box((cx - 7, CURB, cz - 7), (cx + 7, py + 0.005, cz + 7), L["plaza"], faces="Y", top_tile=4)
        city.place("fountain", cx, py, cz)
        city.add_box_collider(cx - 4.2, 0, cz - 4.2, cx + 4.2, py + 0.7, cz + 4.2)
        city.add_box_collider(cx - 1.2, 0, cz - 1.2, cx + 1.2, py + 2.5, cz + 1.2)
    city.beacon_points.append((cx + 10, py, cz + 10))
    city.street_points.append((cx - 12, py, cz + 3))
    # arbres
    placed = []
    for _ in range(40):
        if len(placed) >= 11:
            break
        tx = rng.uniform(x0 + 3, x1 - 3)
        tz = rng.uniform(z0 + 3, z1 - 3)
        if abs(tx - cx) < pw + 2.5 or abs(tz - cz) < pw + 2.5:
            continue
        if any((tx - a) ** 2 + (tz - b) ** 2 < 36 for a, b in placed):
            continue
        placed.append((tx, tz))
        city.place(f"tree_{rng.integers(0, 4)}", tx, py, tz, rng.random() * 6.28, 0.9 + rng.random() * 0.5)
        city.add_box_collider(tx - 0.3, 0, tz - 0.3, tx + 0.3, 4.5, tz + 0.3)
    # herbes hautes
    for _ in range(260):
        gx = rng.uniform(x0 + 0.5, x1 - 0.5)
        gz = rng.uniform(z0 + 0.5, z1 - 0.5)
        if abs(gx - cx) < pw + 0.3 or abs(gz - cz) < pw + 0.3:
            continue
        if has_fountain and abs(gx - cx) < 7.3 and abs(gz - cz) < 7.3:
            continue
        city.place(f"grass_{rng.integers(0, 2)}", gx, py - 0.02, gz, rng.random() * 6.28, 0.8 + rng.random() * 0.7)
    # haies et bancs
    for (hx, hz, yaw) in ((cx - 10, z0 + 1.2, 0), (cx + 10, z1 - 1.2, 0), (x0 + 1.2, cz + 10, math.pi / 2),
                          (x1 - 1.2, cz - 10, math.pi / 2)):
        city.place("hedge", hx, py, hz, yaw)
        if yaw == 0:
            city.add_box_collider(hx - 3.2, 0, hz - 0.7, hx + 3.2, 1.3, hz + 0.7)
        else:
            city.add_box_collider(hx - 0.7, 0, hz - 3.2, hx + 0.7, 1.3, hz + 3.2)
    for (bx, bz, yaw) in ((cx - pw - 0.8, cz - 11, math.pi / 2), (cx + pw + 0.8, cz + 11, -math.pi / 2),
                          (cx - 11, cz + pw + 0.8, math.pi), (cx + 11, cz - pw - 0.8, 0)):
        city.place("bench", bx, py, bz, yaw)


def _plaza(city, rng, x0, z0, x1, z1):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    ch = city.chunk(cx, cz)
    ch.box((x0, CURB, z0), (x1, CURB + 0.02, z1), L["plaza"], faces="Y", top_tile=4)
    city.plazas.append((x0, z0, x1, z1))
    py = CURB + 0.02
    city.place("monument", cx, py, cz)
    city.add_box_collider(cx - 4, 0, cz - 4, cx + 4, py + 0.5, cz + 4)
    city.add_box_collider(cx - 3, 0, cz - 3, cx + 3, py + 1.0, cz + 3)
    city.add_box_collider(cx - 1.2, 0, cz - 1.2, cx + 1.2, py + 11.5, cz + 1.2)
    # couverture : conteneurs et barrières
    cont = [(-12, -12, 0.0), (12, 12, 0.0), (-12, 12, math.pi / 2), (12, -12, math.pi / 2)]
    for (dx, dz, yaw) in cont:
        col = AWNING_COLORS[int(rng.integers(0, len(AWNING_COLORS)))]
        x, z = cx + dx, cz + dz
        city.place("container", x, py, z, yaw, color=col, color_layers=[L["container"]])
        hx, hz = (1.22, 3.0) if yaw == 0 else (3.0, 1.22)
        city.add_box_collider(x - hx, 0, z - hz, x + hx, py + 2.6, z + hz)
    for (dx, dz, yaw) in ((0, -10, 0), (0, 10, 0), (-10, 0, math.pi / 2), (10, 0, math.pi / 2),
                          (-6, -15, 0.3), (6, 15, 0.3), (15, 5, 1.2), (-15, -5, 1.2)):
        x, z = cx + dx, cz + dz
        city.place("barrier", x, py, z, yaw)
        c, s = abs(math.cos(yaw)), abs(math.sin(yaw))
        hx, hz = 1.5 * c + 0.32 * s, 1.5 * s + 0.32 * c
        city.add_box_collider(x - hx, 0, z - hz, x + hx, py + 0.95, z + hz)
    for (dx, dz) in ((-16, -16), (16, -16), (-16, 16), (16, 16)):
        city.place("lamppost", cx + dx, py, cz + dz, -math.atan2(-dz, -dx))
        city.lamps.append((cx + dx * 0.92, 6.3, cz + dz * 0.92))
        city.add_box_collider(cx + dx - 0.2, 0, cz + dz - 0.2, cx + dx + 0.2, 7, cz + dz + 0.2)
    city.beacon_points += [(cx, py, cz - 8), (cx + 8, py, cz), (cx - 8, py, cz)]
    city.street_points += [(cx - 16, py, cz), (cx + 16, py, cz)]
    city.player_spawn = (cx, py, z1 + 1.5)


def _yard(city, rng, x0, z0, x1, z1):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    ch = city.chunk(cx, cz)
    ch.box((x0, CURB, z0), (x1, CURB + 0.02, z1), L["dirt"], faces="Y", top_tile=6)
    py = CURB + 0.02
    for row in range(3):
        for k in range(3):
            if rng.random() < 0.25:
                continue
            x = x0 + 6 + k * 13
            z = z0 + 7 + row * 12
            yaw = 0.0 if (row + k) % 2 == 0 else math.pi / 2
            hx, hz = (1.22, 3.0) if yaw == 0 else (3.0, 1.22)
            stack = 2 if rng.random() < 0.4 else 1
            for s in range(stack):
                col = AWNING_COLORS[int(rng.integers(0, len(AWNING_COLORS)))]
                city.place("container", x, py + s * 2.6, z, yaw, color=col, color_layers=[L["container"]])
            city.add_box_collider(x - hx, 0, z - hz, x + hx, py + 2.6 * stack, z + hz)
            if stack == 2:
                city.rooftops.append((x, py + 5.2, z))
    for _ in range(6):
        x = rng.uniform(x0 + 3, x1 - 3)
        z = rng.uniform(z0 + 3, z1 - 3)
        yaw = rng.random() * 3.14
        city.place("barrier", x, py, z, yaw)
        c, s = abs(math.cos(yaw)), abs(math.sin(yaw))
        hx, hz = 1.5 * c + 0.32 * s, 1.5 * s + 0.32 * c
        city.add_box_collider(x - hx, 0, z - hz, x + hx, py + 0.95, z + hz)
    city.street_points.append((cx, py, cz))
    city.beacon_points.append((cx, py, cz))


def _cars(city, rng):
    car = models.get("car")
    for k in range(N + 1):
        c = road_c(k)
        for i in range(N):
            a = road_c(i) + ROAD / 2 + 6
            b = road_c(i + 1) - ROAD / 2 - 6
            for along_x in (True, False):
                for side in (-1, 1):
                    t = a
                    while t < b - 4.6:
                        if rng.random() < 0.42:
                            off = c + side * (ROAD / 2 - 1.25)
                            if along_x:
                                x, z, yaw = t + 2.3, off, math.pi / 2 + (0 if side > 0 else math.pi)
                            else:
                                x, z, yaw = off, t + 2.3, (0 if side > 0 else math.pi)
                            col = models.CAR_COLORS[int(rng.integers(0, len(models.CAR_COLORS)))]
                            city.place("car", x, 0.0, z, yaw, color=col, color_layers=[L["paint"]])
                            if along_x:
                                city.add_box_collider(x - 2.3, 0, z - 0.95, x + 2.3, 1.45, z + 0.95)
                            else:
                                city.add_box_collider(x - 0.95, 0, z - 2.3, x + 0.95, 1.45, z + 2.3)
                        t += 5.8 + rng.random() * 1.5
    # quelques véhicules abandonnés en travers (couverture)
    for _ in range(14):
        k = int(rng.integers(1, N))
        i = int(rng.integers(0, N))
        c = road_c(k)
        t = rng.uniform(road_c(i) + 14, road_c(i + 1) - 14)
        yaw = rng.uniform(0.3, 1.2) * (1 if rng.random() < 0.5 else -1)
        if rng.random() < 0.5:
            x, z = t, c + rng.uniform(-2, 2)
            yaw += math.pi / 2
        else:
            x, z = c + rng.uniform(-2, 2), t
        col = models.CAR_COLORS[int(rng.integers(0, len(models.CAR_COLORS)))]
        city.place("car", x, 0.0, z, yaw, color=col, color_layers=[L["paint"]])
        cs, sn = abs(math.cos(yaw)), abs(math.sin(yaw))
        hx = 0.95 * cs + 2.3 * sn
        hz = 0.95 * sn + 2.3 * cs
        # boîte englobante réduite (approximation d'une voiture orientée)
        city.add_box_collider(x - hx * 0.8, 0, z - hz * 0.8, x + hx * 0.8, 1.45, z + hz * 0.8)


def _skyline(city, rng):
    far = city.far
    layers = [L["glass_tower"], L["dark_panel"], L["panel"], L["brick"]]
    for _ in range(170):
        a = rng.random() * 2 * math.pi
        r = rng.uniform(270, 650)
        x, z = math.cos(a) * r, math.sin(a) * r
        w = rng.uniform(18, 40)
        d = rng.uniform(18, 40)
        h = rng.uniform(25, 60) + (150 - min(r, 650) * 0.15) * rng.random()
        lay = layers[int(rng.integers(0, 4))]
        tint = tuple(float(t) for t in (0.8 + rng.random(3) * 0.2))
        far.box((x - w / 2, 0, z - d / 2), (x + w / 2, h, z + d / 2), lay, top_layer=L["roof"], tile_u=12, tile_v=6.4,
                top_tile=8, color=tint, faces="xXzZY")
