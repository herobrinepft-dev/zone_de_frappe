"""Table des matériaux : indices de couche dans les texture arrays + paramètres PBR.

Drapeaux (bits) :
  1  = découpe alpha (feuillages, herbe)
  2  = animé par le vent
  4  = teintable (couleur cosmétique dynamique)
  8  = surface mouillable (pluie : flaques, reflets)
  16 = façade : alpha = masque des vitres (reflets + fenêtres allumées la nuit)
  32 = émissif : alpha = masque d'émission
"""

CUTOUT, WIND, TINT, WET, WINDOWS, EMISSIVE = 1, 2, 4, 8, 16, 32

# nom : (rugosité, métal, émission, drapeaux)
MATERIALS = [
    ("road",        0.82, 0.0, 0.0, WET),
    ("asphalt",     0.85, 0.0, 0.0, WET),
    ("crosswalk",   0.80, 0.0, 0.0, WET),
    ("sidewalk",    0.80, 0.0, 0.0, WET),
    ("concrete",    0.88, 0.0, 0.0, WET),
    ("brick",       0.85, 0.0, 0.0, WINDOWS),
    ("glass_tower", 0.30, 0.6, 0.0, WINDOWS),
    ("panel",       0.75, 0.0, 0.0, WINDOWS),
    ("dark_panel",  0.45, 0.5, 0.0, WINDOWS),
    ("storefront",  0.60, 0.0, 0.0, WINDOWS),
    ("roof",        0.95, 0.0, 0.0, WET),
    ("grass",       0.92, 0.0, 0.0, 0),
    ("bark",        0.90, 0.0, 0.0, 0),
    ("leaves",      0.75, 0.0, 0.0, CUTOUT | WIND),
    ("paint",       0.30, 0.0, 0.0, TINT),
    ("brushed",     0.28, 1.0, 0.0, 0),
    ("drone_shell", 0.38, 0.1, 0.0, TINT),
    ("emissive",    0.50, 0.0, 6.0, EMISSIVE),
    ("glass",       0.04, 0.0, 0.0, 0),
    ("rubber",      0.92, 0.0, 0.0, 0),
    ("wood",        0.78, 0.0, 0.0, 0),
    ("dirt",        0.95, 0.0, 0.0, WET),
    ("hazard",      0.70, 0.0, 0.0, 0),
    ("grass_blades", 0.85, 0.0, 0.0, CUTOUT | WIND),
    ("container",   0.55, 0.3, 0.0, 0),
    ("plaza",       0.70, 0.0, 0.0, WET),
    ("awning",      0.85, 0.0, 0.0, 0),
    ("polymer",     0.55, 0.0, 0.0, 0),
    ("hologram",    0.30, 0.0, 3.0, EMISSIVE),
]

NUM_LAYERS = len(MATERIALS)
MAX_LAYERS = 32
L = {m[0]: i for i, m in enumerate(MATERIALS)}


def material_arrays():
    import numpy as np
    rough = np.zeros(MAX_LAYERS, "f4")
    metal = np.zeros(MAX_LAYERS, "f4")
    emis = np.zeros(MAX_LAYERS, "f4")
    flags = np.zeros(MAX_LAYERS, "f4")
    for i, (_, r, m, e, f) in enumerate(MATERIALS):
        rough[i], metal[i], emis[i], flags[i] = r, m, e, f
    return rough, metal, emis, flags
