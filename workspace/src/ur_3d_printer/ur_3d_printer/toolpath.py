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
Toolpath Data Structures

Core data structures for 3D printing toolpaths: Waypoint, Layer, Toolpath.
No ROS dependencies - pure Python + NumPy.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np


@dataclass
class Waypoint:
    """Single point along a toolpath.

    Attributes:
        position: XYZ position in meters (in print frame).
        orientation: 3x3 rotation matrix for nozzle direction.
            Defaults to nozzle-down (identity = Z-down in print frame).
        feed_rate: Linear feed rate in m/s.
        extrusion_rate: Volumetric extrusion rate in m^3/s (0 for travel).
        is_travel: True if this is a non-extruding travel move.
        layer_index: Which layer this waypoint belongs to.
        line_number: Original G-code line number.
    """
    position: np.ndarray  # (3,) xyz meters
    orientation: np.ndarray = field(default_factory=lambda: np.eye(3))  # 3x3 rotation
    feed_rate: float = 0.0  # m/s
    extrusion_rate: float = 0.0  # m^3/s
    is_travel: bool = False
    layer_index: int = 0
    line_number: int = 0

    def __post_init__(self):
        self.position = np.asarray(self.position, dtype=np.float64)
        self.orientation = np.asarray(self.orientation, dtype=np.float64)

    @property
    def x(self) -> float:
        return float(self.position[0])

    @property
    def y(self) -> float:
        return float(self.position[1])

    @property
    def z(self) -> float:
        return float(self.position[2])

    def distance_to(self, other: 'Waypoint') -> float:
        """Euclidean distance to another waypoint."""
        return float(np.linalg.norm(self.position - other.position))

    def to_homogeneous(self) -> np.ndarray:
        """Return 4x4 homogeneous transformation matrix."""
        T = np.eye(4)
        T[:3, :3] = self.orientation
        T[:3, 3] = self.position
        return T


@dataclass
class Layer:
    """A single layer of the print.

    Attributes:
        index: Layer number (0-based).
        z_height: Z position of this layer in meters.
        waypoints: Ordered list of waypoints in this layer.
        layer_height: Height of this layer in meters.
        surface_normals: Optional per-waypoint surface normals for non-planar.
    """
    index: int
    z_height: float
    waypoints: List[Waypoint] = field(default_factory=list)
    layer_height: float = 0.0
    surface_normals: Optional[np.ndarray] = None  # (N, 3) for non-planar

    @property
    def num_waypoints(self) -> int:
        return len(self.waypoints)

    @property
    def extrusion_waypoints(self) -> List[Waypoint]:
        """Return only extruding (non-travel) waypoints."""
        return [w for w in self.waypoints if not w.is_travel]

    @property
    def travel_waypoints(self) -> List[Waypoint]:
        """Return only travel waypoints."""
        return [w for w in self.waypoints if w.is_travel]

    def path_length(self) -> float:
        """Total path length of this layer in meters."""
        length = 0.0
        for i in range(1, len(self.waypoints)):
            length += self.waypoints[i].distance_to(self.waypoints[i - 1])
        return length

    def extrusion_length(self) -> float:
        """Total extrusion path length (excluding travel)."""
        length = 0.0
        for i in range(1, len(self.waypoints)):
            if not self.waypoints[i].is_travel:
                length += self.waypoints[i].distance_to(self.waypoints[i - 1])
        return length


@dataclass
class Toolpath:
    """Complete 3D printing toolpath.

    Attributes:
        layers: Ordered list of layers.
        print_frame: 4x4 transform from print origin to robot base_link.
        metadata: Arbitrary metadata (slicer info, material, etc.).
    """
    layers: List[Layer] = field(default_factory=list)
    print_frame: np.ndarray = field(default_factory=lambda: np.eye(4))  # 4x4
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.print_frame = np.asarray(self.print_frame, dtype=np.float64)

    @property
    def num_layers(self) -> int:
        return len(self.layers)

    @property
    def num_waypoints(self) -> int:
        return sum(layer.num_waypoints for layer in self.layers)

    @property
    def all_waypoints(self) -> List[Waypoint]:
        """Flatten all waypoints across all layers."""
        waypoints = []
        for layer in self.layers:
            waypoints.extend(layer.waypoints)
        return waypoints

    @property
    def bounding_box(self) -> Tuple[np.ndarray, np.ndarray]:
        """Axis-aligned bounding box in print frame.

        Returns:
            (min_corner, max_corner) as (3,) arrays.
        """
        all_wp = self.all_waypoints
        if not all_wp:
            return np.zeros(3), np.zeros(3)
        positions = np.array([w.position for w in all_wp])
        return positions.min(axis=0), positions.max(axis=0)

    @property
    def estimated_time(self) -> float:
        """Estimated total print time in seconds based on feed rates."""
        total = 0.0
        all_wp = self.all_waypoints
        for i in range(1, len(all_wp)):
            dist = all_wp[i].distance_to(all_wp[i - 1])
            speed = all_wp[i].feed_rate
            if speed > 0:
                total += dist / speed
        return total

    def transform_to_robot_frame(self) -> List[Waypoint]:
        """Transform all waypoints from print frame to robot base frame.

        Applies self.print_frame to each waypoint position and orientation.
        Returns new Waypoint objects (does not modify originals).
        """
        R = self.print_frame[:3, :3]
        t = self.print_frame[:3, 3]
        transformed = []
        for wp in self.all_waypoints:
            new_pos = R @ wp.position + t
            new_orient = R @ wp.orientation
            transformed.append(Waypoint(
                position=new_pos,
                orientation=new_orient,
                feed_rate=wp.feed_rate,
                extrusion_rate=wp.extrusion_rate,
                is_travel=wp.is_travel,
                layer_index=wp.layer_index,
                line_number=wp.line_number,
            ))
        return transformed

    def bounding_box_robot_frame(self) -> Tuple[np.ndarray, np.ndarray]:
        """Bounding box in robot base frame."""
        transformed = self.transform_to_robot_frame()
        if not transformed:
            return np.zeros(3), np.zeros(3)
        positions = np.array([w.position for w in transformed])
        return positions.min(axis=0), positions.max(axis=0)
