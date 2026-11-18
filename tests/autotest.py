"""Test automatique de bout en bout du jeu réel (python main.py --autotest).

Pilote l'application comme un joueur : clics sur les vrais boutons (événements
pygame), touches virtuelles, mouvements de souris. Vérifie :
  - démarrage, compilation des shaders, scène 3D réellement visible ;
  - interface transparente ne masquant pas la scène (comparaison exacte avant/après interface) ;
  - menu : toutes les rubriques et leurs boutons ;
  - contrôles (déplacement, sprint, saut, gravité, vue), collisions ;
  - tir, drones, vagues, pause, redimensionnement, niveaux de qualité, fin de partie.
"""
import json
import math
import time
from pathlib import Path

import numpy as np
import pygame

from engine.resources import ROOT


class TestFailure(Exception):
    pass


class AutoPilot:
    def __init__(self, out_dir=None):
        self.out = Path(out_dir) if out_dir else ROOT / "tests" / "output"
        self.out.mkdir(parents=True, exist_ok=True)
        self.results = []
        self.gen = None
        self.wait = 0.0
        self.pending_shot = None
        self.shots = {}
        self.exit_code = 0
        self.t0 = time.time()
        self.frame_times = []

    # ------------------------------------------------------------------
    def check(self, name, cond, detail=""):
        self.results.append({"test": name, "ok": bool(cond), "detail": detail})
        print(f"  [{'OK ' if cond else 'ÉCHEC'}] {name}  {detail}")

    def shot(self, name):
        self.pending_shot = name

    def click(self, widget):
        pos = widget.rect.center
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos, autotest=True))
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos, autotest=True))

    def key(self, k):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0, autotest=True))
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=k, mod=0, unicode="", scancode=0, autotest=True))

    # ------------------------------------------------------------------
    def step(self, app, dt):
        if self.gen is None:
            self.gen = self.script(app)
        self.frame_times.append(dt)
        self.wait -= dt
        if self.wait > 0:
            return
        try:
            w = next(self.gen)
            self.wait = w or 0.0
        except StopIteration:
            self.finish(app)
        except Exception as e:  # erreur inattendue = échec
            import traceback
            traceback.print_exc()
            self.check("exécution du scénario", False, repr(e))
            self.finish(app)

    def after_render(self, app):
        if self.pending_shot:
            name = self.pending_shot
            self.pending_shot = None
            w, h = app.size
            final = np.frombuffer(app.renderer.read_final(), np.uint8).reshape(h, w, 3)
            pre = app.renderer.pre_overlay
            pre = np.frombuffer(pre, np.uint8).reshape(h, w, 3) if pre is not None else None
            self.shots[name] = (final[::-1].copy(), None if pre is None else pre[::-1].copy())
            img = pygame.image.frombuffer(final[::-1].tobytes(), (w, h), "RGB")
            pygame.image.save(img, str(self.out / f"{name}.png"))

    def finish(self, app):
        ok = sum(r["ok"] for r in self.results)
        n = len(self.results)
        self.exit_code = 0 if ok == n else 1
        ft = np.array(self.frame_times[30:]) if len(self.frame_times) > 30 else np.array(self.frame_times)
        report = {"passed": ok, "total": n, "duration_s": round(time.time() - self.t0, 1),
                  "avg_fps": round(float(1.0 / max(ft.mean(), 1e-6)), 1) if len(ft) else 0,
                  "load_time_s": round(getattr(app, "load_time", 0), 1), "results": self.results}
        (self.out / "rapport_tests.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n=== RÉSULTAT : {ok}/{n} tests réussis — FPS moyen {report['avg_fps']} ===")
        app.running = False

    # ------------------------------------------------------------------
    def analyse(self, name, max_ui_cover):
        """Vérifie que la scène 3D est visible et que l'interface ne la masque pas."""
        final, pre = self.shots[name]
        lum = pre.mean(axis=2) / 255.0 if pre is not None else final.mean(axis=2) / 255.0
        visible = lum.mean() > 0.04 and lum.std() > 0.03
        self.check(f"{name} : scène 3D visible", visible, f"lum. moy={lum.mean():.3f} écart={lum.std():.3f}")
        if pre is not None:
            diff = np.abs(final.astype(np.int16) - pre.astype(np.int16)).max(axis=2)
            covered = float((diff > 24).mean())
            self.check(f"{name} : interface transparente (couverture {covered:.0%} ≤ {max_ui_cover:.0%})",
                       covered <= max_ui_cover, f"couverture={covered:.3f}")
            # la zone centrale (hors réticule) doit rester visible
            h, w = diff.shape
            core = diff[int(h * 0.38):int(h * 0.62), int(w * 0.3):int(w * 0.45)]
            return covered, float((core > 24).mean())
        return None, None

    def find_clear_lane(self, app, length):
        """Cherche un point de départ et un cap sans obstacle sur `length` mètres."""
        w = app.world
        for (x, z) in app.city.intersections:
            for yaw in (0.0, math.pi / 2, math.pi, -math.pi / 2):
                d = np.array([math.sin(yaw), 0.0, -math.cos(yaw)])
                ok = True
                for h in (0.3, 1.0, 1.6):
                    for off in (-0.4, 0.0, 0.4):
                        side = np.array([-d[2], 0.0, d[0]]) * off
                        o = np.array([x, h, z]) + side
                        t, _ = w.raycast(o, d, length + 2.0, ground=False)
                        if t is not None:
                            ok = False
                if ok and abs(x) < w.half - length and abs(z) < w.half - length:
                    return (x, 0.0, z), yaw
        return None

    # ------------------------------------------------------------------
    def script(self, app):
        from ui.menu import MenuState, PAGES
        from gameplay.game_state import GameState
        print("\n=== ZONE DE FRAPPE — TEST AUTOMATIQUE ===")
        app.renderer.capture_before_overlay = True
        self.check("démarrage et chargement", True, f"{app.load_time:.1f} s")
        self.check("shaders compilés", app.renderer.prog_lit is not None and app.renderer.prog_composite is not None)
        yield 2.0
        menu = app.state
        self.check("état initial = menu principal", isinstance(menu, MenuState))
        self.shot("01_menu_accueil")
        yield 0.1
        self.analyse("01_menu_accueil", 0.75)

        # --- navigation : clic réel sur chaque bouton du menu ----------------
        for i, name in enumerate(PAGES):
            if name == "QUITTER":
                continue
            self.click(menu.nav[i])
            yield 0.6
            self.check(f"menu : bouton {name}", menu.page == i, f"page={PAGES[menu.page]}")
            fname = f"02_menu_{i}_{name.lower().replace('è', 'e').replace('é', 'e').replace('é', 'e')}"
            self.shot(fname)
            yield 0.1
            if name == "ARMURERIE":
                self.analyse(fname, 0.85)
            # interactions spécifiques
            if name == "ARMURERIE":
                cards = [w for w in menu.page_widgets if hasattr(w, "wid")]
                self.click(cards[1])
                yield 0.3
                self.check("armurerie : sélection d'un émetteur", menu.armory_sel == "faucon")
                yield 0.6
                self.shot("02_menu_armurerie_faucon")
                yield 0.1
                credits = app.profile.data["credits"]
                sw = [w for w in menu.page_widgets if hasattr(w, "swatch") and not hasattr(w, "beam")]
                self.click(sw[1])
                yield 0.3
                ok = "sable" in app.profile.data["owned_finishes"] and app.profile.data["credits"] < credits
                self.check("armurerie : achat d'une finition (crédits débités)", ok,
                           f"crédits {credits} -> {app.profile.data['credits']}")
                bw = [w for w in menu.page_widgets if hasattr(w, "beam")]
                self.click(bw[1])
                yield 0.3
                self.check("armurerie : couleur de faisceau", app.profile.data["beam"] == "cyan")
                cards = [w for w in menu.page_widgets if hasattr(w, "wid")]
                self.click(cards[0])
                yield 0.3
            if name == "OPÉRATIONS":
                cards = [w for w in menu.page_widgets if hasattr(w, "op")]
                self.click(cards[2])     # orage (verrouillé niveau 2)
                yield 0.3
                self.check("opérations : verrouillage par niveau", app.profile.data["operation"] == "midi")
                self.click(cards[0])
                yield 0.3
                self.check("opérations : sélection", app.profile.data["operation"] == "aube")
                cards = [w for w in menu.page_widgets if hasattr(w, "op")]
                self.click(cards[1])
                yield 0.3
                diff = [w for w in menu.page_widgets if not hasattr(w, "op")]
                self.click(diff[0])
                yield 0.3
                self.check("opérations : difficulté", app.profile.data["difficulty"] == "Recrue")
                diff = [w for w in menu.page_widgets if not hasattr(w, "op")]
                self.click(diff[1])
                yield 0.3
            if name == "PARAMÈTRES":
                sp = menu.settings_panel
                for ti in (1, 2, 0):
                    self.click(sp.tab_buttons[ti])
                    yield 0.3
                    self.check(f"paramètres : onglet {ti}", sp.tab == ti)
                from ui.widgets import Toggle
                tg = [w for w in sp.widgets if isinstance(w, Toggle) and "FPS" in w.label][0]
                before = app.settings["show_fps"]
                self.click(tg)
                yield 0.2
                self.check("paramètres : interrupteur", app.settings["show_fps"] != before)
                self.click([w for w in sp.widgets if isinstance(w, Toggle) and "FPS" in w.label][0])
                yield 0.2
        # QUITTER : confirmation puis annulation
        self.click(menu.nav[PAGES.index("QUITTER")])
        yield 0.4
        self.check("menu : QUITTER ouvre la confirmation", menu.confirm_quit)
        self.shot("03_menu_quitter")
        yield 0.1
        self.click(menu.page_widgets[1])
        yield 0.4
        self.check("menu : ANNULER ferme la confirmation", not menu.confirm_quit)

        # --- lancement de la partie via le bouton DÉPLOYER ---------------
        self.click(menu.nav[0])
        yield 0.5
        deploy = [w for w in menu.page_widgets if getattr(w, "label", "") == "DÉPLOYER"][0]
        self.click(deploy)
        yield 2.0
        gs = app.state
        self.check("DÉPLOYER lance la partie", isinstance(gs, GameState))
        s = gs.session
        p = s.player
        yield 1.0
        self.shot("04_jeu_depart")
        yield 0.1
        cov, core = self.analyse("04_jeu_depart", 0.30)
        self.check("HUD : centre de l'écran dégagé", core is not None and core < 0.05, f"{core}")
        self.check("joueur au sol au départ", p.on_ground, f"y={p.pos[1]:.2f}")

        # --- contrôles -------------------------------------------------------
        # trajectoire dégagée sur 25 m (vérifiée par rayons à hauteur de genou et de torse)
        lane = self.find_clear_lane(app, 25.0)
        self.check("test : trajectoire dégagée trouvée", lane is not None)
        (lx, ly, lz), yaw = lane
        gs.cam.yaw = yaw
        gs.cam.pitch = 0.0
        p.pos[:] = (lx, ly, lz)
        p.vel[:] = 0
        yield 0.3
        fdir = np.array([math.sin(yaw), 0.0, -math.cos(yaw)])
        start = p.pos.copy()
        app.virtual_keys = {"forward"}
        yield 1.0
        app.virtual_keys = set()
        dist = float(np.dot(p.pos - start, fdir))
        self.check("contrôles : avancer (Z/W)", dist > 3.0, f"{dist:.2f} m en 1 s")
        yield 0.3
        p.pos[:] = (lx, ly, lz)
        p.vel[:] = 0
        yield 0.2
        start = p.pos.copy()
        app.virtual_keys = {"forward", "sprint"}
        yield 1.0
        app.virtual_keys = set()
        dsp = float(np.dot(p.pos - start, fdir))
        self.check("contrôles : sprint plus rapide que la course", dsp > dist * 1.25, f"{dsp:.2f} m vs {dist:.2f} m")
        yield 0.4
        # pas latéral : on se tourne de 90° vers la gauche, la droite pointe alors le long du couloir dégagé
        p.pos[:] = (lx, ly, lz)
        p.vel[:] = 0
        gs.cam.yaw = yaw - math.pi / 2
        yield 0.2
        start = p.pos.copy()
        app.virtual_keys = {"right"}
        yield 0.6
        app.virtual_keys = set()
        dl = float(np.dot(p.pos - start, fdir))
        self.check("contrôles : pas latéral (D)", dl > 1.5, f"{dl:.2f} m")
        gs.cam.yaw = yaw
        yield 0.3
        y0 = p.pos[1]
        app.virtual_keys = {"jump"}
        yield 0.05
        app.virtual_keys = set()
        peak = y0
        for _ in range(20):
            yield 0.02
            peak = max(peak, p.pos[1])
        self.check("contrôles : saut", peak - y0 > 0.8, f"hauteur {peak - y0:.2f} m")
        yield 0.8
        self.check("gravité : retour au sol", p.on_ground and abs(p.pos[1] - y0) < 0.2, f"y={p.pos[1]:.2f}")
        yaw0 = gs.cam.yaw
        app.virtual_look = (300.0, 0.0)
        yield 0.1
        self.check("contrôles : rotation de la vue (souris)", abs(gs.cam.yaw - yaw0) > 0.3,
                   f"Δlacet={gs.cam.yaw - yaw0:.2f} rad")
        app.virtual_look = (0.0, 120.0)
        yield 0.1
        self.check("contrôles : tangage de la vue", gs.cam.pitch < -0.1, f"tangage={gs.cam.pitch:.2f}")
        gs.cam.pitch = 0.0
        app.virtual_keys = {"crouch"}
        yield 0.5
        self.check("contrôles : accroupi", p.height < 1.4, f"hauteur={p.height:.2f}")
        app.virtual_keys = set()
        yield 0.5

        # --- collisions : on fonce dans un immeuble -----------------------
        b = app.city.buildings[0]
        x0, z0, x1, z1, top = b
        cx = (x0 + x1) / 2
        p.pos[:] = (cx, 0.15, z1 + 3.5)
        p.vel[:] = 0
        gs.cam.yaw = 0.0   # regarde vers -Z, donc vers la façade sud
        gs.cam.pitch = 0.0
        yield 0.2
        app.virtual_keys = {"forward", "sprint"}
        yield 2.0
        app.virtual_keys = set()
        inside = app.world.inside_any(p.center, -0.05)
        self.check("collisions : impossible de traverser un immeuble", p.pos[2] > z1 and not inside,
                   f"z={p.pos[2]:.2f} façade={z1:.2f}")
        self.shot("05_collision_mur")
        yield 0.1
        # glissement le long du mur
        x_before = p.pos[0]
        app.virtual_keys = {"forward", "right"}
        yield 0.8
        app.virtual_keys = set()
        self.check("collisions : glissement le long du mur", p.pos[0] - x_before > 1.0 and p.pos[2] > z1,
                   f"dx={p.pos[0] - x_before:.2f}")
        # montée de trottoir (marche) + chute depuis un toit
        p.pos[:] = (cx, top + 0.01, (z0 + z1) / 2)
        p.vel[:] = 0
        yield 0.5
        self.check("collisions : on tient debout sur un toit", abs(p.pos[1] - top) < 0.3 and p.on_ground,
                   f"y={p.pos[1]:.2f} toit={top:.2f}")
        p.pos[:] = app.city.player_spawn
        p.vel[:] = 0
        yield 0.5

        # --- tir sur un drone ----------------------------------------------
        from entities.drone import Drone
        cam = gs.cam
        target = p.eye + np.array([0.0, 4.0, -16.0])
        d = Drone("sentinelle", target, s.difficulty, np.random.default_rng(1))
        d.arrival = 0.0
        d.fire_cd = 99.0
        d.update = lambda dt, sess, d=d: None   # immobile pour le test
        s.drones.append(d)
        hp0 = d.hp
        cam.look_at_point(d.pos)
        shots0 = s.stats["shots"]
        app.virtual_keys = {"fire", "aim"}
        for _ in range(12):
            cam.look_at_point(d.pos)
            yield 0.05
        self.shot("06_tir")
        for _ in range(30):
            cam.look_at_point(d.pos)
            yield 0.05
        app.virtual_keys = set()
        self.check("tir : des impulsions sont émises", s.stats["shots"] > shots0 + 3, f"{s.stats['shots'] - shots0} tirs")
        self.check("tir : le drone subit des dégâts", d.hp < hp0, f"PV {hp0:.0f} -> {d.hp:.0f}")
        self.check("tir : particules (faisceaux, étincelles)", s.particles.alive.sum() > 0 or not d.alive,
                   f"{int(s.particles.alive.sum())} particules")
        yield 0.1
        self.analyse("06_tir", 0.30)
        if d in s.drones:
            s.drones.remove(d)
        yield 0.5

        # --- vagues : apparition de drones et tirs ennemis ----------------
        s.waves.timer = 0.01
        yield 1.0
        self.check("vagues : la vague 1 démarre", s.waves.wave == 1 and s.waves.state == "active",
                   f"vague={s.waves.wave} état={s.waves.state}")
        seen_proj = False
        dmg0 = s.stats["damage_taken"]
        for i in range(200):   # jusqu'à 20 s : les drones apparaissent à plus de 70 m
            yield 0.1
            p.health = 100.0   # observation du comportement des drones : le joueur reste en vie
            if s.projectiles or s.stats["damage_taken"] > dmg0:
                seen_proj = True
            if seen_proj and i >= 60:
                break
        self.check("partie toujours en cours pendant l'observation", not s.over)
        self.check("drones : apparition", len(s.drones) > 0, f"{len(s.drones)} drones")
        alive = [d for d in s.drones if d.alive]
        if alive:
            cam.look_at_point(alive[0].pos)
        yield 0.2
        self.shot("07_combat")
        yield 0.1
        self.analyse("07_combat", 0.30)
        self.check("drones : tirs d'orbes ennemis", seen_proj or s.stats["damage_taken"] > dmg0,
                   f"dégâts reçus pendant l'observation : {s.stats['damage_taken'] - dmg0:.0f}")
        p.health = 100.0

        # --- mission DÉFENSE : capture de balise ---------------------------
        for d in s.drones:
            d.damage(1e6)
        yield 0.5
        s.waves.wave = 2
        s.waves.start_wave()
        self.check("mission défense : balise placée", s.waves.mission == "defense" and s.waves.beacon is not None)
        bx, by, bz = s.waves.beacon
        p.pos[:] = (bx + 2.0, by + 0.5, bz + 2.0)
        p.vel[:] = 0
        gs.cam.look_at_point(s.waves.beacon + np.array([0, 2.0, 0]))
        gs.cam.pitch = 0.0
        yield 0.8
        self.shot("07b_balise")
        p0 = s.waves.beacon_progress
        for _ in range(10):
            p.health = 100.0
            yield 0.3
        self.check("mission défense : progression de capture dans la zone", s.waves.beacon_progress > p0,
                   f"{p0:.2f} -> {s.waves.beacon_progress:.2f}")
        s.waves.beacon_progress = 0.999
        yield 0.5
        self.check("mission défense : balise capturée, vague terminée", s.waves.state == "intermission")

        # --- mission COLLECTE : modules de données ------------------------
        yield 0.5
        s.waves.wave = 3
        s.waves.start_wave()
        cores = list(s.waves.cores)
        self.check("mission collecte : modules placés", s.waves.mission == "collecte" and len(cores) == 3,
                   f"{len(cores)} modules")
        for c in cores:
            p.pos[:] = (c.base[0], c.base[1] + 0.3, c.base[2])
            p.vel[:] = 0
            p.health = 100.0
            yield 0.4
        self.check("mission collecte : modules ramassés", all(c.collected for c in cores))
        yield 0.5
        self.check("mission collecte : vague terminée", s.waves.state == "intermission")
        s.waves.timer = 999.0
        for d in s.drones:
            d.damage(1e6)
        p.pos[:] = app.city.player_spawn
        p.vel[:] = 0
        p.health = 100.0
        yield 1.0

        # --- pause --------------------------------------------------------------
        self.key(pygame.K_ESCAPE)
        yield 0.3
        self.check("pause : Échap ouvre le menu pause", gs.paused)
        self.shot("08_pause")
        yield 0.1
        self.analyse("08_pause", 0.999)
        self.click(gs.pause_widgets[1])
        yield 0.4
        self.check("pause : PARAMÈTRES", gs.pause_settings)
        self.click(gs.settings_back)
        yield 0.3
        self.click(gs.pause_widgets[0])
        yield 0.3
        self.check("pause : REPRENDRE", not gs.paused)

        # --- redimensionnement ------------------------------------------
        for (w, h) in ((1280, 720), (1024, 768), (1600, 900)):
            pygame.display.set_mode((w, h), pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
            app.on_resize((w, h))
            yield 0.4
            nm = f"09_resize_{w}x{h}"
            self.shot(nm)
            yield 0.1
            self.check(f"redimensionnement {w}x{h}", app.renderer.window_size == (w, h) and
                       self.shots[nm][0].shape[:2] == (h, w))
            self.analyse(nm, 0.30)

        # --- niveaux de qualité --------------------------------------------
        from config.settings import QUALITY_LEVELS
        for q in QUALITY_LEVELS:
            app.settings["quality"] = q
            app.apply_quality()
            t0 = len(self.frame_times)
            yield 1.0
            ft = np.array(self.frame_times[t0 + 5:])
            fps = 1.0 / ft.mean() if len(ft) else 0
            nm = f"10_qualite_{q.lower().replace('é', 'e')}"
            self.shot(nm)
            yield 0.1
            self.analyse(nm, 0.30)
            self.check(f"qualité {q} : fluidité", fps > 30, f"{fps:.0f} FPS")
        app.settings["quality"] = "Élevé"
        app.apply_quality()

        # --- fin de partie et écran de résultats --------------------------
        s.player_hit(500, p.pos + np.array([5, 0, 0]))
        yield 3.5
        self.check("défaite : partie terminée", s.over and s.result is not None)
        self.shot("11_resultats")
        yield 0.1
        self.check("résultats : profil mis à jour", app.profile.data["stats"]["games"] >= 1)
        self.click(gs.result_widgets[1])
        yield 1.5
        self.check("résultats : MENU PRINCIPAL", isinstance(app.state, MenuState))

        # --- ambiances : nuit et orage ------------------------------------
        app.profile.data["xp"] = 20000   # débloque toutes les opérations
        for op in ("nuit", "orage", "aube"):
            app.profile.data["operation"] = op
            app.start_game()
            gs = app.state
            gs.session.waves.timer = 999
            gs.cam.yaw = 0.6
            gs.cam.pitch = 0.05
            yield 2.5
            nm = f"12_operation_{op}"
            self.shot(nm)
            yield 0.1
            self.analyse(nm, 0.30)
        app.to_menu()
        yield 1.0

        # --- quitter via le menu --------------------------------------------
        menu = app.state
        called = []
        app.quit = lambda: called.append(True)   # interception : on vérifie l'appel sans couper le test
        self.click(menu.nav[PAGES.index("QUITTER")])
        yield 0.4
        self.click(menu.page_widgets[0])
        yield 0.3
        self.check("menu : QUITTER ferme le jeu", bool(called))
        yield 0.0
