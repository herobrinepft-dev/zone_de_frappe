#version 330
#include "common.glsl"

in vec3 v_wpos;
in vec3 v_normal;
in vec2 v_uv;
in vec3 v_color;
flat in int v_layer;
flat in float v_seed;

uniform sampler2DArray u_albedo;
uniform sampler2DArray u_normalmap;
uniform sampler2DShadow u_shadow;

uniform float u_matRough[32];
uniform float u_matMetal[32];
uniform float u_matEmis[32];
uniform float u_matFlags[32];

uniform mat4 u_lightvp;
uniform vec3 u_camPos;
uniform vec3 u_tint;          // teinte cosmétique (couches teintables)
uniform vec3 u_emisTint;      // couleur des émissifs pour cet objet
uniform float u_emisScale;
uniform float u_flash;        // flash d'impact (blanc)
uniform float u_wetness;
uniform float u_windowLights;
uniform float u_shadowTexel;
uniform int u_pcf;
uniform float u_ambient;
uniform int u_numLights;
uniform vec4 u_lightPos[24];  // xyz position, w rayon
uniform vec3 u_lightCol[24];

out vec4 f_color;

mat3 cotangent_frame(vec3 N, vec3 p, vec2 uv) {
    vec3 dp1 = dFdx(p);
    vec3 dp2 = dFdy(p);
    vec2 duv1 = dFdx(uv);
    vec2 duv2 = dFdy(uv);
    vec3 dp2perp = cross(dp2, N);
    vec3 dp1perp = cross(N, dp1);
    vec3 T = dp2perp * duv1.x + dp1perp * duv2.x;
    vec3 B = dp2perp * duv1.y + dp1perp * duv2.y;
    float invmax = inversesqrt(max(max(dot(T, T), dot(B, B)), 1e-12));
    return mat3(T * invmax, B * invmax, N);
}

float D_GGX(float NdH, float a) {
    float a2 = a * a;
    float d = NdH * NdH * (a2 - 1.0) + 1.0;
    return a2 / (PI * d * d + 1e-6);
}

float G_Smith(float NdV, float NdL, float r) {
    float k = (r + 1.0) * (r + 1.0) / 8.0;
    float gv = NdV / (NdV * (1.0 - k) + k);
    float gl = NdL / (NdL * (1.0 - k) + k);
    return gv * gl;
}

vec3 F_Schlick(float c, vec3 f0) {
    return f0 + (1.0 - f0) * pow(1.0 - c, 5.0);
}

vec3 brdf(vec3 N, vec3 V, vec3 Ld, vec3 albedo, float rough, float metal, vec3 f0) {
    vec3 H = normalize(V + Ld);
    float NdL = max(dot(N, Ld), 0.0);
    float NdV = max(dot(N, V), 1e-4);
    float NdH = max(dot(N, H), 0.0);
    rough = max(rough, 0.09);   // évite les pics spéculaires infinis
    float a = rough * rough;
    vec3 F = F_Schlick(max(dot(H, V), 0.0), f0);
    vec3 spec = D_GGX(NdH, a) * G_Smith(NdV, NdL, rough) * F / (4.0 * NdV * NdL + 1e-4);
    vec3 kd = (1.0 - F) * (1.0 - metal);
    return (kd * albedo / PI + spec) * NdL;
}

float shadow_factor(vec3 wpos, vec3 N) {
    float ndl = dot(N, u_sunDir);
    vec3 p = wpos + N * (0.04 + 0.12 * (1.0 - abs(ndl)));
    vec4 lp = u_lightvp * vec4(p, 1.0);
    vec3 sc = lp.xyz / lp.w * 0.5 + 0.5;
    if (sc.x < 0.0 || sc.x > 1.0 || sc.y < 0.0 || sc.y > 1.0 || sc.z > 1.0) return 1.0;
    float bias = 0.0006;
    float s = 0.0;
    float n = 0.0;
    for (int x = -u_pcf; x <= u_pcf; x++) {
        for (int y = -u_pcf; y <= u_pcf; y++) {
            s += texture(u_shadow, vec3(sc.xy + vec2(x, y) * u_shadowTexel, sc.z - bias));
            n += 1.0;
        }
    }
    float edge = max(abs(sc.x - 0.5), abs(sc.y - 0.5));
    return mix(s / n, 1.0, smoothstep(0.42, 0.5, edge));
}

