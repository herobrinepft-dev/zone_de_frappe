#version 330
in vec2 v_uv;
uniform sampler2D u_tex;
uniform vec2 u_dir;   // direction * taille du texel
out vec4 f_color;

void main() {
    // flou gaussien 9 taps via échantillonnage linéaire
    vec3 c = texture(u_tex, v_uv).rgb * 0.2270270270;
    c += texture(u_tex, v_uv + u_dir * 1.3846153846).rgb * 0.3162162162;
    c += texture(u_tex, v_uv - u_dir * 1.3846153846).rgb * 0.3162162162;
    c += texture(u_tex, v_uv + u_dir * 3.2307692308).rgb * 0.0702702703;
    c += texture(u_tex, v_uv - u_dir * 3.2307692308).rgb * 0.0702702703;
    f_color = vec4(c, 1.0);
}
