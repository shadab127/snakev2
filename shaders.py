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
uniform vec3 u_light_dir;
uniform float u_ambient;
uniform vec3 u_sun_color;
uniform vec3 u_fog_color;
uniform float u_day_cycle;

const vec3 GAME_OVER_TOP = vec3(0.039, 0.098, 0.078);
const vec3 GAME_OVER_SIDE = vec3(0.024, 0.055, 0.047);
const vec3 TILE_GLOW = vec3(0.314, 0.863, 0.588);
const vec3 TILE_EDGE_EMISSIVE = vec3(0.078, 0.235, 0.118);
const vec3 SUNSET_TINT = vec3(1.0, 0.7, 0.4);

void main() {
    vec3 base_c = v_base_color;
    bool is_side = v_normal.z < 0.5;
    if (u_game_over == 1) {
        if (v_normal.z > 0.5) {
            base_c = GAME_OVER_TOP;
        } else {
            base_c = GAME_OVER_SIDE;
        }
    } else if (u_eat_flash > 0.0) {
        float flash = min(1.0, u_eat_flash / 0.2);
        vec3 flash_c = TILE_GLOW * 0.3;
        base_c = mix(base_c, flash_c, flash * 0.5);
        base_c += TILE_EDGE_EMISSIVE * flash * 0.5;
    }

    float sun_factor = 0.85 + 0.15 * sin(u_time_float * 0.03 + v_q * 0.5 + v_r * 0.3);
    float diff = max(0.0, dot(v_normal, u_light_dir));
    float light = (u_ambient + (1.0 - u_ambient) * diff) * sun_factor * v_dist_factor * v_ao;

    vec3 color = base_c * light;

    // Rim lighting (stronger on side faces facing away from light)
    if (is_side) {
        float rim = max(0.0, 1.0 - abs(dot(v_normal, u_light_dir)));
        rim = pow(rim, 2.0) * 0.15;
        color += vec3(rim * 0.5, rim * 0.7, rim * 0.5);
    }

    // Top face specular highlight
    if (v_normal.z > 0.5) {
        float spec = max(0.0, dot(v_normal, u_light_dir));
        spec = pow(spec, 8.0) * 0.08;
        color += vec3(spec);
    }

    // Sunset/dusk warm tint
    float day_t = u_day_cycle;
    if (day_t < 0.3 && day_t > -0.3) {
        float warm_t = 1.0 - abs(day_t) / 0.3;
        color = mix(color, color * SUNSET_TINT, warm_t * 0.15);
    }

    float fog_t = clamp((v_fog_depth - 350.0) / 850.0, 0.0, 1.0);
    color = mix(color, u_fog_color, fog_t * 0.35);
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

GL_BLOOM_DOWN_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
uniform vec2 u_texel_size;
uniform float u_bloom_threshold;
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
    float bright = max(0.0, luma - u_bloom_threshold);
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

GL_TONE_MAP_FS = '''
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
const float A = 0.22;
const float B = 0.30;
const float C = 0.10;
const float D = 0.20;
const float E = 0.01;
const float F = 0.30;
const float W = 11.2;
vec3 uncharted2(vec3 x) {
    return ((x * (A * x + C * B) + D * E) / (x * (A * x + B) + D * F)) - E / F;
}
void main() {
    vec3 color = texture(u_tex, v_uv).rgb;
    vec3 mapped = uncharted2(color * 1.6) / uncharted2(vec3(W));
    f_color = vec4(clamp(mapped, 0.0, 1.0), 1.0);
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
uniform vec3 u_sun_color;
uniform float u_day_cycle;
void main() {
    if (u_day_cycle < 0.2) { f_color = vec4(0.0); return; }
    vec2 dir = v_uv - u_sun_pos;
    float dist = length(dir);
    if (dist < 0.001) { f_color = vec4(0.0); return; }
    dir = normalize(dir);
    float rays = 0.0;
    for (int i = 0; i < 6; i++) {
        float ang = 1.0472 * float(i) + 0.5236 + sin(u_time * 0.15 + float(i)) * 0.14;
        vec2 rd = vec2(cos(ang + u_time * 0.3), sin(ang + u_time * 0.3));
        float d = abs(dot(dir, rd));
        rays += pow(d, 4.0) * max(0.0, 1.0 - dist * 0.6);
    }
    rays *= max(0.0, 1.0 - dist);
    vec3 ray_color = u_sun_color / 255.0;
    f_color = vec4(ray_color * rays * 0.25, rays * 0.2);
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
uniform vec3 u_water_color;
uniform vec3 u_water_highlight;
void main() {
    float t = v_uv.y;
    vec3 c = mix(u_water_color / 255.0, vec3(0.047, 0.137, 0.275), t);
    float fresnel = 0.3 + 0.7 * pow(1.0 - abs(t - 0.5) * 2.0, 2.0);
    float a = 190.0 * fresnel / 255.0;
    float hl = 0.0;
    if (int(v_uv.x * 100.0) % 4 == 0) {
        hl = 50.0 * fresnel * (0.5 + 0.5 * sin(u_time * 1.2 + v_uv.y * 50.0));
    }
    c += u_water_highlight * hl / 255.0 / 255.0;
    f_color = vec4(c, a);
}
'''