void main() {
    int flags = int(u_matFlags[v_layer] + 0.5);
    vec4 alb = texture(u_albedo, vec3(v_uv, float(v_layer)));
    if ((flags & 1) != 0 && alb.a < 0.5) discard;
    vec4 nmr = texture(u_normalmap, vec3(v_uv, float(v_layer)));

    vec3 albedo = pow(alb.rgb, vec3(2.2)) * v_color;
    if ((flags & 4) != 0) albedo *= u_tint;
    float rough = clamp(u_matRough[v_layer] * (0.5 + nmr.b), 0.03, 1.0);
    float metal = clamp(u_matMetal[v_layer] * nmr.a, 0.0, 1.0);

    vec3 Ng = normalize(v_normal);
    if (!gl_FrontFacing && (flags & 1) != 0) Ng = -Ng;
    vec3 V = normalize(u_camPos - v_wpos);
    if (dot(Ng, V) < 0.0 && (flags & 1) == 0) Ng = -Ng;
    vec3 tn = vec3(nmr.rg * 2.0 - 1.0, 0.0);
    tn.z = sqrt(max(1.0 - dot(tn.xy, tn.xy), 0.0));
    vec3 N = normalize(cotangent_frame(Ng, v_wpos, v_uv) * tn);
    if ((flags & 1) != 0) N = normalize(Ng + vec3(0.0, 0.6, 0.0));

    vec3 emission = vec3(0.0);
    float f0s = 0.04;

    // Façades : vitres réfléchissantes + fenêtres éclairées la nuit
    if ((flags & 16) != 0) {
        float g = alb.a;
        rough = mix(rough, 0.05, g);
        metal = mix(metal, 0.0, g);
        N = normalize(mix(N, Ng, g));
        f0s = mix(0.04, 0.09, g);
        vec2 cell = floor(v_uv * vec2(4.0, 2.0));
        float seed = v_seed;
        float h = hash12(cell + seed);
        float h2 = hash12(cell * 1.7 + seed + 4.1);
        float lit = step(h, 0.42) * u_windowLights;
        vec3 wc = mix(vec3(1.0, 0.72, 0.42), vec3(0.75, 0.85, 1.0), step(0.7, h2));
        // léger dégradé intérieur (rideaux / plafond)
        float inner = 0.55 + 0.45 * smoothstep(0.0, 1.0, fract(v_uv.y * 2.0));
        float dimmer = (h2 < 0.35) ? 0.35 : 1.0;   // certaines pièces faiblement éclairées
        emission += g * lit * wc * inner * dimmer * (0.6 + 0.6 * h2);
    }

    // Sol mouillé : assombrissement + flaques réfléchissantes
    if ((flags & 8) != 0 && u_wetness > 0.0 && Ng.y > 0.6) {
        float puddle = smoothstep(0.45, 0.65, vnoise(v_wpos.xz * 0.18) * 0.7 + vnoise(v_wpos.xz * 0.9) * 0.3);
        float w = u_wetness * (0.45 + 0.55 * puddle);
        albedo *= mix(1.0, 0.45, w);
        rough = mix(rough, 0.04, w);
        N = normalize(mix(N, Ng, puddle * u_wetness));
        // gouttes : petites ondulations animées
        float rip = vnoise(v_wpos.xz * 6.0 + u_time * 3.0);
        N = normalize(N + vec3(rip - 0.5, 0.0, vnoise(v_wpos.zx * 6.0 - u_time * 3.0) - 0.5) * 0.08 * puddle * u_wetness);
    }

    if ((flags & 32) != 0) {
        emission += albedo * u_emisTint * u_matEmis[v_layer] * u_emisScale * alb.a;
    }

    vec3 f0 = mix(vec3(f0s), albedo, metal);

    // Lumière principale
    float sh = shadow_factor(v_wpos, Ng);
    vec3 color = brdf(N, V, u_sunDir, albedo, rough, metal, f0) * u_sunColor * sh;

    // Lumières ponctuelles
    for (int i = 0; i < u_numLights; i++) {
        vec3 d = u_lightPos[i].xyz - v_wpos;
        float dist = length(d);
        float r = u_lightPos[i].w;
        if (dist > r) continue;
        float att = pow(clamp(1.0 - pow(dist / r, 4.0), 0.0, 1.0), 2.0) / (dist * dist + 1.0);
        color += brdf(N, V, d / dist, albedo, rough, metal, f0) * u_lightCol[i] * att;
    }

    // Ambiance : hémisphère ciel/sol + occlusion approximative en pied d'immeuble
    float ao = mix(0.45, 1.0, smoothstep(0.0, 7.0, v_wpos.y + 0.6 * N.y));
    vec3 hemi = mix(u_groundColor * 0.6, mix(u_skyHorizon, u_skyZenith, 0.5), N.y * 0.5 + 0.5);
    vec3 F = F_Schlick(max(dot(N, V), 0.0), f0);
    vec3 kd = (1.0 - F) * (1.0 - metal);
    color += kd * albedo * hemi * ao * u_ambient;

    // Réflexion de l'environnement (ciel analytique)
    vec3 R = reflect(-V, N);
    vec3 env = sky_color(normalize(vec3(R.x, max(R.y, -0.2), R.z)));
    float specOcc = (R.y < 0.0) ? 0.35 : 1.0;
    float gloss = pow(1.0 - rough, 2.0);
    color += env * F * gloss * ao * specOcc * u_ambient * 1.2;

    color += emission;
    color += u_flash * vec3(1.0, 0.85, 0.7);
    // garde-fou HDR (le tampon est en float16)
    color = clamp(color, vec3(0.0), vec3(300.0));
    if (any(isnan(color))) color = vec3(0.0);
    f_color = vec4(color, 1.0);
#ifdef VIEWMODEL
    gl_FragDepth = gl_FragCoord.z * 0.02;
#endif
}
