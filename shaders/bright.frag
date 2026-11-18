#version 330
in vec2 v_uv;
uniform sampler2D u_color;
uniform vec2 u_texel;
uniform float u_threshold;
out vec4 f_color;

void main() {
    vec3 c = vec3(0.0);
    c += texture(u_color, v_uv + u_texel * vec2(-1.0, -1.0)).rgb;
    c += texture(u_color, v_uv + u_texel * vec2(1.0, -1.0)).rgb;
    c += texture(u_color, v_uv + u_texel * vec2(-1.0, 1.0)).rgb;
    c += texture(u_color, v_uv + u_texel * vec2(1.0, 1.0)).rgb;
    c *= 0.25;
    c = min(c, vec3(40.0));
    float l = max(max(c.r, c.g), c.b);
    float k = max(l - u_threshold, 0.0) / max(l, 1e-4);
    f_color = vec4(c * k, 1.0);
}
