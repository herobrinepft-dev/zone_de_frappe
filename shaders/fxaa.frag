#version 330
in vec2 v_uv;
uniform sampler2D u_tex;
uniform vec2 u_texel;
uniform int u_enabled;
out vec4 f_color;

float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }

void main() {
    vec3 rgbM = texture(u_tex, v_uv).rgb;
    if (u_enabled == 0) { f_color = vec4(rgbM, 1.0); return; }
    vec3 rgbNW = texture(u_tex, v_uv + vec2(-1.0, -1.0) * u_texel).rgb;
    vec3 rgbNE = texture(u_tex, v_uv + vec2(1.0, -1.0) * u_texel).rgb;
    vec3 rgbSW = texture(u_tex, v_uv + vec2(-1.0, 1.0) * u_texel).rgb;
    vec3 rgbSE = texture(u_tex, v_uv + vec2(1.0, 1.0) * u_texel).rgb;
    float lNW = luma(rgbNW), lNE = luma(rgbNE), lSW = luma(rgbSW), lSE = luma(rgbSE), lM = luma(rgbM);
    float lMin = min(lM, min(min(lNW, lNE), min(lSW, lSE)));
    float lMax = max(lM, max(max(lNW, lNE), max(lSW, lSE)));
    vec2 dir;
    dir.x = -((lNW + lNE) - (lSW + lSE));
    dir.y = ((lNW + lSW) - (lNE + lSE));
    float dirReduce = max((lNW + lNE + lSW + lSE) * 0.03125, 1.0 / 128.0);
    float rcpDirMin = 1.0 / (min(abs(dir.x), abs(dir.y)) + dirReduce);
    dir = clamp(dir * rcpDirMin, vec2(-8.0), vec2(8.0)) * u_texel;
    vec3 rgbA = 0.5 * (texture(u_tex, v_uv + dir * (1.0 / 3.0 - 0.5)).rgb + texture(u_tex, v_uv + dir * (2.0 / 3.0 - 0.5)).rgb);
    vec3 rgbB = rgbA * 0.5 + 0.25 * (texture(u_tex, v_uv + dir * -0.5).rgb + texture(u_tex, v_uv + dir * 0.5).rgb);
    float lB = luma(rgbB);
    f_color = vec4((lB < lMin || lB > lMax) ? rgbA : rgbB, 1.0);
}
