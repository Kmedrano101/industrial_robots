# Copyright 2024 Kevin Medrano
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Self-Collision Detection for UR Robots

Models each robot link as a capsule (cylinder + hemispherical caps) and checks
for intersections between non-adjacent link pairs.  Includes the tool/extruder
as an additional capsule.

No ROS dependencies — pure Python + NumPy.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ── UR Robot DH Parameters (standard DH convention) ─────────────────────────

UR_DH_PARAMS = {
    'ur3e': {
        'd': [0.15185, 0.0, 0.0, 0.13105, 0.08535, 0.0921],
        'a': [0.0, -0.24355, -0.2132, 0.0, 0.0, 0.0],
        'alpha': [np.pi / 2, 0.0, 0.0, np.pi / 2, -np.pi / 2, 0.0],
    },
    'ur5e': {
        'd': [0.1625, 0.0, 0.0, 0.1333, 0.0997, 0.0996],
        'a': [0.0, -0.425, -0.3922, 0.0, 0.0, 0.0],
        'alpha': [np.pi / 2, 0.0, 0.0, np.pi / 2, -np.pi / 2, 0.0],
    },
    'ur10e': {
        'd': [0.1807, 0.0, 0.0, 0.17415, 0.11985, 0.11655],
        'a': [0.0, -0.6127, -0.57155, 0.0, 0.0, 0.0],
        'alpha': [np.pi / 2, 0.0, 0.0, np.pi / 2, -np.pi / 2, 0.0],
    },
}

# Conservative capsule radii per link (slightly larger than actual geometry).
UR_LINK_RADII = {
    'ur3e': [0.060, 0.045, 0.040, 0.035, 0.035, 0.030],
    'ur5e': [0.075, 0.060, 0.050, 0.045, 0.045, 0.040],
    'ur10e': [0.090, 0.075, 0.065, 0.055, 0.055, 0.050],
}

# Default extruder geometry (FDM nozzle assembly).
EXTRUDER_RADIUS = 0.025   # 25 mm
EXTRUDER_LENGTH = 0.105   # heatsink(60) + heatbreak(30) + nozzle(15) mm

LINK_NAMES = [
    'base_shoulder',
    'shoulder_elbow',
    'elbow_wrist1',
    'wrist1_wrist2',
    'wrist2_wrist3',
    'wrist3_flange',
]


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class Capsule:
    """A capsule defined by two endpoints and a radius."""

    p0: np.ndarray  # (3,) start point
    p1: np.ndarray  # (3,) end point
    radius: float

    @property
    def length(self) -> float:
        return float(np.linalg.norm(self.p1 - self.p0))


@dataclass
class CollisionResult:
    """Result of a collision check for one configuration."""

    has_collision: bool
    min_clearance: float            # metres (negative = penetration)
    collision_pairs: List[Tuple[str, str]] = field(default_factory=list)
    clearances: Dict[Tuple[str, str], float] = field(default_factory=dict)


# ── Geometry Primitives ──────────────────────────────────────────────────────

def _dh_transform(theta: float, d: float, a: float, alpha: float) -> np.ndarray:
    """Compute 4x4 homogeneous DH transformation matrix."""
    ct, st = np.cos(theta), np.sin(theta)
    ca, sa = np.cos(alpha), np.sin(alpha)
    return np.array([
        [ct, -st * ca,  st * sa, a * ct],
        [st,  ct * ca, -ct * sa, a * st],
        [0.0,      sa,       ca,      d],
        [0.0,     0.0,      0.0,    1.0],
    ])


def forward_kinematics_all_links(
    joint_angles: np.ndarray,
    dh_params: Optional[Dict] = None,
) -> List[np.ndarray]:
    """Compute transforms for all link frames (base through flange).

    Returns list of 7 transforms [T_base, T_0, T_1, ..., T_5] where each
    is a 4x4 homogeneous matrix expressed in the base frame.
    """
    if dh_params is None:
        dh_params = UR_DH_PARAMS['ur5e']

    transforms = [np.eye(4)]  # T_base
    T = np.eye(4)

    for i in range(6):
        Ti = _dh_transform(
            joint_angles[i],
            dh_params['d'][i],
            dh_params['a'][i],
            dh_params['alpha'][i],
        )
        T = T @ Ti
        transforms.append(T.copy())

    return transforms


