// ---- Atmosphère partagée -------------------------------------------------
uniform vec3 u_sunDir;       // direction VERS la lumière principale (soleil ou lune)
uniform vec3 u_sunColor;     // radiance de la lumière principale
uniform vec3 u_trueSunDir;   // direction réelle du soleil (pour le ciel)
uniform vec3 u_skyZenith;
uniform vec3 u_skyHorizon;
uniform vec3 u_groundColor;
uniform float u_night;
uniform float u_time;

const float PI = 3.14159265;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float hash13(vec3 p3) {
    p3 = fract(p3 * 0.1031);
    p3 += dot(p3, p3.zyx + 31.32);
    return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec3 sky_color(vec3 dir) {
    float y = dir.y;
    float h = pow(1.0 - clamp(y, 0.0, 1.0), 3.0);
    vec3 col = mix(u_skyZenith, u_skyHorizon, h);
    if (y < 0.0) col = mix(u_skyHorizon, u_groundColor, clamp(-y * 3.0, 0.0, 1.0));
    float sd = max(dot(dir, u_trueSunDir), 0.0);
    vec3 sunTint = u_sunColor * (1.0 - u_night);
    col += sunTint * (pow(sd, 6.0) * 0.12 + pow(sd, 48.0) * 0.35);
    return col;
}
