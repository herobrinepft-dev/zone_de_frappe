#version 330
in vec2 in_corner;
in vec3 i_pos;
in vec3 i_axis;
in float i_size;
in vec4 i_color;
in float i_kind;

uniform mat4 u_viewproj;
uniform vec3 u_camPos;
uniform vec3 u_camRight;
uniform vec3 u_camUp;

out vec2 v_corner;
out vec4 v_color;
flat out int v_kind;

void main() {
    vec3 p;
    float al = length(i_axis);
    if (al > 1e-5) {
        // billboard axial (traînées, rayons, pluie)
        vec3 toCam = normalize(u_camPos - i_pos);
        vec3 side = normalize(cross(i_axis / al, toCam));
        p = i_pos + i_axis * in_corner.y + side * in_corner.x * i_size;
    } else {
        p = i_pos + (u_camRight * in_corner.x + u_camUp * in_corner.y) * i_size;
    }
    v_corner = in_corner;
    v_color = i_color;
    v_kind = int(i_kind + 0.5);
    gl_Position = u_viewproj * vec4(p, 1.0);
}
