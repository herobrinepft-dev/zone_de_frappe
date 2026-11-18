#version 330
#include "common.glsl"

in vec2 v_uv;
uniform sampler2D u_color;
uniform sampler2D u_depth;
uniform sampler2D u_bloom;
uniform sampler2DShadow u_shadow;

uniform mat4 u_invViewProj;
uniform mat4 u_lightvp;
uniform vec3 u_camPos;
uniform vec3 u_fogColor;
uniform float u_fogDensity;
uniform float u_fogFalloff;
uniform int u_volSteps;
uniform float u_volStrength;
uniform float u_exposure;
uniform float u_bloomStrength;
uniform int u_useBloom;
uniform int u_studio;
uniform int u_clouds;
uniform float u_cloudCover;
uniform float u_lightning;
uniform float u_damage;
uniform float u_lowHealth;
uniform float u_fade;
uniform vec2 u_resolution;

out vec4 f_color;

float fbm(vec2 p) {
    float s = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) {
        s += vnoise(p) * a;
        p = p * 2.03 + vec2(1.7, 9.2);
        a *= 0.5;
    }
    return s;
}

vec3 sky_full(vec3 dir) {
    vec3 col = sky_color(dir);
    float sd = dot(dir, u_trueSunDir);
    float day = 1.0 - u_night;
    col += u_sunColor * smoothstep(0.99935, 0.9997, sd) * 18.0 * day * (1.0 - u_cloudCover * 0.8);
    vec3 moonDir = normalize(vec3(-u_trueSunDir.x, abs(u_trueSunDir.y) + 0.25, -u_trueSunDir.z));
    float md = dot(dir, moonDir);
    col += vec3(0.75, 0.82, 1.0) * smoothstep(0.9992, 0.9995, md) * 1.6 * u_night;
    col += vec3(0.3, 0.35, 0.5) * pow(max(md, 0.0), 200.0) * 0.4 * u_night;
    if (u_night > 0.01 && dir.y > 0.0) {
        vec3 d = dir * 420.0;
        float s = hash13(floor(d));
        float tw = 0.6 + 0.4 * sin(u_time * 3.0 + s * 100.0);
        col += vec3(0.9, 0.95, 1.0) * step(0.9982, s) * u_night * tw * 1.5 * (1.0 - u_cloudCover) * smoothstep(0.0, 0.2, dir.y);
    }
    if (u_clouds == 1 && dir.y > 0.0) {
        float t = (1600.0 - u_camPos.y) / max(dir.y, 0.02);
        vec2 p = (u_camPos.xz + dir.xz * t) * 0.00028 + vec2(u_time * 0.006, u_time * 0.002);
        float n = fbm(p);
        float cov = u_cloudCover;
        float c = smoothstep(0.62 - cov * 0.45, 0.85 - cov * 0.3, n);
        float n2 = fbm(p * 1.7 + vec2(u_trueSunDir.x, u_trueSunDir.z) * 0.08);
        float light = clamp(1.0 - (n2 - n) * 2.5 - cov * 0.4, 0.15, 1.0);
        vec3 shadowCol = mix(u_skyZenith, u_skyHorizon, 0.6) * 0.75;
        vec3 litCol = u_skyHorizon * 0.8 + u_sunColor * 0.35 * day;
        vec3 cc = mix(shadowCol, litCol, light);
        cc *= mix(1.0, 0.45, smoothstep(0.65, 1.0, cov));
        float sun_edge = pow(max(sd, 0.0), 12.0) * day;
        cc += u_sunColor * sun_edge * 0.6 * (1.0 - c);
        float fade = smoothstep(0.0, 0.18, dir.y);
        col = mix(col, cc, c * fade * 0.97);
    }
    col += vec3(0.6, 0.65, 0.9) * u_lightning * 2.5 * (0.4 + 0.6 * max(dir.y, 0.0));
    return col;
}

float phaseHG(float c, float g) {
    float g2 = g * g;
    return (1.0 - g2) / (4.0 * PI * pow(1.0 + g2 - 2.0 * g * c, 1.5));
}

