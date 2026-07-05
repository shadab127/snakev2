import math
import struct
import pygame
from config import *
from shaders import *
from utils import hex_to_pixel, hex_corners, tile_noise, compute_tile_ao, lerp_color, all_hexes, hex_side_normal, compute_sun_light, compute_sky_color, in_bounds, rgb_to_hsv, hsv_to_rgb
from game_state import GameState

try:
    import moderngl
    _GL_AVAILABLE = True
except ImportError:
    _GL_AVAILABLE = False


class GLRenderer:
    def __init__(self):
        self.available = False
        self._quad_vao_cache = {}
        self.tex_cache = {}
        self.vbo = None
        self.vao_tile = None
        self.vertex_count = 0
        if not _GL_AVAILABLE:
            return
        try:
            self.ctx = moderngl.create_context(standalone=True, require=330)
            self.available = True
            self._compile_shaders()
            self._create_fbos()
            self._create_fullscreen_quad()
        except Exception as e:
            print(f"GLRenderer: {e}")
            self.available = False

    def _compile_shaders(self):
        self.prog_tile = self.ctx.program(
            vertex_shader=GL_VERTEX_SHADER_SRC,
            fragment_shader=GL_FRAGMENT_SHADER_SRC)
        self.prog_texture = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_TEXTURE_FS)
        self.prog_bloom_down = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_BLOOM_DOWN_FS)
        self.prog_bloom_blur = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_BLOOM_BLUR_FS)
        self.prog_bloom_up = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_BLOOM_UP_FS)
        self.prog_god_rays = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_GOD_RAYS_FS)
        self.prog_tone_map = self.ctx.program(
            vertex_shader=GL_FULLSCREEN_VS,
            fragment_shader=GL_TONE_MAP_FS)
    def _create_fbos(self):
        self.tex_scene = self.ctx.texture((WIDTH, HEIGHT), 4)
        self.fbo_scene = self.ctx.framebuffer(color_attachments=[self.tex_scene])
        self.tex_main = self.ctx.texture((WIDTH, HEIGHT), 4)
        self.fbo_main = self.ctx.framebuffer(color_attachments=[self.tex_main])
        bw, bh = WIDTH // 4, HEIGHT // 4
        self.tex_bloom1 = self.ctx.texture((bw, bh), 4)
        self.tex_bloom2 = self.ctx.texture((bw, bh), 4)
        self.fbo_bloom1 = self.ctx.framebuffer(color_attachments=[self.tex_bloom1])
        self.fbo_bloom2 = self.ctx.framebuffer(color_attachments=[self.tex_bloom2])
        self.fbo_tile = self.ctx.simple_framebuffer((WIDTH, HEIGHT), dtype='f4')

    def _create_fullscreen_quad(self):
        quad = [-1.0, -1.0, 0.0, 0.0,
                 1.0, -1.0, 1.0, 0.0,
                 1.0,  1.0, 1.0, 1.0,
                -1.0, -1.0, 0.0, 0.0,
                 1.0,  1.0, 1.0, 1.0,
                -1.0,  1.0, 0.0, 1.0]
        buf = bytearray()
        for i in range(0, len(quad), 4):
            buf.extend(struct.pack('<2f2f', quad[i], quad[i+1], quad[i+2], quad[i+3]))
        self.quad_vbo = self.ctx.buffer(bytes(buf))

    def _quad_vao(self, prog):
        if prog not in self._quad_vao_cache:
            self._quad_vao_cache[prog] = self.ctx.vertex_array(
                prog, self.quad_vbo, 'in_pos', 'in_uv')
        return self._quad_vao_cache[prog]

    def _set_fbo(self, fbo, clear=True):
        fbo.use()
        w, h = fbo.size
        self.ctx.viewport = (0, 0, w, h)
        if clear:
            self.ctx.clear(0.0, 0.0, 0.0, 0.0)

    def _set_uniform(self, prog, name, value):
        try:
            prog[name].value = value
        except (KeyError, ValueError):
            pass

    def _render_quad(self, prog, src_tex, target_fbo=None, blend=False, uniforms=None):
        if target_fbo:
            self._set_fbo(target_fbo, clear=False)
        if blend:
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE
        else:
            self.ctx.disable(moderngl.BLEND)
        src_tex.use(0)
        self._set_uniform(prog, 'u_tex', 0)
        if uniforms:
            for k, v in uniforms.items():
                self._set_uniform(prog, k, v)
        self._quad_vao(prog).render(moderngl.TRIANGLES)

    def upload_texture(self, name, surf):
        rgba = pygame.image.tostring(surf, 'RGBA', True)
        w, h = surf.get_size()
        if name in self.tex_cache:
            t = self.tex_cache[name]
            if t.size == (w, h):
                t.write(rgba)
                return t
            t.release()
        t = self.ctx.texture((w, h), 4, data=rgba)
        t.filter = (moderngl.LINEAR, moderngl.LINEAR)
        t.repeat_x = False
        t.repeat_y = False
        self.tex_cache[name] = t
        return t

    def render_tiles_to_fbo(self, game, fbo):
        if not self.available:
            return False
        try:
            snake_set = set(game.snake)
            tile_depths = []
            for q, r in all_hexes():
                cx, cy = hex_to_pixel(q, r)
                sx, sy, depth = game.camera.project(cx, cy, 0)
                if sx < -TILE_CLIP_MARGIN or sx > WIDTH + TILE_CLIP_MARGIN:
                    continue
                if sy < -TILE_CLIP_MARGIN or sy > HEIGHT + TILE_CLIP_MARGIN:
                    continue
                tile_depths.append((depth, q, r))
            tile_depths.sort(key=lambda x: x[0], reverse=True)
            all_verts = []
            for tile_depth, q, r in tile_depths:
                cx, cy = hex_to_pixel(q, r)
                corners = hex_corners(cx, cy)
                top_pts = [game.camera.project(c_x, c_y, 0)[:2] for c_x, c_y in corners]
                bot_pts = [game.camera.project(c_x, c_y, -TILE_HEIGHT)[:2] for c_x, c_y in corners]
                cx_proj = sum(p[0] for p in top_pts) / 6
                cy_proj = sum(p[1] for p in top_pts) / 6
                noise = tile_noise(q, r)
                noise_val = noise['detail'] * 0.15
                dist_from_center = (q * q + r * r + q * r) ** 0.5 / GRID_RADIUS
                dist_factor = max(0, 1 - dist_from_center * 0.3)
                ao_val = compute_tile_ao(q, r, snake_set)
                mat_noise = noise['base']
                if mat_noise > 0.4:
                    base_top_color, base_side_color = list(TILE_DIRT), list(TILE_SIDE_DARK)
                elif mat_noise < -0.3:
                    base_top_color, base_side_color = [130, 220, 165], list(TILE_SIDE)
                else:
                    base_top_color, base_side_color = list(TILE_TOP), list(TILE_SIDE)
                moss_noise = noise['moss']
                if moss_noise > 0.15:
                    moss_t = min(1.0, (moss_noise - 0.15) * 3)
                    base_top_color = list(lerp_color(tuple(base_top_color), TILE_MOSS, moss_t * 0.35))
                dirt_noise = noise['dirt']
                if dirt_noise > 0.2:
                    dirt_t = min(1.0, (dirt_noise - 0.2) * 2.5)
                    for ci in range(3):
                        base_top_color[ci] = min(255, int(base_top_color[ci] + (TILE_DIRT[ci] - base_top_color[ci]) * dirt_t * 0.25))
                noise_offset = int(noise_val * 20)
                for ci in range(3):
                    base_top_color[ci] = max(0, min(255, base_top_color[ci] + noise_offset))
                # HSV color variation
                h, s, v = rgb_to_hsv(*base_top_color)
                hue_shift = noise['hue'] * TILE_COLOR_HUE_SHIFT
                bright_shift = noise['brightness'] * TILE_COLOR_BRIGHTNESS_SHIFT
                sat_shift = noise['saturation'] * TILE_COLOR_SATURATION_SHIFT
                h = (h + hue_shift) % 1.0
                s = max(0.05, min(1.0, s + sat_shift))
                v = max(0.2, min(1.0, v + bright_shift))
                base_top_color = list(hsv_to_rgb(h, s, v))
                # Side color variation
                h_s, s_s, v_s = rgb_to_hsv(*base_side_color)
                h_s = (h_s + hue_shift * 0.7) % 1.0
                s_s = max(0.05, min(1.0, s_s + sat_shift * 0.7))
                v_s = max(0.15, min(1.0, v_s + bright_shift * 0.7))
                base_side_color = list(hsv_to_rgb(h_s, s_s, v_s))
                if (q, r) in snake_set:
                    base_top_color = list(lerp_color(tuple(base_top_color), TILE_TOP_LIGHT, 0.15))
                fog_depth = game.camera.project(cx, cy, 0)[2]
                tex_variation = 1.0 + 0.06 * noise['tex']
                ftop_norm = tuple(c / 255.0 for c in base_top_color)
                fside_norm = tuple(c / 255.0 for c in base_side_color)
                for i in range(6):
                    j = (i + 1) % 6
                    for px, py in [top_pts[i], top_pts[j], (cx_proj, cy_proj)]:
                        all_verts.append((px, py, ftop_norm[0], ftop_norm[1], ftop_norm[2],
                                          0.0, 0.0, 1.0, ao_val, dist_factor, fog_depth, tex_variation, float(q), float(r)))
                for i in range(6):
                    j = (i + 1) % 6
                    nq, nr = q + DIR_VECTORS[i][0], r + DIR_VECTORS[i][1]
                    if game.state == GameState.PLAYING and in_bounds(nq, nr):
                        continue
                    nx_s, ny_s, nz_s = hex_side_normal(i)
                    for px, py in [top_pts[i], top_pts[j], bot_pts[j], top_pts[i], bot_pts[j], bot_pts[i]]:
                        all_verts.append((px, py, fside_norm[0], fside_norm[1], fside_norm[2],
                                          nx_s, ny_s, nz_s, ao_val, dist_factor, fog_depth, tex_variation, float(q), float(r)))
            self.vertex_count = len(all_verts)
            buf = bytearray()
            for v in all_verts:
                buf.extend(struct.pack('<14f', *v))
            if self.vbo is None or len(buf) != self.vbo.size:
                self.vbo = self.ctx.buffer(bytes(buf))
                self.vao_tile = self.ctx.vertex_array(self.prog_tile, self.vbo,
                    'in_position', 'in_base_color', 'in_normal',
                    'in_ao', 'in_dist_factor', 'in_fog_depth',
                    'in_tex_var', 'in_q', 'in_r')
            else:
                self.vbo.write(bytes(buf))
            self._set_fbo(fbo)
            time_float = game.render_time
            self._set_uniform(self.prog_tile, 'u_time_float', time_float)
            self._set_uniform(self.prog_tile, 'u_game_over', 1 if game.state == GameState.GAME_OVER else 0)
            self._set_uniform(self.prog_tile, 'u_eat_flash', game.eat_flash)
            self._set_uniform(self.prog_tile, 'u_screen_size', (float(WIDTH), float(HEIGHT)))
            light_dir, ambient, sun_color = compute_sun_light(time_float)
            self._set_uniform(self.prog_tile, 'u_light_dir', light_dir)
            self._set_uniform(self.prog_tile, 'u_ambient', ambient)
            self._set_uniform(self.prog_tile, 'u_sun_color', tuple(c / 255.0 for c in sun_color))
            sky_top, sky_mid, sky_hor = compute_sky_color(time_float)
            fog_c = tuple(c / 255.0 for c in lerp_color(sky_mid, FOG_COLOR, 0.6))
            self._set_uniform(self.prog_tile, 'u_fog_color', fog_c)
            day_cycle = math.sin(time_float * SUN_ANGLE_SPEED)
            self._set_uniform(self.prog_tile, 'u_day_cycle', day_cycle)
            if self.vao_tile:
                self.vao_tile.render(moderngl.TRIANGLES, vertices=self.vertex_count)
            return True
        except Exception as e:
            print(f"GL tile render error: {e}")
            return False

    def post_process(self, scene_surf, time_float):
        if not self.available:
            return None
        try:
            tex_scene = self.upload_texture('_scene', scene_surf)
            light_dir, ambient, sun_color = compute_sun_light(time_float)
            sun_color_norm = tuple(c / 255.0 for c in sun_color)

            tex_current = tex_scene
            self._set_fbo(self.fbo_main)
            self._render_quad(self.prog_texture, tex_scene)

            if POST_TONE_MAP_ENABLED:
                self._set_fbo(self.fbo_scene, clear=True)
                self._render_quad(self.prog_tone_map, tex_current)
                tex_current = self.tex_scene
                self._set_fbo(self.fbo_main, clear=False)
            else:
                tex_current = tex_scene

            if POST_BLOOM_ENABLED:
                bw, bh = WIDTH // 4, HEIGHT // 4
                self._set_fbo(self.fbo_bloom1)
                self._render_quad(self.prog_bloom_down, tex_current,
                                  uniforms={'u_texel_size': (1.0 / WIDTH, 1.0 / HEIGHT),
                                            'u_bloom_threshold': BLOOM_THRESHOLD})
                self._set_fbo(self.fbo_bloom2)
                self._render_quad(self.prog_bloom_blur, self.tex_bloom1,
                                  uniforms={'u_texel_size': (1.0 / bw, 1.0 / bh), 'u_direction': (1.0, 0.0)})
                self._set_fbo(self.fbo_bloom1)
                self._render_quad(self.prog_bloom_blur, self.tex_bloom2,
                                  uniforms={'u_texel_size': (1.0 / bw, 1.0 / bh), 'u_direction': (0.0, 1.0)})
                self.tex_bloom1.use(0)
                tex_current.use(1)
                self._set_fbo(self.fbo_main, clear=False)
                self._set_uniform(self.prog_bloom_up, 'u_bloom', 0)
                self._set_uniform(self.prog_bloom_up, 'u_scene', 1)
                self._quad_vao(self.prog_bloom_up).render(moderngl.TRIANGLES)

            day_cycle = 0.5 + 0.5 * math.sin(time_float * SUN_ANGLE_SPEED)
            if POST_GOD_RAYS_ENABLED and day_cycle > 0.2:
                sun_x = WIDTH // 2 + int(math.sin(time_float * SUN_ANGLE_SPEED) * 200)
                sun_y = int(HEIGHT * 0.15)
                self._set_fbo(self.fbo_main, clear=False)
                self.ctx.enable(moderngl.BLEND)
                self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE
                self._set_uniform(self.prog_god_rays, 'u_sun_pos', (sun_x / WIDTH, sun_y / HEIGHT))
                self._set_uniform(self.prog_god_rays, 'u_time', time_float)
                self._set_uniform(self.prog_god_rays, 'u_sun_color', sun_color_norm)
                self._set_uniform(self.prog_god_rays, 'u_day_cycle', day_cycle)
                self._quad_vao(self.prog_god_rays).render(moderngl.TRIANGLES)
                self.ctx.disable(moderngl.BLEND)

            raw = self.fbo_main.read(components=4, alignment=1, dtype='u1')
            return pygame.image.frombuffer(raw, (WIDTH, HEIGHT), 'RGBA')
        except Exception as e:
            print(f"GL post_process error: {e}")
            return None
