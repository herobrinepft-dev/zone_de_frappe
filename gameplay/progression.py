"""Profil du joueur : crédits, expérience, déblocages, cosmétiques et statistiques."""
import json
import copy

from engine.resources import CONFIG
from gameplay.data import WEAPONS, UPGRADES, level_from_xp

PROFILE_FILE = CONFIG / "profile.json"

DEFAULT_PROFILE = {
    "xp": 0,
    "credits": 500,
    "owned_weapons": ["pulsar"],
    "weapon": "pulsar",
    "upgrades": {w: {u: 0 for u in UPGRADES} for w in WEAPONS},
    "owned_finishes": ["graphite"],
    "finish": "graphite",
    "owned_beams": ["ambre", "cyan"],
    "beam": "ambre",
    "operation": "midi",
    "difficulty": "Vétéran",
    "stats": {
        "games": 0, "victories": 0, "drones": 0, "shots": 0, "hits": 0, "best_score": 0, "best_wave": 0,
        "time_played": 0.0, "distance": 0.0, "damage_taken": 0.0, "data_cores": 0, "beacons": 0,
        "kills_by_type": {"eclaireur": 0, "sentinelle": 0, "blinde": 0},
    },
    "last_result": None,
}


class Profile:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULT_PROFILE)
        self.load()

    def load(self):
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self._merge(self.data, saved)
        except (OSError, ValueError):
            pass

    def _merge(self, base, saved):
        for k, v in saved.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._merge(base[k], v)
            else:
                base[k] = v

    def save(self):
        try:
            CONFIG.mkdir(parents=True, exist_ok=True)
            with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    # ------------------------------------------------------------------
    @property
    def level(self):
        return level_from_xp(self.data["xp"])[0]

    @property
    def level_progress(self):
        return level_from_xp(self.data["xp"])[1]

    def can_afford(self, cost):
        return self.data["credits"] >= cost

    def spend(self, cost):
        if self.data["credits"] < cost:
            return False
        self.data["credits"] -= cost
        self.save()
        return True

    def weapon_stats(self, wid):
        w = dict(WEAPONS[wid])
        up = self.data["upgrades"].get(wid, {})
        w["damage"] *= 1.0 + 0.10 * up.get("puissance", 0)
        w["rate"] *= 1.0 + 0.08 * up.get("cadence", 0)
        w["cool"] *= 1.0 + 0.18 * up.get("refroidissement", 0)
        return w

    def record_game(self, result):
        s = self.data["stats"]
        s["games"] += 1
        s["victories"] += 1 if result["victory"] else 0
        s["drones"] += result["kills"]
        s["shots"] += result["shots"]
        s["hits"] += result["hits"]
        s["best_score"] = max(s["best_score"], result["score"])
        s["best_wave"] = max(s["best_wave"], result["wave"])
        s["time_played"] += result["time"]
        s["distance"] += result["distance"]
        s["damage_taken"] += result["damage_taken"]
        s["data_cores"] += result["data_cores"]
        s["beacons"] += result["beacons"]
        for k, v in result["kills_by_type"].items():
            s["kills_by_type"][k] = s["kills_by_type"].get(k, 0) + v
        old_level = self.level
        self.data["xp"] += result["xp"]
        self.data["credits"] += result["credits"]
        result["level_up"] = self.level > old_level
        result["new_level"] = self.level
        self.data["last_result"] = {k: v for k, v in result.items() if k != "kills_by_type"}
        self.save()
        return result
