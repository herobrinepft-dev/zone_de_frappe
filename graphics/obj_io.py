"""Lecture/écriture OBJ (avec couleurs de sommets « v x y z r g b » et groupes usemtl = matériau)."""
import numpy as np
from graphics.materials import MATERIALS, L


def save_obj(arr, path, name="model"):
    lines = [f"# ZONE DE FRAPPE - modèle {name}", "# Généré procéduralement - licence CC0", f"o {name}"]
    pos, nrm, uv, layer, colr = arr[:, 0:3], arr[:, 3:6], arr[:, 6:8], arr[:, 8], arr[:, 9:12]
    for p, c in zip(pos, colr):
        lines.append(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f} {c[0]:.4f} {c[1]:.4f} {c[2]:.4f}")
    for t in uv:
        lines.append(f"vt {t[0]:.5f} {t[1]:.5f}")
    for n in nrm:
        lines.append(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}")
    cur = None
    for f in range(len(arr) // 3):
        lay = int(round(layer[f * 3]))
        if lay != cur:
            cur = lay
            lines.append(f"usemtl {MATERIALS[lay][0]}")
        i = f * 3 + 1
        lines.append(f"f {i}/{i}/{i} {i + 1}/{i + 1}/{i + 1} {i + 2}/{i + 2}/{i + 2}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_obj(path):
    """Charge un OBJ triangulé ou à polygones convexes. Les matériaux inconnus -> 'paint'."""
    V, C, T, N = [], [], [], []
    rows = []
    layer = L["paint"]
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            tag = parts[0]
            if tag == "v":
                V.append([float(x) for x in parts[1:4]])
                C.append([float(x) for x in parts[4:7]] if len(parts) >= 7 else [1.0, 1.0, 1.0])
            elif tag == "vt":
                T.append([float(parts[1]), float(parts[2]) if len(parts) > 2 else 0.0])
            elif tag == "vn":
                N.append([float(x) for x in parts[1:4]])
            elif tag == "usemtl":
                layer = L.get(parts[1], L["paint"])
            elif tag == "f":
                idx = []
                for p in parts[1:]:
                    s = p.split("/")
                    vi = int(s[0])
                    ti = int(s[1]) if len(s) > 1 and s[1] else 0
                    ni = int(s[2]) if len(s) > 2 and s[2] else 0
                    idx.append((vi, ti, ni))
                for k in range(1, len(idx) - 1):
                    for (vi, ti, ni) in (idx[0], idx[k], idx[k + 1]):
                        rows.append((vi, ti, ni, layer))
    V, C = np.array(V, np.float32), np.array(C, np.float32)
    T = np.array(T, np.float32) if T else np.zeros((1, 2), np.float32)
    N = np.array(N, np.float32) if N else None
    out = np.zeros((len(rows), 12), np.float32)
    for i, (vi, ti, ni, lay) in enumerate(rows):
        vi = vi - 1 if vi > 0 else len(V) + vi
        out[i, 0:3] = V[vi]
        out[i, 9:12] = C[vi]
        if ti:
            out[i, 6:8] = T[ti - 1 if ti > 0 else len(T) + ti]
        if N is not None and ni:
            out[i, 3:6] = N[ni - 1 if ni > 0 else len(N) + ni]
        out[i, 8] = lay
    if N is None:
        tri = out[:, 0:3].reshape(-1, 3, 3)
        fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
        out[:, 3:6] = np.repeat(fn, 3, axis=0)
    return out
