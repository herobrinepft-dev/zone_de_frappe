"""Régénère toutes les ressources du jeu (textures PBR, modèles OBJ, sons et musiques).

Usage : python tools/generate_assets.py [--force]
  --force : supprime les fichiers existants avant de les recréer.
Le jeu génère automatiquement les ressources manquantes au premier lancement ;
ce script sert à les reconstruire après une modification des générateurs.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import pygame  # noqa: E402

from engine.resources import TEX_DIR, AUDIO_DIR, MODEL_DIR  # noqa: E402
from graphics import textures, models  # noqa: E402
from audio import synth  # noqa: E402


def main():
    force = "--force" in sys.argv
    pygame.init()
    if force:
        for d in (TEX_DIR, AUDIO_DIR, MODEL_DIR):
            if d.exists():
                for f in d.iterdir():
                    if f.suffix in (".png", ".wav", ".obj"):
                        f.unlink()
    t = time.time()
    textures.load_all(512, lambda f, m: print(f"\r{m:<40} {f:4.0%}", end=""))
    print(f"\nTextures : {time.time() - t:.1f} s")
    t = time.time()
    for n in models.all_names():
        models.get(n)
    print(f"Modèles OBJ : {time.time() - t:.1f} s")
    t = time.time()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for name, fn in synth.CATALOG.items():
        p = AUDIO_DIR / f"{name}.wav"
        if not p.exists():
            synth.write_wav(p, fn())
        print(f"\rAudio : {name:<20}", end="")
    print(f"\nAudio : {time.time() - t:.1f} s")
    print("Ressources prêtes.")


if __name__ == "__main__":
    main()
