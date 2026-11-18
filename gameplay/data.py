"""Données de conception : équipements fictifs, améliorations, cosmétiques, opérations."""

WEAPONS = {
    "pulsar": dict(
        name="PULSAR MK-II", role="Émetteur polyvalent",
        desc="Émetteur d'impulsions à cadence élevée. Fiable et précis à moyenne portée.",
        damage=20.0, rate=8.0, spread=0.010, range=170.0, heat=0.055, cool=0.55, pellets=1, auto=True,
        zoom=1.35, recoil=0.010, price=0, level=1, beam_width=0.03,
        offset=(0.15, -0.15, -0.42), ads_offset=(0.0, -0.096, -0.34)),
    "faucon": dict(
        name="FAUCON LR-7", role="Émetteur longue portée",
        desc="Décharges lourdes et précises. Lunette intégrée, idéal contre les unités blindées.",
        damage=95.0, rate=1.4, spread=0.0015, range=320.0, heat=0.26, cool=0.5, pellets=1, auto=False,
        zoom=3.2, recoil=0.05, price=2500, level=3, beam_width=0.05,
        offset=(0.14, -0.15, -0.40), ads_offset=(0.0, -0.1, -0.3)),
    "tempete": dict(
        name="TEMPÊTE SG-4", role="Émetteur à dispersion",
        desc="Salve de 9 impulsions en cône. Dévastateur au contact des essaims d'éclaireurs.",
        damage=13.0, rate=1.9, spread=0.055, range=70.0, heat=0.2, cool=0.6, pellets=9, auto=False,
        zoom=1.2, recoil=0.06, price=4000, level=5, beam_width=0.025,
        offset=(0.15, -0.15, -0.40), ads_offset=(0.0, -0.092, -0.32)),
}
WEAPON_ORDER = ["pulsar", "faucon", "tempete"]

UPGRADES = {
    "puissance": dict(name="PUISSANCE", desc="+10 % dégâts / niv.", costs=[600, 1300, 2400]),
    "cadence": dict(name="CADENCE", desc="+8 % cadence / niv.", costs=[500, 1100, 2100]),
    "refroidissement": dict(name="REFROIDISSEMENT", desc="+18 % dissipation / niv.", costs=[450, 1000, 1900]),
}

FINISHES = [
    ("graphite", "Graphite", (0.16, 0.17, 0.19), 0),
    ("sable", "Sable", (0.62, 0.52, 0.36), 400),
    ("arctique", "Arctique", (0.86, 0.88, 0.9), 700),
    ("foret", "Forêt", (0.2, 0.3, 0.18), 700),
    ("cobalt", "Cobalt", (0.1, 0.2, 0.55), 1100),
    ("braise", "Braise", (0.55, 0.12, 0.06), 1400),
    ("or", "Or royal", (0.85, 0.62, 0.2), 3000),
]

BEAMS = [
    ("ambre", "Ambre", (1.0, 0.55, 0.12), 0),
    ("cyan", "Cyan", (0.15, 0.75, 1.0), 0),
    ("emeraude", "Émeraude", (0.2, 1.0, 0.4), 500),
    ("magenta", "Magenta", (1.0, 0.2, 0.75), 800),
    ("blanc", "Blanc pur", (1.0, 0.95, 0.9), 1500),
]

OPERATIONS = [
    dict(id="aube", name="AUBE GRISE", hour=6.3, clouds=0.55, fog=0.006, rain=0.0, level=1,
         desc="Brume matinale sur le centre-ville. Visibilité réduite, drones furtifs.",
         weather="Brouillard", time="06:20"),
    dict(id="midi", name="MIDI ÉCLATANT", hour=12.8, clouds=0.25, fog=0.0012, rain=0.0, level=1,
         desc="Plein soleil, ciel dégagé. L'opération de référence du programme.",
         weather="Dégagé", time="12:50"),
    dict(id="orage", name="CRÉPUSCULE D'ORAGE", hour=18.3, clouds=0.9, fog=0.003, rain=1.0, level=2,
         desc="Pluie battante et éclairs. Chaussées détrempées, reflets partout.",
         weather="Orage", time="18:20"),
    dict(id="nuit", name="NUIT BLANCHE", hour=22.6, clouds=0.2, fog=0.0018, rain=0.0, level=4,
         desc="Ville illuminée sous les étoiles. Repérez les drones à leurs feux.",
         weather="Nuit claire", time="22:40"),
]

DIFFICULTIES = {
    "Recrue": dict(damage=0.55, health=0.8, count=0.8, score=0.75, desc="Pour découvrir le programme."),
    "Vétéran": dict(damage=1.0, health=1.0, count=1.0, score=1.0, desc="L'équilibre prévu par les instructeurs."),
    "Élite": dict(damage=1.45, health=1.3, count=1.25, score=1.6, desc="Drones agressifs et résistants."),
}
DIFFICULTY_ORDER = ["Recrue", "Vétéran", "Élite"]

DRONES = {
    "eclaireur": dict(name="ÉCLAIREUR", hp=45.0, speed=13.0, radius=0.75, score=100, alt=(6, 12),
                      fire_range=55.0, fire_rate=1.1, burst=3, damage=4.0, proj_speed=38.0, pref_dist=18.0,
                      color=(1.0, 0.25, 0.1), scale=1.0),
    "sentinelle": dict(name="SENTINELLE", hp=110.0, speed=7.5, radius=1.0, score=200, alt=(9, 18),
                       fire_range=75.0, fire_rate=0.55, burst=2, damage=9.0, proj_speed=26.0, pref_dist=32.0,
                       color=(0.2, 0.7, 1.0), scale=1.0),
    "blinde": dict(name="BLINDÉ", hp=420.0, speed=4.5, radius=1.5, score=500, alt=(10, 16),
                   fire_range=85.0, fire_rate=0.35, burst=1, damage=22.0, proj_speed=20.0, pref_dist=38.0,
                   color=(1.0, 0.75, 0.15), scale=1.0, splash=4.0),
}

TOTAL_WAVES = 10

# Mission par vague : élimination, défense de balise, collecte de données
WAVE_PLAN = [
    dict(mission="elimination", mix={"eclaireur": 5}),
    dict(mission="elimination", mix={"eclaireur": 6, "sentinelle": 2}),
    dict(mission="defense", mix={"eclaireur": 6, "sentinelle": 3}),
    dict(mission="collecte", mix={"eclaireur": 7, "sentinelle": 3}),
    dict(mission="elimination", mix={"eclaireur": 6, "sentinelle": 3, "blinde": 1}),
    dict(mission="defense", mix={"eclaireur": 8, "sentinelle": 4, "blinde": 1}),
    dict(mission="collecte", mix={"eclaireur": 8, "sentinelle": 5, "blinde": 1}),
    dict(mission="elimination", mix={"eclaireur": 10, "sentinelle": 5, "blinde": 2}),
    dict(mission="defense", mix={"eclaireur": 10, "sentinelle": 6, "blinde": 2}),
    dict(mission="elimination", mix={"eclaireur": 12, "sentinelle": 7, "blinde": 3}),
]

MISSION_TEXT = {
    "elimination": "Neutraliser tous les drones de la vague",
    "defense": "Capturer la balise et tenir la zone",
    "collecte": "Récupérer les modules de données",
}


def level_from_xp(xp):
    """Niveau et progression (0..1) vers le suivant."""
    lvl = 1
    need = 1500
    while xp >= need:
        xp -= need
        lvl += 1
        need = int(1500 * lvl ** 1.25)
    return lvl, xp / need, need
