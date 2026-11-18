#version 330
in vec2 v_uv;
uniform sampler2D u_tex;
uniform int u_flip;
out vec4 f_color;
void main() {
    // Interface pygame (alpha non prémultiplié) composée au-dessus de la scène 3D.
    vec2 uv = (u_flip == 1) ? vec2(v_uv.x, 1.0 - v_uv.y) : v_uv;
    f_color = texture(u_tex, uv);
}
