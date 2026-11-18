#version 330
in vec2 v_corner;
in vec4 v_color;
flat in int v_kind;
out vec4 f_color;

float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

void main() {
    float r2 = dot(v_corner, v_corner);
    float shape;
    float alpha;
    // Sortie en alpha prémultiplié : blend (ONE, ONE_MINUS_SRC_ALPHA).
    // kind 0 : lueur additive ; 1 : fumée ; 2 : traînée additive ; 3 : pluie (alpha) ; 4 : débris opaques
    if (v_kind == 0) {
        shape = exp(-r2 * 3.5) - 0.03;
        if (shape <= 0.0) discard;
        f_color = vec4(v_color.rgb * v_color.a * shape, 0.0);
    } else if (v_kind == 1) {
        if (r2 > 1.0) discard;
        float n = hash(floor(v_corner * 4.0 + 7.0)) * 0.3 + 0.7;
        shape = (1.0 - r2) * n;
        alpha = v_color.a * shape;
        f_color = vec4(v_color.rgb * alpha, alpha);
    } else if (v_kind == 2) {
        float across = 1.0 - abs(v_corner.x);
        float along = 1.0 - pow(abs(v_corner.y), 4.0);
        shape = across * across * along;
        f_color = vec4(v_color.rgb * v_color.a * shape, 0.0);
    } else if (v_kind == 3) {
        float across = 1.0 - abs(v_corner.x);
        alpha = v_color.a * across * (1.0 - abs(v_corner.y));
        f_color = vec4(v_color.rgb * alpha, alpha);
    } else {
        if (r2 > 0.8) discard;
        f_color = vec4(v_color.rgb, 1.0);
    }
}
