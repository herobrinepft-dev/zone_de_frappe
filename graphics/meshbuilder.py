"""Construction de maillages : format de sommet unique (12 flottants).

  position (3) | normale (3) | uv (2) | couche matériau (1) | couleur (3)
"""
import math
import numpy as np

STRIDE = 12
FORMAT = "3f 3f 2f 1f 3f"


def transform_array(arr, m, color=None, color_layers=None):
    """Applique une matrice 4x4 à un tableau de sommets (copie)."""
    out = arr.copy()
    p = out[:, 0:3]
    out[:, 0:3] = p @ m[:3, :3].T + m[:3, 3]
    nm = np.linalg.inv(m[:3, :3]).T
    n = out[:, 3:6] @ nm.T
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    out[:, 3:6] = n
    if color is not None:
        c = np.asarray(color, np.float32)
        if color_layers is None:
            out[:, 9:12] *= c
        else:
            mask = np.isin(out[:, 8].round().astype(int), color_layers)
            out[mask, 9:12] *= c
    return out


class MeshBuilder:
    def __init__(self):
        self.parts = []

    # ------------------------------------------------------------------
    def _tri_array(self, pos, nrm, uv, layer, color):
        n = len(pos)
        a = np.empty((n, STRIDE), np.float32)
        a[:, 0:3] = pos
        a[:, 3:6] = nrm
        a[:, 6:8] = uv
        a[:, 8] = layer
        a[:, 9:12] = color
        return a

    def add(self, arr, matrix=None, color=None, color_layers=None):
        if matrix is not None or color is not None:
            arr = transform_array(arr, matrix if matrix is not None else np.eye(4), color, color_layers)
        self.parts.append(np.asarray(arr, np.float32))

    def quad(self, p0, p1, p2, p3, uvs, layer, color=(1, 1, 1), normal=None):
        p = np.array([p0, p1, p2, p3], np.float32)
        if normal is None:
            n = np.cross(p[1] - p[0], p[3] - p[0])
            ln = np.linalg.norm(n)
            n = n / ln if ln > 1e-9 else np.array([0, 1, 0], np.float32)
        else:
            n = np.asarray(normal, np.float32)
        uv = np.array(uvs, np.float32)
        idx = [0, 1, 2, 0, 2, 3]
        self.parts.append(self._tri_array(p[idx], n, uv[idx], layer, color))

    def box(self, mn, mx, layer, top_layer=None, bottom_layer=None, tile_u=1.0, tile_v=1.0,
            v_origin=None, top_tile=None, color=(1, 1, 1), faces="xXzZyY", u_center=False):
        """Boîte alignée. Les UV des faces latérales sont en mètres / tuile.

        faces : x=-X, X=+X, z=-Z, Z=+Z, y=-Y (dessous), Y=+Y (dessus).
        u_center : centre le motif horizontal (fenêtres entières) sur la face.
        """
        x0, y0, z0 = mn
        x1, y1, z1 = mx
        if top_layer is None:
            top_layer = layer
        if bottom_layer is None:
            bottom_layer = layer
        if v_origin is None:
            v_origin = y0
        tt = top_tile if top_tile is not None else tile_u
        va, vb = (y0 - v_origin) / tile_v, (y1 - v_origin) / tile_v

        def uoff(width):
            if not u_center:
                return 0.0
            cell = tile_u / 4.0
            return -((width % cell) * 0.5) / tile_u

        if "X" in faces:  # +X, u vers -Z
            w = z1 - z0
            o = uoff(w)
            self.quad((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1),
                      [(o, va), (o + w / tile_u, va), (o + w / tile_u, vb), (o, vb)], layer, color, (1, 0, 0))
        if "x" in faces:  # -X, u vers +Z
            w = z1 - z0
            o = uoff(w)
            self.quad((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0),
                      [(o, va), (o + w / tile_u, va), (o + w / tile_u, vb), (o, vb)], layer, color, (-1, 0, 0))
        if "Z" in faces:  # +Z, u vers +X
            w = x1 - x0
            o = uoff(w)
            self.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
                      [(o, va), (o + w / tile_u, va), (o + w / tile_u, vb), (o, vb)], layer, color, (0, 0, 1))
        if "z" in faces:  # -Z, u vers -X
            w = x1 - x0
            o = uoff(w)
            self.quad((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0),
                      [(o, va), (o + w / tile_u, va), (o + w / tile_u, vb), (o, vb)], layer, color, (0, 0, -1))
        if "Y" in faces:
            self.quad((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0),
                      [(x0 / tt, -z1 / tt), (x1 / tt, -z1 / tt), (x1 / tt, -z0 / tt), (x0 / tt, -z0 / tt)],
                      top_layer, color, (0, 1, 0))
        if "y" in faces:
            self.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
                      [(x0 / tt, z0 / tt), (x1 / tt, z0 / tt), (x1 / tt, z1 / tt), (x0 / tt, z1 / tt)],
                      bottom_layer, color, (0, -1, 0))

    def cbox(self, center, half, layer, color=(1, 1, 1), tile=1.0, **kw):
        c = np.asarray(center, np.float64)
        h = np.asarray(half, np.float64)
        self.box(tuple(c - h), tuple(c + h), layer, color=color, tile_u=tile, tile_v=tile, top_tile=tile, **kw)

    def cylinder(self, base, radius, height, layer, seg=16, color=(1, 1, 1), radius_top=None,
                 caps=True, tile_u=None, tile_v=None, cap_layer=None, axis="y"):
        r0 = radius
        r1 = radius if radius_top is None else radius_top
        if height < 0:  # cylindre « vers l'arrière » : on décale la base
            height = -height
            base = list(base)
            base["xyz".index(axis)] -= height
            r0, r1 = r1, r0
        circ = 2 * math.pi * max(r0, r1)
        tu = tile_u if tile_u else circ
        tv = tile_v if tile_v else max(height, 1e-3)
        ang = np.linspace(0, 2 * math.pi, seg + 1)
        ca, sa = np.cos(ang), np.sin(ang)
        slope = (r0 - r1) / max(height, 1e-6)
        rows = []
        for i in range(seg):
            for (j, k) in ((i, i + 1),):
                pa0 = (r0 * ca[j], 0, r0 * sa[j])
                pb0 = (r0 * ca[k], 0, r0 * sa[k])
                pa1 = (r1 * ca[j], height, r1 * sa[j])
                pb1 = (r1 * ca[k], height, r1 * sa[k])
                na = np.array([ca[j], slope, sa[j]])
                nb = np.array([ca[k], slope, sa[k]])
                na /= np.linalg.norm(na)
                nb /= np.linalg.norm(nb)
                ua, ub = ang[j] / (2 * math.pi) * circ / tu, ang[k] / (2 * math.pi) * circ / tu
                vtop = height / tv
                rows += [(pa0, na, (ua, 0)), (pb0, nb, (ub, 0)), (pb1, nb, (ub, vtop)),
                         (pa0, na, (ua, 0)), (pb1, nb, (ub, vtop)), (pa1, na, (ua, vtop))]
        if caps:
            cl = cap_layer if cap_layer is not None else layer
            cap_rows = []
            for i in range(seg):
                j, k = i, i + 1
                if r1 > 0:
                    cap_rows += [((0, height, 0), (0, 1, 0), (0.5, 0.5)),
                                 ((r1 * ca[k], height, r1 * sa[k]), (0, 1, 0), (0.5 + 0.5 * ca[k], 0.5 + 0.5 * sa[k])),
                                 ((r1 * ca[j], height, r1 * sa[j]), (0, 1, 0), (0.5 + 0.5 * ca[j], 0.5 + 0.5 * sa[j]))]
                if r0 > 0:
                    cap_rows += [((0, 0, 0), (0, -1, 0), (0.5, 0.5)),
                                 ((r0 * ca[j], 0, r0 * sa[j]), (0, -1, 0), (0.5 + 0.5 * ca[j], 0.5 + 0.5 * sa[j])),
                                 ((r0 * ca[k], 0, r0 * sa[k]), (0, -1, 0), (0.5 + 0.5 * ca[k], 0.5 + 0.5 * sa[k]))]
        pos = np.array([r[0] for r in rows], np.float32)
        nrm = np.array([r[1] for r in rows], np.float32)
        uv = np.array([r[2] for r in rows], np.float32)
        arr = self._tri_array(pos, nrm, uv, layer, color)
        if caps and cap_rows:
            cp = np.array([r[0] for r in cap_rows], np.float32)
            cn = np.array([r[1] for r in cap_rows], np.float32)
            cu = np.array([r[2] for r in cap_rows], np.float32)
            arr = np.concatenate([arr, self._tri_array(cp, cn, cu, cl, color)])
        m = np.eye(4)
        if axis == "x":
            m = np.array([[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], np.float64)
        elif axis == "z":
            m = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], np.float64)
        m[:3, 3] = base
        self.parts.append(transform_array(arr, m))

    def sphere(self, center, radius, layer, seg_u=16, seg_v=10, color=(1, 1, 1), scale=(1, 1, 1),
               noise=0.0, rng=None, uv_scale=1.0):
        u = np.linspace(0, 2 * math.pi, seg_u + 1)
        v = np.linspace(0, math.pi, seg_v + 1)
        uu, vv = np.meshgrid(u, v)
        x = np.sin(vv) * np.cos(uu)
        y = np.cos(vv)
        z = np.sin(vv) * np.sin(uu)
        r = np.full(x.shape, radius)
        if noise > 0 and rng is not None:
            rnd = rng.random((seg_v + 1, seg_u)) * 2 - 1
            rnd = np.concatenate([rnd, rnd[:, :1]], axis=1)
            rnd[0, :] = rnd[0, 0]
            rnd[-1, :] = rnd[-1, 0]
            r = r * (1 + noise * rnd)
        sx, sy, sz = scale
        P = np.stack([x * r * sx, y * r * sy, z * r * sz], -1) + np.asarray(center)
        N = np.stack([x / sx, y / sy, z / sz], -1)
        N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-9)
        UV = np.stack([uu / (2 * math.pi) * uv_scale * 2, vv / math.pi * uv_scale], -1)
        a = np.arange(seg_v)[:, None]
        b = np.arange(seg_u)[None, :]
        i00 = (a * (seg_u + 1) + b).ravel()
        i01 = i00 + 1
        i10 = i00 + seg_u + 1
        i11 = i10 + 1
        tri = np.stack([i00, i10, i11, i00, i11, i01], -1).reshape(-1)
        Pf, Nf, UVf = P.reshape(-1, 3), N.reshape(-1, 3), UV.reshape(-1, 2)
        self.parts.append(self._tri_array(Pf[tri], Nf[tri], UVf[tri], layer, color))

    def build(self):
        if not self.parts:
            return np.zeros((0, STRIDE), np.float32)
        return np.ascontiguousarray(np.concatenate(self.parts).astype(np.float32))
