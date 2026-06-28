GL_FRAGMENT_SHADER_SRC = '''
#version 330

in vec3 v_base_color;
in vec3 v_normal;
in float v_ao;
in float v_dist_factor;
in float v_fog_depth;
in float v_tex_var;
in float v_q;
in float v_r;

out vec4 f_color;

uniform float u_time_float;
uniform int u_game_over;
uniform float u_eat_flash;

const vec3 LIGHT_DIR = vec3(0.436, -0.524, 0.699);
const float AMBIENT_LIGHT_VAL = 0.25;
const float SUN_ANGLE_SPEED = 0.03;
const vec3 FOG_COLOR = vec3(0.110, 0.157, 0.275);
const vec3 GAME_OVER_TOP = vec3(0.039, 0.098, 0.078);
const vec3 GAME_OVER_SIDE = vec3(0.024, 0.055, 0.047);
const vec3 TILE_GLOW = vec3(0.314, 0.863, 0.588);

void main() {
    vec3 base_c = v_base_color;
    if (u_game_over == 1) {
        if (v_normal.z > 0.5) {
            base_c = GAME_OVER_TOP;
        } else {
            base_c = GAME_OVER_SIDE;
        }
    } else if (u_eat_flash > 0.0) {
        float flash = min(1.0, u_eat_flash / 12.0);
        vec3 flash_c = TILE_GLOW * 0.3;
        base_c = mix(base_c, flash_c, flash * 0.5);
    }

    float sun_factor = 0.85 + 0.15 * sin(u_time_float * SUN_ANGLE_SPEED + v_q * 0.5 + v_r * 0.3);
    float diff = max(0.0, dot(v_normal, LIGHT_DIR));
    float light = (AMBIENT_LIGHT_VAL + (1.0 - AMBIENT_LIGHT_VAL) * diff) * sun_factor * v_dist_factor * v_ao;

    vec3 color = base_c * light;

    float fog_t = clamp((v_fog_depth - 350.0) / 850.0, 0.0, 1.0);
    color = mix(color, FOG_COLOR, fog_t * 0.35);
    color *= v_tex_var;

    f_color = vec4(color, 1.0);
}
'''

GL_VERTEX_SHADER_SRC = '''
#version 330

in vec2 in_position;
in vec3 in_base_color;
in vec3 in_normal;
in float in_ao;
in float in_dist_factor;
in float in_fog_depth;
in float in_tex_var;
in float in_q;
in float in_r;

out vec3 v_base_color;
out vec3 v_normal;
out float v_ao;
out float v_dist_factor;
out float v_fog_depth;
out float v_tex_var;
out float v_q;
out float v_r;

uniform vec2 u_screen_size;

void main() {
    gl_Position = vec4(
        (in_position.x / u_screen_size.x) * 2.0 - 1.0,
        -((in_position.y / u_screen_size.y) * 2.0 - 1.0),
        0.0,
        1.0
    );
    v_base_color = in_base_color;
    v_normal = in_normal;
    v_ao = in_ao;
    v_dist_factor = in_dist_factor;
    v_fog_depth = in_fog_depth;
    v_tex_var = in_tex_var;
    v_q = in_q;
    v_r = in_r;
}
'''

GL_FULLSCREEN_VS = '''
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_pos, 0.0, 1.0);
    v_uv = in_uv;
}
'''

GL_TEXTURE_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
void main() {
    f_color = texture(u_tex, v_uv);
}
'''

GL_TEXTURE_ADD_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
void main() {
    vec4 c = texture(u_tex, v_uv);
    f_color = vec4(c.rgb * c.a, c.a);
}
'''

