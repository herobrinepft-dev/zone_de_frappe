"""Monde physique : boîtes de collision, grille spatiale, lancers de rayons."""
import math
import numpy as np

GRID = 16.0


class CollisionWorld:
    def __init__(self, boxes, half_extent):
        self.boxes = np.array(boxes, np.float64).reshape(-1, 6)
        self.mins = self.boxes[:, 0:3]
        self.maxs = self.boxes[:, 3:6]
        self.half = half_extent
        self.grid = {}
        for i, b in enumerate(self.boxes):
            for gx in range(int(math.floor(b[0] / GRID)), int(math.floor(b[3] / GRID)) + 1):
                for gz in range(int(math.floor(b[2] / GRID)), int(math.floor(b[5] / GRID)) + 1):
                    self.grid.setdefault((gx, gz), []).append(i)
        self.grid = {k: np.array(v, np.int32) for k, v in self.grid.items()}

    def query(self, x0, z0, x1, z1):
        out = []
        for gx in range(int(math.floor(x0 / GRID)), int(math.floor(x1 / GRID)) + 1):
            for gz in range(int(math.floor(z0 / GRID)), int(math.floor(z1 / GRID)) + 1):
                v = self.grid.get((gx, gz))
                if v is not None:
                    out.append(v)
        if not out:
            return np.zeros(0, np.int32)
        return np.unique(np.concatenate(out))

    # ------------------------------------------------------------------
    def raycast(self, origin, direction, max_dist, ground=True):
        """Renvoie (distance, normale) du premier impact ou (None, None)."""
        o = np.asarray(origin, np.float64)
        d = np.asarray(direction, np.float64)
        end = o + d * max_dist
        idx = self.query(min(o[0], end[0]), min(o[2], end[2]), max(o[0], end[0]), max(o[2], end[2]))
        best_t, best_n = None, None
        if len(idx):
            mn = self.mins[idx]
            mx = self.maxs[idx]
            with np.errstate(divide="ignore", invalid="ignore"):
                inv = 1.0 / np.where(np.abs(d) < 1e-12, 1e-12, d)
                t1 = (mn - o) * inv
                t2 = (mx - o) * inv
            tmin_axes = np.minimum(t1, t2)
            tmax_axes = np.maximum(t1, t2)
            tmin = tmin_axes.max(axis=1)
            tmax = tmax_axes.min(axis=1)
            hit = (tmax >= np.maximum(tmin, 0.0)) & (tmin <= max_dist)
            if hit.any():
                tm = np.where(hit, np.maximum(tmin, 0.0), np.inf)
                k = int(np.argmin(tm))
                best_t = float(tm[k])
                ax = int(np.argmax(tmin_axes[k]))
                n = np.zeros(3)
                n[ax] = -math.copysign(1.0, d[ax])
                best_n = n
        if ground and d[1] < -1e-6:
            tg = -o[1] / d[1]
            if 0 <= tg <= max_dist and (best_t is None or tg < best_t):
                best_t, best_n = tg, np.array([0.0, 1.0, 0.0])
        return best_t, best_n

    def line_of_sight(self, a, b):
        a = np.asarray(a, np.float64)
        b = np.asarray(b, np.float64)
        d = b - a
        dist = float(np.linalg.norm(d))
        if dist < 1e-6:
            return True
        t, _ = self.raycast(a, d / dist, dist - 0.3)
        return t is None

    def ground_height(self, x, z, feet, radius, step=0.45):
        """Hauteur du sol sous un cylindre (boîtes dont le dessus est sous les pieds + marche)."""
        idx = self.query(x - radius, z - radius, x + radius, z + radius)
        g = 0.0
        if len(idx):
            b = self.boxes[idx]
            over = (b[:, 0] < x + radius) & (b[:, 3] > x - radius) & (b[:, 2] < z + radius) & (b[:, 5] > z - radius)
            ok = over & (b[:, 4] <= feet + step)
            if ok.any():
                g = max(g, float(b[ok, 4].max()))
        return g

    def push_sphere(self, pos, radius):
        """Repousse une sphère hors des boîtes. Renvoie (nouvelle_pos, collision?)."""
        p = np.array(pos, np.float64)
        idx = self.query(p[0] - radius, p[2] - radius, p[0] + radius, p[2] + radius)
        hit = False
        for i in idx:
            mn, mx = self.mins[i], self.maxs[i]
            c = np.clip(p, mn, mx)
            dvec = p - c
            dist2 = float(dvec @ dvec)
            if dist2 < radius * radius:
                hit = True
                if dist2 > 1e-10:
                    dist = math.sqrt(dist2)
                    p += dvec / dist * (radius - dist)
                else:
                    # centre à l'intérieur : sortie par la face la plus proche
                    pen = np.concatenate([p - mn, mx - p])
                    k = int(np.argmin(pen))
                    ax = k % 3
                    if k < 3:
                        p[ax] = mn[ax] - radius
                    else:
                        p[ax] = mx[ax] + radius
        if p[1] < radius:
            p[1] = radius
            hit = True
        return p, hit

    def inside_any(self, p, margin=0.0):
        idx = self.query(p[0] - margin, p[2] - margin, p[0] + margin, p[2] + margin)
        for i in idx:
            if np.all(p >= self.mins[i] - margin) and np.all(p <= self.maxs[i] + margin):
                return True
        return False

    def max_height_near(self, x, z, r):
        idx = self.query(x - r, z - r, x + r, z + r)
        if not len(idx):
            return 0.0
        return float(self.maxs[idx, 1].max())