vec3 aces(vec3 x) {
    const float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

float ign(vec2 p) {
    return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

void main() {
    float depth = texture(u_depth, v_uv).r;
    vec4 ndc = vec4(v_uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
    vec4 wp4 = u_invViewProj * ndc;
    vec3 wp = wp4.xyz / wp4.w;
    vec4 farp = u_invViewProj * vec4(ndc.xy, 1.0, 1.0);
    vec3 dir = normalize(farp.xyz / farp.w - u_camPos);

    vec3 color;
    bool sky = depth >= 0.99999;
    float dist;
    if (sky) {
        if (u_studio == 1) {
            float r = length((v_uv - vec2(0.5, 0.42)) * vec2(u_resolution.x / u_resolution.y, 1.0));
            color = mix(vec3(0.05, 0.045, 0.04), vec3(0.008, 0.009, 0.012), smoothstep(0.0, 0.9, r));
            color += vec3(0.25, 0.12, 0.03) * exp(-pow((v_uv.y - 0.25) * 6.0, 2.0)) * 0.3;
        } else {
            color = sky_full(dir);
        }
        dist = 3000.0;
    } else {
        color = texture(u_color, v_uv).rgb;
        dist = length(wp - u_camPos);
    }

    if (u_studio == 0) {
        // Brouillard de hauteur analytique
        float b = u_fogFalloff;
        float a = u_fogDensity;
        float dy = dir.y;
        float fogAmt;
        float effDist = sky ? 2200.0 : dist;
        if (abs(dy) < 1e-3) fogAmt = a * exp(-u_camPos.y * b) * effDist;
        else fogAmt = a * exp(-u_camPos.y * b) * (1.0 - exp(-effDist * dy * b)) / (dy * b);
        float fog = 1.0 - exp(-max(fogAmt, 0.0));
        if (sky) fog *= 0.85;
        float sunAmt = pow(max(dot(dir, u_sunDir), 0.0), 8.0);
        vec3 fogCol = u_fogColor + u_sunColor * sunAmt * 0.12;
        color = mix(color, fogCol, fog);

        // Lumière volumétrique : marche dans la shadow map
        if (u_volSteps > 0) {
            float maxD = min(dist, 140.0);
            float stepLen = maxD / float(u_volSteps);
            float jitter = ign(gl_FragCoord.xy + vec2(u_time * 60.0, 0.0));
            float acc = 0.0;
            for (int i = 0; i < u_volSteps; i++) {
                float t = (float(i) + jitter) * stepLen;
                vec3 p = u_camPos + dir * t;
                vec4 lp = u_lightvp * vec4(p, 1.0);
                vec3 sc = lp.xyz / lp.w * 0.5 + 0.5;
                float lit = 1.0;
                if (sc.x > 0.0 && sc.x < 1.0 && sc.y > 0.0 && sc.y < 1.0 && sc.z < 1.0)
                    lit = texture(u_shadow, vec3(sc.xy, sc.z - 0.001));
                float dens = exp(-max(p.y, 0.0) * 0.03);
                acc += lit * dens * stepLen;
            }
            float ph = phaseHG(dot(dir, u_sunDir), 0.6);
            color += u_sunColor * acc * ph * u_volStrength;
        }
    }

    if (u_useBloom == 1) color += texture(u_bloom, v_uv).rgb * u_bloomStrength;

    color *= u_exposure;
    color = aces(color);
    color = pow(color, vec3(1.0 / 2.2));

    // étalonnage léger : contraste
    color = mix(vec3(0.5), color, 1.06);
    float lum = dot(color, vec3(0.299, 0.587, 0.114));
    color = mix(vec3(lum), color, 1.0 - u_lowHealth * 0.55);

    vec2 q = v_uv - 0.5;
    float vig = 1.0 - dot(q, q) * 0.55;
    color *= vig;
    float edge = smoothstep(0.25, 0.75, length(q * vec2(1.2, 1.0)));
    color = mix(color, vec3(0.75, 0.04, 0.02), edge * clamp(u_damage, 0.0, 1.0) * 0.75);
    color = mix(color, vec3(0.45, 0.0, 0.0), edge * u_lowHealth * (0.25 + 0.15 * sin(u_time * 5.0)));
    color *= u_fade;

    // dithering pour éviter le banding
    color += (ign(gl_FragCoord.xy) - 0.5) / 255.0;
    f_color = vec4(clamp(color, 0.0, 1.0), dot(color, vec3(0.299, 0.587, 0.114)));
}
