"""Moteur de rendu ModernGL : ombres, passe HDR, particules, post-traitement, interface."""
import math
import numpy as np
import moderngl
import pygame

from engine import mathutils as mu
from engine.resources import load_shader_source
from graphics import textures
from graphics.materials import material_arrays, NUM_LAYERS
from graphics.meshbuilder import FORMAT

MAX_LIGHTS = 24


class ShaderError(RuntimeError):
    pass


def set_u(prog, name, value):
    u = prog.get(name, None)
    if u is None:
        return
    if isinstance(value, (bytes, bytearray)):
        u.write(value)
    elif isinstance(value, np.ndarray):
        u.write(np.ascontiguousarray(value, dtype=np.float32).tobytes())
    else:
        u.value = value


class GpuMesh:
    """Maillage statique sur GPU avec ses VAO pour chaque programme."""

    def __init__(self, renderer, arr):
        ctx = renderer.ctx
        arr = np.ascontiguousarray(arr, np.float32)
        self.count = len(arr)
        self.vbo = ctx.buffer(arr.tobytes())
        attrs = ("in_pos", "in_normal", "in_uv", "in_layer", "in_color")
        self.vao = ctx.vertex_array(renderer.prog_lit, [(self.vbo, FORMAT, *attrs)])
        self.vao_vm = ctx.vertex_array(renderer.prog_vm, [(self.vbo, FORMAT, *attrs)])
        self.vao_shadow = ctx.vertex_array(renderer.prog_shadow,
                                           [(self.vbo, "3f 12x 2f 1f 12x", "in_pos", "in_uv", "in_layer")])
        self.min = arr[:, 0:3].min(axis=0) if len(arr) else np.zeros(3)
        self.max = arr[:, 0:3].max(axis=0) if len(arr) else np.zeros(3)

    def release(self):
        for o in (self.vao, self.vao_vm, self.vao_shadow, self.vbo):
            o.release()


class DrawItem:
    __slots__ = ("mesh", "model", "tint", "emis", "emis_scale", "flash", "shadow")

    def __init__(self, mesh, model, tint=(1, 1, 1), emis=(1, 1, 1), emis_scale=1.0, flash=0.0, shadow=True):
        self.mesh = mesh
        self.model = model
        self.tint = tint
        self.emis = emis
        self.emis_scale = emis_scale
        self.flash = flash
        self.shadow = shadow


class FrameData:
    """Tout ce qu'il faut pour dessiner une image."""

    def __init__(self):
        self.view = np.eye(4)
        self.proj = np.eye(4)
        self.cam_pos = np.zeros(3)
        self.cam_forward = np.array([0, 0, -1.0])
        self.env = None
        self.lights = []          # (pos, rayon, couleur)
        self.static_chunks = []   # GpuMesh statiques (culling par le renderer)
        self.far_meshes = []      # décors lointains (pas d'ombre)
        self.dynamic = []         # DrawItem
        self.viewmodel = []       # DrawItem (arme en vue subjective)
        self.particles = None     # np.ndarray (N, 12)
        self.vm_particles = None
        self.studio = False
        self.damage = 0.0
        self.low_health = 0.0
        self.fade = 1.0
        self.time = 0.0
        self.shadow_center = None


