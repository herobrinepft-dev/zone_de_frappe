"""Mathématiques 3D (matrices 4x4 en convention colonne, stockage NumPy ligne)."""
import math
import numpy as np


def normalize(v):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def perspective(fovy_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy_deg) / 2.0)
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2.0 * far * near / (near - far)
    m[3, 2] = -1.0
    return m


def ortho(l, r, b, t, n, f):
    m = np.eye(4)
    m[0, 0] = 2.0 / (r - l)
    m[1, 1] = 2.0 / (t - b)
    m[2, 2] = -2.0 / (f - n)
    m[0, 3] = -(r + l) / (r - l)
    m[1, 3] = -(t + b) / (t - b)
    m[2, 3] = -(f + n) / (f - n)
    return m


def look_at(eye, target, up=(0.0, 1.0, 0.0)):
    eye = np.asarray(eye, dtype=np.float64)
    f = normalize(np.asarray(target, dtype=np.float64) - eye)
    s = normalize(np.cross(f, up))
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m


def translate(x, y, z):
    m = np.eye(4)
    m[0, 3], m[1, 3], m[2, 3] = x, y, z
    return m


def scale(x, y=None, z=None):
    if y is None:
        y = z = x
    return np.diag([x, y, z, 1.0])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    return m


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[0, 0], m[0, 2], m[2, 0], m[2, 2] = c, s, -s, c
    return m


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[0, 0], m[0, 1], m[1, 0], m[1, 1] = c, -s, s, c
    return m


def to_gl(m):
    """Matrice NumPy -> octets colonne-major float32 pour OpenGL."""
    return np.ascontiguousarray(m.T, dtype=np.float32).tobytes()


def frustum_planes(vp):
    """6 plans (a,b,c,d) normalisés extraits d'une matrice vue-projection."""
    r = vp
    planes = np.array([
        r[3] + r[0], r[3] - r[0],
        r[3] + r[1], r[3] - r[1],
        r[3] + r[2], r[3] - r[2],
    ])
    n = np.linalg.norm(planes[:, :3], axis=1, keepdims=True)
    return planes / n


def aabbs_in_frustum(planes, mins, maxs):
    """Test vectorisé : renvoie un masque booléen des AABB (N,3) visibles."""
    mins = np.atleast_2d(mins)
    maxs = np.atleast_2d(maxs)
    visible = np.ones(len(mins), dtype=bool)
    for p in planes:
        # sommet positif (le plus loin dans la direction de la normale)
        px = np.where(p[0] >= 0, maxs[:, 0], mins[:, 0])
        py = np.where(p[1] >= 0, maxs[:, 1], mins[:, 1])
        pz = np.where(p[2] >= 0, maxs[:, 2], mins[:, 2])
        visible &= (p[0] * px + p[1] * py + p[2] * pz + p[3]) >= 0
    return visible


def project(vp, point, width, height):
    """Projette un point monde à l'écran. Renvoie (x, y, devant_camera)."""
    p = vp @ np.array([point[0], point[1], point[2], 1.0])
    if p[3] <= 1e-4:
        ndc = p[:3] / max(abs(p[3]), 1e-4)
        return (width * 0.5 * (1 - ndc[0]), height * 0.5 * (1 + ndc[1]), False)
    ndc = p[:3] / p[3]
    return (width * 0.5 * (ndc[0] + 1), height * 0.5 * (1 - ndc[1]), True)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)