def segment_segment_distance(
    p0: np.ndarray, p1: np.ndarray,
    q0: np.ndarray, q1: np.ndarray,
) -> Tuple[float, float, float]:
    """Minimum distance between two line segments.

    Segments:  P(s) = p0 + s*(p1-p0),  s in [0,1]
               Q(t) = q0 + t*(q1-q0),  t in [0,1]

    Returns (distance, s_closest, t_closest).
    """
    d1 = p1 - p0
    d2 = q1 - q0
    r = p0 - q0

    a = float(np.dot(d1, d1))
    e = float(np.dot(d2, d2))
    f = float(np.dot(d2, r))

    EPS = 1e-10

    if a <= EPS and e <= EPS:
        return float(np.linalg.norm(r)), 0.0, 0.0

    if a <= EPS:
        s = 0.0
        t = np.clip(f / e, 0.0, 1.0)
    else:
        c = float(np.dot(d1, r))
        if e <= EPS:
            t = 0.0
            s = np.clip(-c / a, 0.0, 1.0)
        else:
            b = float(np.dot(d1, d2))
            denom = a * e - b * b

            s = np.clip((b * f - c * e) / denom, 0.0, 1.0) if abs(denom) > EPS else 0.0

            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0
                s = np.clip(-c / a, 0.0, 1.0)
            elif t > 1.0:
                t = 1.0
                s = np.clip((b - c) / a, 0.0, 1.0)

    closest_p = p0 + s * d1
    closest_q = q0 + t * d2
    return float(np.linalg.norm(closest_p - closest_q)), float(s), float(t)


def capsule_distance(cap_a: Capsule, cap_b: Capsule) -> float:
    """Minimum distance between two capsules (negative = penetration)."""
    dist, _, _ = segment_segment_distance(cap_a.p0, cap_a.p1, cap_b.p0, cap_b.p1)
    return dist - cap_a.radius - cap_b.radius


# ── Self-Collision Checker ───────────────────────────────────────────────────