class Renderer:
    def __init__(self, ctx, settings, window_size, progress=None, defer_textures=False):
        self.ctx = ctx
        self.settings = settings
        self.window_size = window_size
        self.stats = {"chunks": 0, "draws": 0, "particles": 0}
        self.capture_before_overlay = False
        self.pre_overlay = None
        self._compile_programs()
        quad = np.array([-1, -1, 1, -1, 1, 1, -1, -1, 1, 1, -1, 1], np.float32)
        self.quad_vbo = ctx.buffer(quad.tobytes())
        self.vao_composite = ctx.vertex_array(self.prog_composite, [(self.quad_vbo, "2f", "in_pos")])
        self.vao_bright = ctx.vertex_array(self.prog_bright, [(self.quad_vbo, "2f", "in_pos")])
        self.vao_blur = ctx.vertex_array(self.prog_blur, [(self.quad_vbo, "2f", "in_pos")])
        self.vao_fxaa = ctx.vertex_array(self.prog_fxaa, [(self.quad_vbo, "2f", "in_pos")])
        self.vao_overlay = ctx.vertex_array(self.prog_overlay, [(self.quad_vbo, "2f", "in_pos")])
        # particules instanciées
        corners = np.array([-1, -1, 1, -1, 1, 1, -1, -1, 1, 1, -1, 1], np.float32)
        self.corner_vbo = ctx.buffer(corners.tobytes())
        self.particle_capacity = 8192
        self.particle_vbo = ctx.buffer(reserve=self.particle_capacity * 12 * 4, dynamic=True)
        self.vao_particles = ctx.vertex_array(self.prog_particles, [
            (self.corner_vbo, "2f", "in_corner"),
            (self.particle_vbo, "3f 3f 1f 4f 1f/i", "i_pos", "i_axis", "i_size", "i_color", "i_kind"),
        ])
        self.tex_albedo = None
        self.tex_normal = None
        self.tex_size = settings.preset["tex_size"]
        if not defer_textures:
            self.load_textures(progress)
        rough, metal, emis, flags = material_arrays()
        for p in (self.prog_lit, self.prog_vm):
            set_u(p, "u_matRough", rough)
            set_u(p, "u_matMetal", metal)
            set_u(p, "u_matEmis", emis)
            set_u(p, "u_matFlags", flags)
            set_u(p, "u_albedo", 0)
            set_u(p, "u_normalmap", 1)
            set_u(p, "u_shadow", 2)
        set_u(self.prog_shadow, "u_matFlags", flags)
        set_u(self.prog_shadow, "u_albedo", 0)
        set_u(self.prog_composite, "u_color", 0)
        set_u(self.prog_composite, "u_depth", 1)
        set_u(self.prog_composite, "u_bloom", 2)
        set_u(self.prog_composite, "u_shadow", 3)
        self.shadow_tex = None
        self.overlay_tex = None
        self.targets_ok = False
        self.apply_quality()
        self.resize(window_size)

    # ------------------------------------------------------------------
    def _program(self, vert, frag, defines=()):
        try:
            return self.ctx.program(vertex_shader=load_shader_source(vert, defines),
                                    fragment_shader=load_shader_source(frag, defines))
        except moderngl.Error as e:
            raise ShaderError(f"Échec de compilation {vert}/{frag} :\n{e}") from e

    def _compile_programs(self):
        self.prog_lit = self._program("lit.vert", "lit.frag")
        self.prog_vm = self._program("lit.vert", "lit.frag", ("VIEWMODEL",))
        self.prog_shadow = self._program("shadow.vert", "shadow.frag")
        self.prog_composite = self._program("fullscreen.vert", "composite.frag")
        self.prog_bright = self._program("fullscreen.vert", "bright.frag")
        self.prog_blur = self._program("fullscreen.vert", "blur.frag")
        self.prog_fxaa = self._program("fullscreen.vert", "fxaa.frag")
        self.prog_overlay = self._program("fullscreen.vert", "overlay.frag")
        self.prog_particles = self._program("particles.vert", "particles.frag")

    def load_textures(self, progress=None):
        size = self.settings.preset["tex_size"]
        alb, nrm = textures.load_all(size, progress)
        if self.tex_albedo:
            self.tex_albedo.release()
            self.tex_normal.release()
        n = alb.shape[0]
        self.tex_albedo = self.ctx.texture_array((size, size, n), 4, np.ascontiguousarray(alb).tobytes())
        self.tex_normal = self.ctx.texture_array((size, size, n), 4, np.ascontiguousarray(nrm).tobytes())
        for t in (self.tex_albedo, self.tex_normal):
            t.build_mipmaps()
            t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            t.repeat_x = True
            t.repeat_y = True
        self.tex_size = size
        self._apply_anisotropy()

    def _apply_anisotropy(self):
        if self.tex_albedo is None:
            return
        a = float(self.settings.preset["anisotropy"])
        for t in (self.tex_albedo, self.tex_normal):
            try:
                t.anisotropy = a
            except Exception:
                pass

    def apply_quality(self):
        p = self.settings.preset
        if self.tex_albedo is not None and p["tex_size"] != self.tex_size:
            self.load_textures()
        self._apply_anisotropy()
        size = p["shadow_size"]
        if self.shadow_tex is None or self.shadow_tex.size[0] != size:
            if self.shadow_tex:
                self.shadow_fbo.release()
                self.shadow_tex.release()
            self.shadow_tex = self.ctx.depth_texture((size, size))
            self.shadow_tex.compare_func = "<="
            self.shadow_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.shadow_tex.repeat_x = False
            self.shadow_tex.repeat_y = False
            self.shadow_fbo = self.ctx.framebuffer(depth_attachment=self.shadow_tex)
        if self.targets_ok:
            self.resize(self.window_size)

    def resize(self, window_size):
        w, h = max(64, int(window_size[0])), max(64, int(window_size[1]))
        self.window_size = (w, h)
        scale = self.settings.preset["render_scale"]
        sw, sh = max(64, int(w * scale)), max(64, int(h * scale))
        if self.targets_ok:
            for o in self._targets:
                o.release()
        ctx = self.ctx
        self.scene_size = (sw, sh)
        self.hdr_tex = ctx.texture((sw, sh), 4, dtype="f2")
        self.depth_tex = ctx.depth_texture((sw, sh))
        self.depth_tex.compare_func = ""
        self.depth_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.scene_fbo = ctx.framebuffer([self.hdr_tex], self.depth_tex)
        self.ldr_tex = ctx.texture((sw, sh), 4)
        self.ldr_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.ldr_fbo = ctx.framebuffer([self.ldr_tex])
        bw, bh = max(16, sw // 2), max(16, sh // 2)
        self.bloom_size = (bw, bh)
        self.bloom_a = ctx.texture((bw, bh), 4, dtype="f2")
        self.bloom_b = ctx.texture((bw, bh), 4, dtype="f2")
        for t in (self.bloom_a, self.bloom_b, self.hdr_tex):
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t.repeat_x = False
            t.repeat_y = False
        self.bloom_fbo_a = ctx.framebuffer([self.bloom_a])
        self.bloom_fbo_b = ctx.framebuffer([self.bloom_b])
        self.overlay_tex = ctx.texture((w, h), 4)
        self.overlay_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        # image finale hors écran (lecture fiable pour les captures, puis copie vers la fenêtre)
        self.final_tex = ctx.texture((w, h), 4)
        self.final_fbo = ctx.framebuffer([self.final_tex])
        self._targets = [self.scene_fbo, self.hdr_tex, self.depth_tex, self.ldr_fbo, self.ldr_tex,
                         self.bloom_fbo_a, self.bloom_fbo_b, self.bloom_a, self.bloom_b, self.overlay_tex,
                         self.final_fbo, self.final_tex]
        self.targets_ok = True

    # ------------------------------------------------------------------
    def light_matrix(self, center, env):
        R = self.settings.preset["shadow_radius"]
        size = self.shadow_tex.size[0]
        ld = np.asarray(env.light_dir, np.float64)
        up = (0, 1, 0) if abs(ld[1]) < 0.99 else (1, 0, 0)
        eye = np.asarray(center) + ld * 400.0
        lv = mu.look_at(eye, center, up)
        texel = 2 * R / size
        o = lv @ np.array([0, 0, 0, 1.0])
        snapped = np.round(o[:2] / texel) * texel
        lv = mu.translate(snapped[0] - o[0], snapped[1] - o[1], 0) @ lv
        lp = mu.ortho(-R, R, -R, R, 1.0, 900.0)
        return lp @ lv

    def _env_uniforms(self, prog, env, t):
        set_u(prog, "u_sunDir", tuple(float(x) for x in env.light_dir))
        set_u(prog, "u_sunColor", tuple(float(x) for x in env.light_color))
        set_u(prog, "u_trueSunDir", tuple(float(x) for x in env.true_sun))
        set_u(prog, "u_skyZenith", tuple(float(x) for x in env.zenith))
        set_u(prog, "u_skyHorizon", tuple(float(x) for x in env.horizon))
        set_u(prog, "u_groundColor", tuple(float(x) for x in env.ground))
        set_u(prog, "u_night", float(env.night))
        set_u(prog, "u_time", float(t))

    def _draw_item_lit(self, prog, vao, item):
        set_u(prog, "u_model", mu.to_gl(item.model))
        set_u(prog, "u_tint", tuple(item.tint))
        set_u(prog, "u_emisTint", tuple(item.emis))
        set_u(prog, "u_emisScale", float(item.emis_scale))
        set_u(prog, "u_flash", float(item.flash))
        vao.render(moderngl.TRIANGLES)

    def render(self, f: FrameData):
        ctx = self.ctx
        p = self.settings.preset
        env = f.env
        t = f.time
        vp = f.proj @ f.view
        planes = mu.frustum_planes(vp)
        identity = mu.to_gl(np.eye(4))
        self.stats["draws"] = 0

        # ---- culling des blocs statiques -----------------------------------
        visible = []
        if f.static_chunks:
            mins = np.array([c.min for c in f.static_chunks])
            maxs = np.array([c.max for c in f.static_chunks])
            vis = mu.aabbs_in_frustum(planes, mins, maxs)
            d = np.linalg.norm((mins + maxs) * 0.5 - f.cam_pos, axis=1) - np.linalg.norm(maxs - mins, axis=1) * 0.5
            vis &= d < p["view_distance"]
            visible = [c for c, v in zip(f.static_chunks, vis) if v]
        self.stats["chunks"] = len(visible)

        # ---- passe d'ombre ---------------------------------------------------
        center = f.shadow_center if f.shadow_center is not None else \
            f.cam_pos + np.array([f.cam_forward[0], 0, f.cam_forward[2]]) * p["shadow_radius"] * 0.45
        light_vp = self.light_matrix(center, env)
        lplanes = mu.frustum_planes(light_vp)
        self.shadow_fbo.use()
        self.shadow_fbo.clear(depth=1.0)
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.CULL_FACE)
        ctx.disable(moderngl.BLEND)
        ps = self.prog_shadow
        set_u(ps, "u_lightvp", mu.to_gl(light_vp))
        set_u(ps, "u_time", float(t))
        set_u(ps, "u_wind", float(env.wind))
        self.tex_albedo.use(0)
        set_u(ps, "u_model", identity)
        if f.static_chunks:
            svis = mu.aabbs_in_frustum(lplanes, mins, maxs)
            for c, v in zip(f.static_chunks, svis):
                if v:
                    c.vao_shadow.render(moderngl.TRIANGLES)
        for item in f.dynamic:
            if item.shadow:
                set_u(ps, "u_model", mu.to_gl(item.model))
                item.mesh.vao_shadow.render(moderngl.TRIANGLES)

        # ---- passe principale HDR ------------------------------------------
        self.scene_fbo.use()
        self.scene_fbo.clear(0.0, 0.0, 0.0, 1.0, depth=1.0)
        pl = self.prog_lit
        lights = sorted(f.lights, key=lambda L: np.sum((np.asarray(L[0]) - f.cam_pos) ** 2))[:min(p["lights"], MAX_LIGHTS)]
        lp = np.zeros((MAX_LIGHTS, 4), np.float32)
        lc = np.zeros((MAX_LIGHTS, 3), np.float32)
        for i, (pos, rad, colr) in enumerate(lights):
            lp[i, :3] = pos
            lp[i, 3] = rad
            lc[i] = colr
        self.tex_albedo.use(0)
        self.tex_normal.use(1)
        self.shadow_tex.use(2)
        for prog in (pl, self.prog_vm):
            self._env_uniforms(prog, env, t)
            set_u(prog, "u_viewproj", mu.to_gl(vp))
            set_u(prog, "u_lightvp", mu.to_gl(light_vp))
            set_u(prog, "u_camPos", tuple(float(x) for x in f.cam_pos))
            set_u(prog, "u_wind", float(env.wind))
            set_u(prog, "u_wetness", float(env.wetness))
            set_u(prog, "u_windowLights", float(env.window_lights))
            set_u(prog, "u_shadowTexel", 1.0 / self.shadow_tex.size[0])
            set_u(prog, "u_pcf", int(p["pcf"]))
            set_u(prog, "u_ambient", float(env.ambient))
            set_u(prog, "u_numLights", len(lights))
            set_u(prog, "u_lightPos", lp)
            set_u(prog, "u_lightCol", lc)
        set_u(pl, "u_model", identity)
        set_u(pl, "u_tint", (1.0, 1.0, 1.0))
        set_u(pl, "u_emisTint", (1.0, 1.0, 1.0))
        set_u(pl, "u_emisScale", float(env.lamp_glow))
        set_u(pl, "u_flash", 0.0)
        for c in visible:
            c.vao.render(moderngl.TRIANGLES)
            self.stats["draws"] += 1
        for m in f.far_meshes:
            m.vao.render(moderngl.TRIANGLES)
        if f.dynamic:
            # culling vectorisé de tous les objets dynamiques en un seul appel
            pos = np.array([it.model[:3, 3] for it in f.dynamic])
            rad = np.array([float(np.max(it.mesh.max - it.mesh.min)) * 1.5 for it in f.dynamic])[:, None]
            dvis = mu.aabbs_in_frustum(planes, pos - rad, pos + rad)
            for item, v in zip(f.dynamic, dvis):
                if v:
                    self._draw_item_lit(pl, item.mesh.vao, item)
                    self.stats["draws"] += 1

        # ---- particules -----------------------------------------------------
        inv_view = np.linalg.inv(f.view)
        cam_right = inv_view[:3, 0]
        cam_up = inv_view[:3, 1]
        self._draw_particles(f.particles, vp, f.cam_pos, cam_right, cam_up)

        # ---- arme en vue subjective -------------------------------------
        if f.viewmodel:
            ctx.disable(moderngl.BLEND)
            for item in f.viewmodel:
                self._draw_item_lit(self.prog_vm, item.mesh.vao_vm, item)
        if f.vm_particles is not None and len(f.vm_particles):
            ctx.disable(moderngl.DEPTH_TEST)
            self._draw_particles(f.vm_particles, vp, f.cam_pos, cam_right, cam_up)
            ctx.enable(moderngl.DEPTH_TEST)

        # ---- post-traitement ------------------------------------------------
        ctx.disable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.BLEND)
        use_bloom = bool(p["bloom"])
        if use_bloom:
            self.bloom_fbo_a.use()
            self.hdr_tex.use(0)
            set_u(self.prog_bright, "u_color", 0)
            set_u(self.prog_bright, "u_texel", (1.0 / self.scene_size[0], 1.0 / self.scene_size[1]))
            set_u(self.prog_bright, "u_threshold", 1.4)
            self.vao_bright.render()
            bw, bh = self.bloom_size
            set_u(self.prog_blur, "u_tex", 0)
            for spread in (1.0, 2.0, 3.5):
                self.bloom_fbo_b.use()
                self.bloom_a.use(0)
                set_u(self.prog_blur, "u_dir", (spread / bw, 0.0))
                self.vao_blur.render()
                self.bloom_fbo_a.use()
                self.bloom_b.use(0)
                set_u(self.prog_blur, "u_dir", (0.0, spread / bh))
                self.vao_blur.render()

        pc = self.prog_composite
        self.ldr_fbo.use()
        self.hdr_tex.use(0)
        self.depth_tex.use(1)
        self.bloom_a.use(2)
        self.shadow_tex.use(3)
        self._env_uniforms(pc, env, t)
        set_u(pc, "u_invViewProj", mu.to_gl(np.linalg.inv(vp)))
        set_u(pc, "u_lightvp", mu.to_gl(light_vp))
        set_u(pc, "u_camPos", tuple(float(x) for x in f.cam_pos))
        set_u(pc, "u_fogColor", tuple(float(x) for x in env.fog_color))
        set_u(pc, "u_fogDensity", float(env.fog_density))
        set_u(pc, "u_fogFalloff", 0.035)
        set_u(pc, "u_volSteps", 0 if f.studio else int(p["volumetric_steps"]))
        set_u(pc, "u_volStrength", float(0.0009 + env.fog_density * 0.12))
        set_u(pc, "u_exposure", float(env.exposure * self.settings["brightness"]))
        set_u(pc, "u_bloomStrength", 0.09)
        set_u(pc, "u_useBloom", 1 if use_bloom else 0)
        set_u(pc, "u_studio", 1 if f.studio else 0)
        set_u(pc, "u_clouds", 1 if p["clouds"] else 0)
        set_u(pc, "u_cloudCover", float(env.cloud_cover))
        set_u(pc, "u_lightning", float(env.lightning))
        set_u(pc, "u_damage", float(f.damage))
        set_u(pc, "u_lowHealth", float(f.low_health))
        set_u(pc, "u_fade", float(f.fade))
        set_u(pc, "u_resolution", (float(self.scene_size[0]), float(self.scene_size[1])))
        self.vao_composite.render()

        self.final_fbo.use()
        self.ldr_tex.use(0)
        set_u(self.prog_fxaa, "u_tex", 0)
        set_u(self.prog_fxaa, "u_texel", (1.0 / self.scene_size[0], 1.0 / self.scene_size[1]))
        set_u(self.prog_fxaa, "u_enabled", 1 if p["fxaa"] else 0)
        self.vao_fxaa.render()
        self.last_light_vp = light_vp

    def _draw_particles(self, data, vp, cam_pos, right, up):
        if data is None or len(data) == 0:
            return
        ctx = self.ctx
        n = min(len(data), self.particle_capacity)
        self.stats["particles"] = n
        self.particle_vbo.orphan(self.particle_capacity * 48)
        self.particle_vbo.write(np.ascontiguousarray(data[:n], np.float32).tobytes())
        pp = self.prog_particles
        set_u(pp, "u_viewproj", mu.to_gl(vp))
        set_u(pp, "u_camPos", tuple(float(x) for x in cam_pos))
        set_u(pp, "u_camRight", tuple(float(x) for x in right))
        set_u(pp, "u_camUp", tuple(float(x) for x in up))
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA
        fbo = ctx.fbo
        try:
            fbo.depth_mask = False
        except Exception:
            pass
        self.vao_particles.render(moderngl.TRIANGLES, vertices=6, instances=n)
        try:
            fbo.depth_mask = True
        except Exception:
            pass
        ctx.disable(moderngl.BLEND)

    # ------------------------------------------------------------------
    def clear_screen(self, color=(0, 0, 0)):
        self.final_fbo.use()
        self.final_fbo.clear(*color, 1.0)

    def read_final(self):
        w, h = self.window_size
        return self.final_fbo.read(viewport=(0, 0, w, h), components=3)

    def draw_overlay(self, surface):
        """Compose une surface pygame RGBA (transparente) au-dessus de l'image."""
        w, h = self.window_size
        if self.capture_before_overlay:
            # utilisé par les tests : image 3D seule, juste avant la composition de l'interface
            self.pre_overlay = self.read_final()
        if surface.get_size() != (w, h):
            self.present()
            return
        if surface.get_pitch() == w * 4 and surface.get_bytesize() == 4:
            # envoi direct du tampon (sans conversion) ; ordre des canaux et retournement gérés par le GPU
            masks = surface.get_masks()
            order = {0xFF: "R", 0xFF00: "G", 0xFF0000: "B", 0xFF000000: "A"}
            # pour chaque canal logique (R, G, B, A) : canal de texture qui le contient
            swizzle = "".join(order.get(m, "A") for m in masks[:4])
            if self.overlay_tex.swizzle != swizzle:
                self.overlay_tex.swizzle = swizzle
            self.overlay_tex.write(surface.get_view("1"))
            flip = 1
        else:
            self.overlay_tex.swizzle = "RGBA"
            self.overlay_tex.write(pygame.image.tobytes(surface, "RGBA", True))
            flip = 0
        set_u(self.prog_overlay, "u_flip", flip)
        ctx = self.ctx
        self.final_fbo.use()
        ctx.disable(moderngl.DEPTH_TEST)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.overlay_tex.use(0)
        set_u(self.prog_overlay, "u_tex", 0)
        self.vao_overlay.render()
        ctx.disable(moderngl.BLEND)
        self.present()

    def present(self):
        """Copie l'image finale dans la fenêtre."""
        ctx = self.ctx
        ctx.copy_framebuffer(ctx.screen, self.final_fbo)
