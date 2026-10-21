"""Parameters print_node can change while running (no relaunch).

Everything here is pure (numpy only) so it is testable without ROS. The
node's ``add_on_set_parameters_callback`` uses ``validate_updates`` to
accept or reject a batch and ``RuntimeConfig.apply`` to rebuild the
derived objects (print frame, home pose, velocity profile, z-hop, tool
offset). Changes are only accepted while no print is running: the planned
trajectory of a running print was computed with the old values, and
swapping the frame or the speed envelope under it would be unsafe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Optional

import numpy as np

# name → (kind, length or None, min, max)
HOT_PARAMS: dict[str, tuple[str, Optional[int], float, float]] = {
    'max_print_velocity': ('float', None, 0.001, 0.5),
    'max_travel_velocity': ('float', None, 0.001, 1.0),
    'max_acceleration': ('float', None, 0.01, 5.0),
    'corner_blend_radius': ('float', None, 0.0, 0.02),
    'singularity_velocity_scale': ('float', None, 0.05, 1.0),
    'z_hop_enabled': ('bool', None, 0, 1),
    'z_hop_height': ('float', None, 0.0, 0.05),
    'print_origin_xyz': ('vec', 3, -2.0, 2.0),
    'print_origin_rpy': ('vec', 3, -2 * math.pi, 2 * math.pi),
    'bed_tilt_rx': ('float', None, -0.2, 0.2),
    'bed_tilt_ry': ('float', None, -0.2, 0.2),
    'home_joints': ('vec', 6, -2 * math.pi, 2 * math.pi),
    'tool_offset_xyz': ('vec', 3, -0.3, 0.6),
    'tool_offset_rpy': ('vec', 3, -2 * math.pi, 2 * math.pi),
}


def _rpy_to_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ])


def build_print_frame(xyz, rpy, tilt_rx: float = 0.0, tilt_ry: float = 0.0) -> np.ndarray:
    """G-code origin → robot base, with bed tilt applied about X then Y."""
    frame = np.eye(4)
    frame[:3, :3] = _rpy_to_matrix(*rpy)
    frame[:3, 3] = np.asarray(xyz, dtype=float)
    if abs(tilt_rx) > 1e-9 or abs(tilt_ry) > 1e-9:
        tilt = np.eye(4)
        tilt[:3, :3] = _rpy_to_matrix(0.0, tilt_ry, 0.0) @ _rpy_to_matrix(tilt_rx, 0.0, 0.0)
        frame = frame @ tilt
    return frame


def build_tool_offset(xyz, rpy) -> np.ndarray:
    t = np.eye(4)
    t[:3, :3] = _rpy_to_matrix(*rpy)
    t[:3, 3] = np.asarray(xyz, dtype=float)
    return t


def validate_value(name: str, value: Any) -> Optional[str]:
    """None when acceptable, else the reason."""
    if name not in HOT_PARAMS:
        return None  # not ours to judge (static params are read-only anyway)
    kind, length, lo, hi = HOT_PARAMS[name]
    if kind == 'bool':
        return None if isinstance(value, bool) else f'{name} must be a bool'
    if kind == 'float':
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f'{name} must be a number'
        if not (lo <= float(value) <= hi) or not math.isfinite(float(value)):
            return f'{name}={value} outside [{lo}, {hi}]'
        return None
    try:
        vec = [float(v) for v in value]
    except (TypeError, ValueError):
        return f'{name} must be a list of numbers'
    if len(vec) != length:
        return f'{name} needs {length} values, got {len(vec)}'
    if any(not math.isfinite(v) or not lo <= v <= hi for v in vec):
        return f'{name} values must be within [{lo:.3g}, {hi:.3g}]'
    return None


def validate_updates(updates: dict[str, Any], busy: bool) -> Optional[str]:
    """Reason to reject the batch, or None."""
    hot = {k: v for k, v in updates.items() if k in HOT_PARAMS}
    if not hot:
        return None
    if busy:
        return 'print in progress: settings apply once the printer is idle'
    for k, v in hot.items():
        why = validate_value(k, v)
        if why:
            return why
    return None


@dataclass
class RuntimeConfig:
    """Current values of every hot parameter, plus the derived objects."""

    values: dict[str, Any] = field(default_factory=dict)

    def merged(self, updates: dict[str, Any]) -> dict[str, Any]:
        out = dict(self.values)
        out.update({k: v for k, v in updates.items() if k in HOT_PARAMS})
        return out

    def print_frame(self, v: Optional[dict[str, Any]] = None) -> np.ndarray:
        v = v or self.values
        return build_print_frame(v['print_origin_xyz'], v['print_origin_rpy'],
                                 v.get('bed_tilt_rx', 0.0), v.get('bed_tilt_ry', 0.0))

    def tool_offset(self, v: Optional[dict[str, Any]] = None) -> np.ndarray:
        v = v or self.values
        return build_tool_offset(v['tool_offset_xyz'], v['tool_offset_rpy'])

    @staticmethod
    def profiler_kwargs(v: dict[str, Any]) -> dict[str, float]:
        return {k: float(v[k]) for k in (
            'max_print_velocity', 'max_travel_velocity', 'max_acceleration',
            'corner_blend_radius') if k in v}
