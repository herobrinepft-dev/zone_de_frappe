"""Chemins du projet et chargement des sources de shaders (avec #include)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SHADERS = ROOT / "shaders"
# dossier des fichiers utilisateur (réglages, profil) — redirigeable pour les tests
CONFIG = Path(os.environ.get("ZDF_CONFIG_DIR", str(ROOT / "config")))
TEX_DIR = ASSETS / "textures"
AUDIO_DIR = ASSETS / "audio"
MODEL_DIR = ASSETS / "models"


def load_shader_source(name, defines=()):
    """Charge un shader GLSL, résout les lignes `#include "fichier"` et injecte des #define."""
    src = (SHADERS / name).read_text(encoding="utf-8")
    lines = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#include"):
            inc = stripped.split('"')[1]
            lines.append((SHADERS / inc).read_text(encoding="utf-8"))
        else:
            lines.append(line)
    if defines:
        # les #define doivent suivre immédiatement la ligne #version
        for i, l in enumerate(lines):
            if l.strip().startswith("#version"):
                for d in reversed(defines):
                    lines.insert(i + 1, f"#define {d}")
                break
    return "\n".join(lines)