class SelfCollisionChecker:
    """Self-collision detection for UR robots using capsule approximation.

    Models each robot link as a capsule and checks for collisions between
    non-adjacent link pairs.  Adjacent links (connected by a joint) are
    skipped since they are always in contact.

    Args:
        robot_model: UR robot model name ('ur3e', 'ur5e', 'ur10e').
        extruder_length: Length of extruder/tool from flange (m).
        extruder_radius: Radius of extruder capsule (m).
        safety_margin: Extra clearance required between links (m).
        adjacency_skip: Skip link pairs within this joint distance.
            2 means pairs separated by up to 2 joints are skipped
            (appropriate for tightly-packed UR wrist joints).
    """

    def __init__(
        self,
        robot_model: str = 'ur5e',
        extruder_length: float = EXTRUDER_LENGTH,
        extruder_radius: float = EXTRUDER_RADIUS,
        safety_margin: float = 0.02,
        adjacency_skip: int = 2,
    ):
        if robot_model not in UR_DH_PARAMS:
            raise ValueError(
                f'Unknown robot model {robot_model!r}. '
                f'Available: {list(UR_DH_PARAMS)}'
            )
        self.robot_model = robot_model
        self.dh_params = UR_DH_PARAMS[robot_model]
        self.link_radii = UR_LINK_RADII[robot_model]
        self.extruder_length = extruder_length
        self.extruder_radius = extruder_radius
        self.safety_margin = safety_margin
        self.adjacency_skip = adjacency_skip

    # ── Public API ───────────────────────────────────────────────────────

    def check_config(self, joint_angles: np.ndarray) -> CollisionResult:
        """Check a single joint configuration for self-collisions.

        Args:
            joint_angles: Array of 6 joint angles (radians).

        Returns:
            CollisionResult with collision status and per-pair clearances.
        """
        joint_angles = np.asarray(joint_angles, dtype=float)
        capsules = self._build_capsules(joint_angles)
        n = len(capsules)

        collision_pairs: List[Tuple[str, str]] = []
        clearances: Dict[Tuple[str, str], float] = {}
        min_clearance = float('inf')

        for i in range(n):
            for j in range(i + 1, n):
                if self._are_adjacent(i, j, n, self.adjacency_skip):
                    continue

                cap_i, name_i = capsules[i]
                cap_j, name_j = capsules[j]

                clearance = capsule_distance(cap_i, cap_j) - self.safety_margin
                pair_key = (name_i, name_j)
                clearances[pair_key] = clearance

                if clearance < min_clearance:
                    min_clearance = clearance

                if clearance < 0.0:
                    collision_pairs.append(pair_key)

        return CollisionResult(
            has_collision=len(collision_pairs) > 0,
            min_clearance=min_clearance,
            collision_pairs=collision_pairs,
            clearances=clearances,
        )

    def check_trajectory(
        self, joint_trajectory: np.ndarray,
    ) -> List[Tuple[int, CollisionResult]]:
        """Check an entire trajectory for self-collisions.

        Args:
            joint_trajectory: (N, 6) array of joint angle arrays.

        Returns:
            List of (index, CollisionResult) for configurations with
            collisions.  Empty list means the trajectory is collision-free.
        """
        collisions = []
        for idx, q in enumerate(joint_trajectory):
            result = self.check_config(q)
            if result.has_collision:
                collisions.append((idx, result))
        return collisions

    def min_clearance_trajectory(
        self, joint_trajectory: np.ndarray,
    ) -> Tuple[float, int, Optional[Tuple[str, str]]]:
        """Find minimum clearance across an entire trajectory.

        Returns (min_clearance, worst_index, worst_pair).
        """
        worst_clearance = float('inf')
        worst_idx = -1
        worst_pair: Optional[Tuple[str, str]] = None

        for idx, q in enumerate(joint_trajectory):
            result = self.check_config(q)
            if result.min_clearance < worst_clearance:
                worst_clearance = result.min_clearance
                worst_idx = idx
                for pair, cl in result.clearances.items():
                    if abs(cl - result.min_clearance) < 1e-10:
                        worst_pair = pair
                        break

        return worst_clearance, worst_idx, worst_pair

    # ── Internal ─────────────────────────────────────────────────────────

    def _build_capsules(
        self, joint_angles: np.ndarray,
    ) -> List[Tuple[Capsule, str]]:
        """Build capsule list from joint configuration.

        Returns list of (Capsule, link_name) tuples.
        """
        transforms = forward_kinematics_all_links(joint_angles, self.dh_params)
        capsules: List[Tuple[Capsule, str]] = []

        for i in range(6):
            p0 = transforms[i][:3, 3].copy()
            p1 = transforms[i + 1][:3, 3].copy()

            # For collocated joints, create a tiny capsule along the frame Z
            if np.linalg.norm(p1 - p0) < 1e-6:
                p1 = p0 + transforms[i][:3, 2] * 0.01

            capsules.append((
                Capsule(p0, p1, self.link_radii[i]),
                LINK_NAMES[i],
            ))

        # Extruder: extends from flange along the flange Z-axis.
        T_flange = transforms[6]
        ext_p0 = T_flange[:3, 3].copy()
        ext_p1 = ext_p0 + T_flange[:3, 2] * self.extruder_length
        capsules.append((
            Capsule(ext_p0, ext_p1, self.extruder_radius),
            'extruder',
        ))

        return capsules

    @staticmethod
    def _are_adjacent(
        i: int, j: int, n_capsules: int, adjacency_skip: int = 2,
    ) -> bool:
        """Determine if two capsule indices are adjacent (skip checking).

        Link indices 0..5 are robot links, index 6 is the extruder.
        The extruder is adjacent to wrist3_flange (index 5) and any
        link within *adjacency_skip* joints of it.
        """
        if i > j:
            i, j = j, i
        # Extruder (last capsule, index n_capsules-1) is adjacent to
        # the last robot link and links close to it.
        if j == n_capsules - 1:
            link_dist = (n_capsules - 1) - i
        else:
            link_dist = j - i
        return link_dist <= adjacency_skip
