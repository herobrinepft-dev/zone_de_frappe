#version 330
in vec2 v_uv;
flat in int v_layer;
uniform sampler2DArray u_albedo;
uniform float u_matFlags[32];
out vec4 f_color;

void main() {
    int flags = int(u_matFlags[v_layer] + 0.5);
    if ((flags & 1) != 0) {
        if (texture(u_albedo, vec3(v_uv, float(v_layer))).a < 0.5) discard;
    }
    if ((flags & 32) != 0 && (flags & 16) == 0) {
        // les surfaces purement émissives ne projettent pas d'ombre
        discard;
    }
    f_color = vec4(1.0);
}
