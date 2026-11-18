"""Application : fenêtre OpenGL, chargement, boucle principale, gestion des états."""
import os
import sys
import time
import datetime
import numpy as np
import pygame
import moderngl

from engine.resources import ROOT
from config.settings import Settings
from gameplay.progression import Profile
from graphics.renderer import Renderer, GpuMesh
from graphics import models
from gameplay import city as citymod
from gameplay.world import CollisionWorld
from audio.manager import AudioManager
from ui import theme as T
from ui.theme import S

DYNAMIC_MODELS = ["drone_eclaireur", "drone_sentinelle", "drone_blinde", "rotor", "weapon_pulsar", "weapon_faucon",
                  "weapon_tempete", "repair_kit", "overcharge", "data_core", "beacon", "ring", "pedestal"]

INPUT_EVENTS = (pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION,
                pygame.MOUSEWHEEL, pygame.TEXTINPUT)

LOADING_TIPS = [
    "Génération des matériaux PBR de la ville…",
    "Calibrage des drones d'entraînement…",
    "Synthèse de l'ambiance sonore urbaine…",
    "Construction des quartiers et du mobilier urbain…",
]


class App:
    def __init__(self, autopilot=None, windowed_size=None):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.init()
        pygame.display.set_caption("ZONE DE FRAPPE")
        self.settings = Settings()
        if windowed_size:
            self.settings["resolution"] = list(windowed_size)
            self.settings["fullscreen"] = False
        self.autopilot = autopilot
        self.virtual_keys = set()
        self.virtual_look = (0.0, 0.0)
        self.mouse_captured = False
        self.running = True
        self.dt = 1 / 60
        self.fps = 60.0
        self.state = None
        self.display_change = False
        self.frame = 0
        for a, b in ((pygame.GL_CONTEXT_MAJOR_VERSION, 3), (pygame.GL_CONTEXT_MINOR_VERSION, 3),
                     (pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)):
            pygame.display.gl_set_attribute(a, b)
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)
        self._set_mode()
        self.ctx = moderngl.create_context()
        self.size = pygame.display.get_surface().get_size()
        T.FONTS.set_scale(self.size[1])
        self.ui_surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self.renderer = Renderer(self.ctx, self.settings, self.size, defer_textures=True)
        self.profile = Profile()
        self.audio = AudioManager(self.settings)
        self.load()

    # ------------------------------------------------------------------
    def _set_mode(self):
        st = self.settings
        vs = 1 if st["vsync"] else 0
        if st["fullscreen"]:
            desk = pygame.display.get_desktop_sizes()[0]
            flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.FULLSCREEN
            size = desk
        else:
            flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
            desk = pygame.display.get_desktop_sizes()[0]
            size = (min(st["resolution"][0], desk[0]), min(st["resolution"][1], desk[1] - 60))
        try:
            pygame.display.set_mode(size, flags, vsync=vs)
        except pygame.error:
            pygame.display.set_mode(size, flags)

    def request_display_change(self):
        self.display_change = True

    def _apply_display_change(self):
        self.display_change = False
        self._set_mode()
        self.on_resize(pygame.display.get_surface().get_size())

    def on_resize(self, size):
        size = (max(320, int(size[0])), max(200, int(size[1])))
        if size == self.size and self.renderer.window_size == size:
            return
        self.size = size
        self.ctx.viewport = (0, 0, *size)
        self.renderer.resize(size)
        self.ui_surface = pygame.Surface(size, pygame.SRCALPHA)
        T.FONTS.set_scale(size[1])
        if self.state and hasattr(self.state, "layout"):
            self.state.layout()

    def apply_quality(self):
        self.renderer.apply_quality()
        if self.state and hasattr(self.state, "session"):
            self.state.session.particles.resize(self.settings.preset["particles"])

    def set_mouse_captured(self, cap):
        if self.autopilot is not None:
            cap = False  # en test automatique on ne capture jamais la souris
        self.mouse_captured = cap
        pygame.event.set_grab(cap)
        pygame.mouse.set_visible(not cap)
        pygame.mouse.get_rel()

    # ------------------------------------------------------------------
    def _loading_screen(self, frac, msg):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
        W, H = self.size
        surf = self.ui_surface
        surf.fill((6, 8, 12, 255))
        g = T.gradient_v((W, H // 2), (0, 0, 0, 0), (255, 140, 30, 18))
        surf.blit(g, (0, H // 2))
        T.text(surf, "ZONE DE", (S(80), H - S(330)), 40, T.ACCENT, bold=True)
        T.text(surf, "FRAPPE", (S(76), H - S(292)), 96, T.WHITE, bold=True)
        T.text(surf, "PROGRAMME D'ENTRAÎNEMENT TACTIQUE", (S(80), H - S(170)), 16, T.MUTED, bold=True)
        T.bar(surf, (S(80), H - S(110), W - S(160), S(4)), frac, T.ACCENT)
        T.text(surf, msg, (S(80), H - S(96)), 16, T.TEXT)
        T.text(surf, f"{int(frac * 100)} %", (W - S(80), H - S(96)), 16, T.WHITE, bold=True, anchor="topright")
        tip = LOADING_TIPS[min(len(LOADING_TIPS) - 1, int(frac * len(LOADING_TIPS)))]
        T.text(surf, tip, (W - S(80), H - S(140)), 16, T.DIM, anchor="topright")
        self.renderer.clear_screen((0.02, 0.025, 0.035))
        self.renderer.draw_overlay(surf)
        pygame.display.flip()

    def load(self):
        t0 = time.time()
        stage = lambda a, b: (lambda f, m: self._loading_screen(a + (b - a) * f, m))
        self._loading_screen(0.0, "Initialisation…")
        self.renderer.load_textures(stage(0.0, 0.35))
        self.audio.load(stage(0.35, 0.6))
        names = models.all_names()
        for i, n in enumerate(names):
            models.get(n)
            self._loading_screen(0.6 + 0.1 * (i + 1) / len(names), f"Modèles 3D : {n}")
        self.city = citymod.generate(progress=stage(0.7, 0.9))
        self.world = CollisionWorld(self.city.boxes, self.city.half)
        self._loading_screen(0.92, "Envoi de la géométrie au GPU…")
        self.static_chunks = [GpuMesh(self.renderer, b.build()) for b in self.city.chunks.values()]
        self.far_meshes = [GpuMesh(self.renderer, self.city.far.build())]
        self.meshes = {n: GpuMesh(self.renderer, models.get(n)) for n in DYNAMIC_MODELS}
        self.lamp_array = np.array(self.city.lamps, np.float64)
        from ui.hud import HUD
        self.hud = HUD(self, self.city)
        self._loading_screen(1.0, "Prêt")
        self.load_time = time.time() - t0
        print(f"[ZONE DE FRAPPE] chargement {self.load_time:.1f} s — "
              f"{sum(c.count for c in self.static_chunks) // 3} triangles statiques, "
              f"{len(self.city.boxes)} volumes de collision")

    # ------------------------------------------------------------------
    def change_state(self, st):
        self.state = st
        st.enter()

    def to_menu(self):
        from ui.menu import MenuState
        self.change_state(MenuState(self))

    def start_game(self):
        from gameplay.game_state import GameState
        self.audio.stop_loops()
        self.change_state(GameState(self))

    def quit(self):
        self.running = False

    def screenshot(self, path=None):
        w, h = self.size
        data = self.renderer.read_final()
        img = pygame.image.frombuffer(data, (w, h), "RGB")
        img = pygame.transform.flip(img, False, True)
        if path is None:
            d = ROOT / "screenshots"
            d.mkdir(exist_ok=True)
            path = d / f"zone_de_frappe_{datetime.datetime.now():%Y%m%d_%H%M%S}.png"
        pygame.image.save(img, str(path))
        return path

    def run(self):
        self.to_menu()
        clock = pygame.time.Clock()
        fps_acc, fps_n = 0.0, 0
        while self.running:
            ms = clock.tick(0 if self.settings["vsync"] else 240)
            self.dt = min(0.05, max(1e-4, ms / 1000.0))
            fps_acc += self.dt
            fps_n += 1
            if fps_acc > 0.5:
                self.fps = fps_n / fps_acc
                fps_acc, fps_n = 0.0, 0
            if self.display_change:
                self._apply_display_change()
            for ev in pygame.event.get():
                if self.autopilot is not None and ev.type in INPUT_EVENTS and not getattr(ev, "autotest", False):
                    continue  # test automatique : on ignore le vrai clavier / la vraie souris
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.VIDEORESIZE:
                    self.on_resize((ev.w, ev.h))
                elif ev.type == pygame.WINDOWSIZECHANGED:
                    self.on_resize((ev.x, ev.y))
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                    self.settings["fullscreen"] = not self.settings["fullscreen"]
                    self.settings.save()
                    self.request_display_change()
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F12:
                    p = self.screenshot()
                    print("Capture :", p)
                else:
                    self.state.handle(ev)
            if self.autopilot is not None:
                self.autopilot.step(self, self.dt)
                if not self.running:
                    break
            self.state.update(self.dt)
            self.state.render()
            if self.autopilot is not None:
                self.autopilot.after_render(self)
            pygame.display.flip()
            self.frame += 1
        self.settings.save()
        self.profile.save()
        pygame.quit()
