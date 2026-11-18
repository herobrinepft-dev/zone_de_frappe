#version 330
in vec3 in_pos;
in vec3 in_normal;
in vec2 in_uv;
in float in_layer;
in vec3 in_color;

uniform mat4 u_model;
uniform mat4 u_viewproj;
uniform float u_time;
uniform float u_wind;
uniform float u_matFlags[32];

out vec3 v_wpos;
out vec3 v_normal;
out vec2 v_uv;
out vec3 v_color;
flat out int v_layer;
flat out float v_seed;

void main() {
    v_seed = floor(dot(in_color, vec3(127.1, 311.7, 74.7)) * 8.0) * 0.125;
    vec4 wp = u_model * vec4(in_pos, 1.0);
    int layer = int(in_layer + 0.5);
    int flags = int(u_matFlags[layer] + 0.5);
    if ((flags & 2) != 0) {
        float h = clamp(in_pos.y, 0.0, 6.0);
        float s = sin(u_time * 1.6 + wp.x * 0.31 + wp.z * 0.23) * 0.6 + sin(u_time * 3.7 + wp.x * 1.3 + wp.y) * 0.25;
        wp.xz += vec2(s, s * 0.7) * u_wind * 0.035 * h;
    }
    v_wpos = wp.xyz;
    v_normal = mat3(u_model) * in_normal;
    v_uv = in_uv;
    v_color = in_color;
    v_layer = layer;
    gl_Position = u_viewproj * wp;
}
