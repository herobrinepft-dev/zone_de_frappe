"""Paramètres utilisateur persistants et préréglages de qualité graphique."""
import json
import copy
from engine.resources import CONFIG

SETTINGS_FILE = CONFIG / "user_settings.json"

QUALITY_LEVELS = ["Bas", "Moyen", "Élevé", "Ultra"]

QUALITY_PRESETS = {
    "Bas": dict(shadow_size=1024, shadow_radius=70, tex_size=256, bloom=False, volumetric_steps=0,
                fxaa=False, particles=700, view_distance=320, anisotropy=2, pcf=1, clouds=False,
                render_scale=0.85, lights=8),
    "Moyen": dict(shadow_size=2048, shadow_radius=95, tex_size=512, bloom=True, volumetric_steps=0,
                  fxaa=True, particles=1600, view_distance=420, anisotropy=4, pcf=1, clouds=True,
                  render_scale=1.0, lights=12),
    "Élevé": dict(shadow_size=2048, shadow_radius=120, tex_size=512, bloom=True, volumetric_steps=14,
                  fxaa=True, particles=3000, view_distance=600, anisotropy=8, pcf=2, clouds=True,
                  render_scale=1.0, lights=20),
    "Ultra": dict(shadow_size=4096, shadow_radius=150, tex_size=512, bloom=True, volumetric_steps=28,
                  fxaa=True, particles=4500, view_distance=900, anisotropy=16, pcf=2, clouds=True,
                  render_scale=1.0, lights=24),
}

RESOLUTIONS = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160)]

DEFAULTS = {
    "resolution": [1600, 900],
    "fullscreen": False,
    "vsync": True,
    "quality": "Élevé",
    "fov": 80,
    "sensitivity": 1.0,
    "invert_y": False,
    "head_bob": True,
    "master_volume": 0.8,
    "music_volume": 0.55,
    "sfx_volume": 0.9,
    "weather_effects": True,
    "show_fps": True,
    "brightness": 1.0,
}


class Settings:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in self.data:
                    self.data[k] = v
            if self.data["quality"] not in QUALITY_PRESETS:
                self.data["quality"] = DEFAULTS["quality"]
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            CONFIG.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v

    @property
    def preset(self):
        return QUALITY_PRESETS[self.data["quality"]]
