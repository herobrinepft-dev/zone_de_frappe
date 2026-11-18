"""Caméra première personne (lacet / tangage / roulis)."""
import math
import numpy as np

from engine import mathutils as mu


class Camera:
    def __init__(self):
        self.pos = np.array([0.0, 1.7, 0.0])
        self.yaw = 0.0      # 0 = regarde vers -Z
        self.pitch = 0.0
        self.roll = 0.0
        self.fov = 80.0
        self.near = 0.08
        self.far = 1700.0

    @property
    def forward(self):
        cp = math.cos(self.pitch)
        return np.array([math.sin(self.yaw) * cp, math.sin(self.pitch), -math.cos(self.yaw) * cp])

    @property
    def flat_forward(self):
        return np.array([math.sin(self.yaw), 0.0, -math.cos(self.yaw)])

    @property
    def right(self):
        return np.array([math.cos(self.yaw), 0.0, math.sin(self.yaw)])

    def view(self):
        v = mu.look_at(self.pos, self.pos + self.forward, (0, 1, 0))
        if abs(self.roll) > 1e-5:
            v = mu.rot_z(-self.roll) @ v
        return v

    def proj(self, aspect):
        return mu.perspective(self.fov, aspect, self.near, self.far)

    def look_at_point(self, target):
        d = np.asarray(target, float) - self.pos
        self.yaw = math.atan2(d[0], -d[2])
        self.pitch = math.atan2(d[1], math.hypot(d[0], d[2]))