GL_BLOOM_DOWN_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
uniform vec2 u_texel_size;
const vec3 LUMA = vec3(0.299, 0.587, 0.114);
void main() {
    vec2 ts = u_texel_size;
    vec4 color = vec4(0.0);
    color += texture(u_tex, v_uv + vec2(-ts.x, -ts.y));
    color += texture(u_tex, v_uv + vec2( ts.x, -ts.y));
    color += texture(u_tex, v_uv + vec2(-ts.x,  ts.y));
    color += texture(u_tex, v_uv + vec2( ts.x,  ts.y));
    color *= 0.25;
    float luma = dot(color.rgb, LUMA);
    float bright = max(0.0, luma - 0.25);
    f_color = vec4(color.rgb * bright, 1.0);
}
'''

GL_BLOOM_BLUR_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
uniform vec2 u_texel_size;
uniform vec2 u_direction;
void main() {
    vec4 color = texture(u_tex, v_uv) * 0.227027;
    vec2 ts = u_texel_size * u_direction;
    color += texture(u_tex, v_uv + ts) * 0.1945946;
    color += texture(u_tex, v_uv - ts) * 0.1945946;
    color += texture(u_tex, v_uv + ts * 2.0) * 0.1216216;
    color += texture(u_tex, v_uv - ts * 2.0) * 0.1216216;
    color += texture(u_tex, v_uv + ts * 3.0) * 0.054054;
    color += texture(u_tex, v_uv - ts * 3.0) * 0.054054;
    color += texture(u_tex, v_uv + ts * 4.0) * 0.016216;
    color += texture(u_tex, v_uv - ts * 4.0) * 0.016216;
    f_color = vec4(color.rgb, 1.0);
}
'''

GL_BLOOM_UP_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_bloom;
uniform sampler2D u_scene;
void main() {
    vec3 bloom = texture(u_bloom, v_uv).rgb;
    vec3 scene = texture(u_scene, v_uv).rgb;
    f_color = vec4(scene + bloom * 0.8, 1.0);
}
'''

GL_GOD_RAYS_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform vec2 u_sun_pos;
uniform float u_time;
void main() {
    vec2 dir = v_uv - u_sun_pos;
    float dist = length(dir);
    if (dist < 0.001) { f_color = vec4(0.0); return; }
    dir = normalize(dir);
    float rays = 0.0;
    for (int i = 0; i < 12; i++) {
        float ang = 0.5236 * float(i) + sin(u_time * 0.15 + float(i)) * 0.12;
        vec2 rd = vec2(cos(ang + u_time * 0.5), sin(ang + u_time * 0.5));
        float d = abs(dot(dir, rd));
        rays += pow(d, 8.0) * max(0.0, 1.0 - dist * 0.5);
    }
    rays *= max(0.0, 1.0 - dist * 0.8);
    f_color = vec4(vec3(0.78, 0.86, 1.0) * rays * 0.35, rays * 0.3);
}
'''

GL_WATER_VS = '''
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
out float v_wave;
uniform float u_time;
uniform float u_amp_scale;
void main() {
    vec2 p = in_pos;
    float wave = sin(p.y * 0.04 + u_time * 0.6) * 2.0
               + sin(p.y * 0.07 + u_time * 0.9 + 1.0) * 1.2
               + sin(p.y * 0.02 + u_time * 0.3 + 2.5) * 0.6;
    p.y += wave * u_amp_scale;
    gl_Position = vec4((p.x / 640.0) - 1.0, -((p.y / 400.0) - 1.0), 0.0, 1.0);
    v_uv = in_uv;
    v_wave = wave;
}
'''

GL_WATER_FS = '''
#version 330
in vec2 v_uv;
in float v_wave;
out vec4 f_color;
uniform float u_time;
const vec3 WC1 = vec3(0.024, 0.078, 0.196);
const vec3 WC2 = vec3(0.047, 0.137, 0.275);
const vec3 WH = vec3(0.196, 0.510, 0.784);
void main() {
    float t = v_uv.y;
    vec3 c = mix(WC1, WC2, t);
    float fresnel = 0.3 + 0.7 * pow(1.0 - abs(t - 0.5) * 2.0, 2.0);
    float a = 190.0 * fresnel / 255.0;
    float hl = 0.0;
    if (int(v_uv.x * 100.0) % 4 == 0) {
        hl = 50.0 * fresnel * (0.5 + 0.5 * sin(u_time * 1.2 + v_uv.y * 50.0));
    }
    c += WH * hl / 255.0;
    f_color = vec4(c, a);
}
'''
