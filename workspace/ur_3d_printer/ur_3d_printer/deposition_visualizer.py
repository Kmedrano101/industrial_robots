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
Deposition Visualizer — 3D material deposition in RViz.

Renders the printed part as it grows layer by layer.  Each extrusion
segment is visualized as a 3D tube (TRIANGLE_LIST) that looks like
deposited plastic filament.

Modes:
    demo  — animates the full print at configurable speed (standalone).
    live  — syncs with the actual print_node via /print_node/progress.

Topics published:
    ~/deposition  (MarkerArray) — 3D tube geometry per completed layer,
        active extrusion line, nozzle position, and progress text.
"""

import math
from typing import List, Optional

import numpy as np

import rclpy
from rclpy.node import Node
from std_msgs.msg import Header, ColorRGBA
from geometry_msgs.msg import Point, Vector3
from visualization_msgs.msg import Marker, MarkerArray

from ur_3d_printer.msg import PrintProgress
from .gcode_parser import GCodeParser
from .toolpath import Toolpath, Layer, Waypoint


# ── Tube Geometry ────────────────────────────────────────────────────────────

def _perpendicular_frame(direction):
    """Return two unit vectors (u, v) perpendicular to *direction*."""
    d = direction / (np.linalg.norm(direction) + 1e-15)
    ref = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(d, ref)
    u /= (np.linalg.norm(u) + 1e-15)
    v = np.cross(d, u)
    return u, v


def generate_tube_points(
    p0: np.ndarray,
    p1: np.ndarray,
    radius: float,
    n_sides: int = 8,
) -> List[np.ndarray]:
    """Generate triangle vertices for a tube from *p0* to *p1*.

    Returns a flat list of (x, y, z) arrays — every three consecutive
    entries form one triangle, suitable for a TRIANGLE_LIST marker.
    """
    d = p1 - p0
    length = np.linalg.norm(d)
    if length < 1e-8:
        return []

    u, v = _perpendicular_frame(d)
    angles = np.linspace(0.0, 2.0 * np.pi, n_sides, endpoint=False)

    ring0 = [p0 + radius * (np.cos(a) * u + np.sin(a) * v) for a in angles]
    ring1 = [p1 + radius * (np.cos(a) * u + np.sin(a) * v) for a in angles]

    pts: List[np.ndarray] = []
    for i in range(n_sides):
        j = (i + 1) % n_sides
        # Two triangles per quad
        pts.extend([ring0[i], ring1[i], ring1[j]])
        pts.extend([ring0[i], ring1[j], ring0[j]])

    return pts


def generate_cap_points(
    centre: np.ndarray,
    direction: np.ndarray,
    radius: float,
    n_sides: int = 8,
) -> List[np.ndarray]:
    """Generate a flat disc cap (fan triangles) at *centre*."""
    u, v = _perpendicular_frame(direction)
    angles = np.linspace(0.0, 2.0 * np.pi, n_sides, endpoint=False)
    ring = [centre + radius * (np.cos(a) * u + np.sin(a) * v) for a in angles]

    pts: List[np.ndarray] = []
    for i in range(n_sides):
        j = (i + 1) % n_sides
        pts.extend([centre, ring[i], ring[j]])
    return pts


# ── Filament Color Schemes ──────────────────────────────────────────────────

def filament_color(layer_idx: int, total_layers: int, scheme: str = 'pla') -> ColorRGBA:
    """Return a color for the given layer index.

    Schemes:
        pla      — warm orange (realistic PLA) with subtle shade per layer.
        gradient — rainbow from blue (bottom) to red (top).
    """
    frac = layer_idx / max(total_layers - 1, 1)

    if scheme == 'gradient':
        # Blue → Cyan → Green → Yellow → Red
        if frac < 0.25:
            t = frac / 0.25
            return ColorRGBA(r=0.0, g=t, b=1.0, a=0.95)
        elif frac < 0.50:
            t = (frac - 0.25) / 0.25
            return ColorRGBA(r=0.0, g=1.0, b=1.0 - t, a=0.95)
        elif frac < 0.75:
            t = (frac - 0.50) / 0.25
            return ColorRGBA(r=t, g=1.0, b=0.0, a=0.95)
        else:
            t = (frac - 0.75) / 0.25
            return ColorRGBA(r=1.0, g=1.0 - t, b=0.0, a=0.95)

    # Default: PLA orange with slight shade variation per layer
    shade = 0.85 + 0.15 * frac  # brighter toward top
    return ColorRGBA(r=1.0 * shade, g=0.55 * shade, b=0.08 * shade, a=0.95)


# ── ROS2 Node ───────────────────────────────────────────────────────────────

class DepositionVisualizer(Node):
    """Visualizes 3D material deposition in RViz.

    Renders the printed part growing layer by layer.  Each extrusion
    segment is drawn as a 3D tube with realistic filament colour.
    """

    def __init__(self):
        super().__init__('deposition_visualizer')

        # ── Parameters ───────────────────────────────────────────────────
        self.declare_parameter('gcode_file', '')
        self.declare_parameter('frame_id', 'world')
        self.declare_parameter('print_origin_xyz', [-0.3, 0.0, -0.01])
        self.declare_parameter('print_origin_rpy', [0.0, 0.0, 0.0])
        self.declare_parameter('filament_diameter', 1.75)
        self.declare_parameter('nozzle_diameter', 0.0004)    # m
        self.declare_parameter('tube_sides', 8)
        self.declare_parameter('tube_radius_scale', 1.0)
        self.declare_parameter('color_scheme', 'pla')         # pla | gradient
        self.declare_parameter('demo_mode', True)
        self.declare_parameter('speed_scale', 5.0)
        self.declare_parameter('publish_rate', 30.0)

        self.frame_id = self.get_parameter('frame_id').value
        self.tube_sides = self.get_parameter('tube_sides').value
        self.color_scheme = self.get_parameter('color_scheme').value
        self.demo_mode = self.get_parameter('demo_mode').value
        self.speed_scale = self.get_parameter('speed_scale').value
        publish_rate = self.get_parameter('publish_rate').value
        nozzle_d = self.get_parameter('nozzle_diameter').value
        radius_scale = self.get_parameter('tube_radius_scale').value
        self.tube_radius = nozzle_d / 2.0 * radius_scale

        # ── State ────────────────────────────────────────────────────────
        self.toolpath: Optional[Toolpath] = None
        self.robot_waypoints: List[Waypoint] = []   # transformed
        self.current_wp_idx = 0
        self.current_layer = 0
        self.layer_progress = 0.0
        self.completed_layer_markers = {}   # layer_idx → Marker
        self.print_frame = np.eye(4)

        # ── Publisher ────────────────────────────────────────────────────
        self.marker_pub = self.create_publisher(
            MarkerArray, '~/deposition', 10,
        )

        # ── Load toolpath ────────────────────────────────────────────────
        gcode_file = self.get_parameter('gcode_file').value
        if gcode_file:
            self._load_gcode(gcode_file)

        # ── Timer / subscriber ───────────────────────────────────────────
        if self.demo_mode:
            self.timer = self.create_timer(
                1.0 / publish_rate, self._demo_tick,
            )
            self.get_logger().info(
                f'Demo mode: speed_scale={self.speed_scale}x'
            )
        else:
            self.progress_sub = self.create_subscription(
                PrintProgress, '/print_node/progress',
                self._progress_callback, 10,
            )
            self.timer = self.create_timer(
                1.0 / min(publish_rate, 10.0), self._live_tick,
            )

        self.get_logger().info('Deposition visualizer ready')

    # ── G-code Loading ───────────────────────────────────────────────────

    def _load_gcode(self, path: str):
        try:
            filament_d = self.get_parameter('filament_diameter').value
            parser = GCodeParser(filament_diameter=filament_d)
            self.toolpath = parser.parse_file(path)

            origin_xyz = list(self.get_parameter('print_origin_xyz').value)
            origin_rpy = list(self.get_parameter('print_origin_rpy').value)
            self.print_frame = self._build_print_frame(origin_xyz, origin_rpy)
            self.toolpath.print_frame = self.print_frame

            self.robot_waypoints = self.toolpath.transform_to_robot_frame()

            self.get_logger().info(
                f'Loaded {path}: {self.toolpath.num_layers} layers, '
                f'{self.toolpath.num_waypoints} waypoints'
            )
        except Exception as e:
            self.get_logger().error(f'Failed to load {path}: {e}')

    @staticmethod
    def _build_print_frame(xyz, rpy):
        roll, pitch, yaw = rpy
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
        Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
        Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
        T = np.eye(4)
        T[:3, :3] = Rz @ Ry @ Rx
        T[:3, 3] = xyz
        return T

    # ── Demo Mode ────────────────────────────────────────────────────────

    def _demo_tick(self):
        if not self.robot_waypoints:
            return

        # Advance through waypoints at scaled speed.
        # Each tick moves ~speed_scale waypoints.
        advance = max(1, int(self.speed_scale))
        self.current_wp_idx = min(
            self.current_wp_idx + advance,
            len(self.robot_waypoints) - 1,
        )

        # Figure out which layer we're in.
        wp = self.robot_waypoints[self.current_wp_idx]
        self.current_layer = wp.layer_index

        self._publish_markers()

    # ── Live Mode ────────────────────────────────────────────────────────

    def _progress_callback(self, msg: PrintProgress):
        self.current_layer = msg.current_layer
        self.layer_progress = msg.layer_progress

        if self.toolpath:
            total_wp = self.toolpath.num_waypoints
            self.current_wp_idx = int(msg.overall_progress * total_wp)

    def _live_tick(self):
        if self.robot_waypoints:
            self._publish_markers()

    # ── Marker Generation ────────────────────────────────────────────────

    def _publish_markers(self):
        markers = MarkerArray()
        stamp = self.get_clock().now().to_msg()
        mid = 0  # marker id counter

        total_layers = self.toolpath.num_layers if self.toolpath else 1

        # ── Completed layers (3D tubes) ──────────────────────────────
        # Build tube geometry for each completed layer once, then cache.
        for layer in (self.toolpath.layers if self.toolpath else []):
            if layer.index >= self.current_layer:
                break

            if layer.index not in self.completed_layer_markers:
                m = self._build_layer_tube_marker(
                    layer, mid, stamp, total_layers,
                )
                if m is not None:
                    self.completed_layer_markers[layer.index] = m

            if layer.index in self.completed_layer_markers:
                cached = self.completed_layer_markers[layer.index]
                cached.id = mid
                cached.header.stamp = stamp
                markers.markers.append(cached)
                mid += 1

        # ── Active layer (growing tube) ──────────────────────────────
        active_marker = self._build_active_layer_marker(mid, stamp, total_layers)
        if active_marker is not None:
            markers.markers.append(active_marker)
            mid += 1

        # ── Nozzle position (small sphere) ───────────────────────────
        nozzle = self._build_nozzle_marker(mid, stamp)
        if nozzle is not None:
            markers.markers.append(nozzle)
            mid += 1

        # ── Progress text ────────────────────────────────────────────
        text = self._build_text_marker(mid, stamp, total_layers)
        if text is not None:
            markers.markers.append(text)
            mid += 1

        self.marker_pub.publish(markers)

    def _build_layer_tube_marker(
        self, layer: Layer, mid: int, stamp, total_layers: int,
    ) -> Optional[Marker]:
        """Build TRIANGLE_LIST marker for a completed layer's extrusion."""
        R = self.print_frame[:3, :3]
        t = self.print_frame[:3, 3]

        extrusion_wps = layer.extrusion_waypoints
        if len(extrusion_wps) < 2:
            return None

        all_pts: List[np.ndarray] = []
        for i in range(1, len(extrusion_wps)):
            p0 = R @ extrusion_wps[i - 1].position + t
            p1 = R @ extrusion_wps[i].position + t
            all_pts.extend(
                generate_tube_points(p0, p1, self.tube_radius, self.tube_sides),
            )

        if not all_pts:
            return None

        marker = Marker()
        marker.header = Header(stamp=stamp, frame_id=self.frame_id)
        marker.ns = 'deposition'
        marker.id = mid
        marker.type = Marker.TRIANGLE_LIST
        marker.action = Marker.ADD
        marker.scale = Vector3(x=1.0, y=1.0, z=1.0)
        marker.pose.orientation.w = 1.0
        marker.color = filament_color(
            layer.index, total_layers, self.color_scheme,
        )

        for pt in all_pts:
            marker.points.append(
                Point(x=float(pt[0]), y=float(pt[1]), z=float(pt[2])),
            )

        return marker

    def _build_active_layer_marker(
        self, mid: int, stamp, total_layers: int,
    ) -> Optional[Marker]:
        """Build tube for the portion of the current layer printed so far."""
        if not self.toolpath or not self.robot_waypoints:
            return None

        # Collect extrusion waypoints in the current layer up to current_wp_idx
        active_wps: List[Waypoint] = []
        for wp in self.robot_waypoints[:self.current_wp_idx + 1]:
            if wp.layer_index == self.current_layer and not wp.is_travel:
                active_wps.append(wp)

        if len(active_wps) < 2:
            return None

        all_pts: List[np.ndarray] = []
        for i in range(1, len(active_wps)):
            all_pts.extend(
                generate_tube_points(
                    active_wps[i - 1].position,
                    active_wps[i].position,
                    self.tube_radius,
                    self.tube_sides,
                ),
            )

        if not all_pts:
            return None

        marker = Marker()
        marker.header = Header(stamp=stamp, frame_id=self.frame_id)
        marker.ns = 'active_layer'
        marker.id = mid
        marker.type = Marker.TRIANGLE_LIST
        marker.action = Marker.ADD
        marker.scale = Vector3(x=1.0, y=1.0, z=1.0)
        marker.pose.orientation.w = 1.0

        # Active layer: brighter version of the filament color
        base = filament_color(
            self.current_layer, total_layers, self.color_scheme,
        )
        marker.color = ColorRGBA(
            r=min(1.0, base.r * 1.3),
            g=min(1.0, base.g * 1.3),
            b=min(1.0, base.b * 1.3),
            a=1.0,
        )

        for pt in all_pts:
            marker.points.append(
                Point(x=float(pt[0]), y=float(pt[1]), z=float(pt[2])),
            )

        return marker

    def _build_nozzle_marker(self, mid: int, stamp) -> Optional[Marker]:
        """Small glowing sphere at the current nozzle position."""
        if not self.robot_waypoints or self.current_wp_idx >= len(self.robot_waypoints):
            return None

        wp = self.robot_waypoints[self.current_wp_idx]

        marker = Marker()
        marker.header = Header(stamp=stamp, frame_id=self.frame_id)
        marker.ns = 'nozzle'
        marker.id = mid
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD

        size = self.tube_radius * 6
        marker.scale = Vector3(x=size, y=size, z=size)
        marker.pose.position = Point(
            x=float(wp.position[0]),
            y=float(wp.position[1]),
            z=float(wp.position[2]),
        )
        marker.pose.orientation.w = 1.0

        # Red-hot glow when extruding, blue when travelling
        if wp.is_travel:
            marker.color = ColorRGBA(r=0.3, g=0.6, b=1.0, a=0.9)
        else:
            marker.color = ColorRGBA(r=1.0, g=0.3, b=0.1, a=0.9)

        return marker

    def _build_text_marker(self, mid: int, stamp, total_layers: int) -> Optional[Marker]:
        """Floating text showing print progress."""
        if not self.toolpath or not self.robot_waypoints:
            return None

        total_wp = len(self.robot_waypoints)
        pct = 100.0 * self.current_wp_idx / max(total_wp - 1, 1)

        marker = Marker()
        marker.header = Header(stamp=stamp, frame_id=self.frame_id)
        marker.ns = 'progress_text'
        marker.id = mid
        marker.type = Marker.TEXT_VIEW_FACING
        marker.action = Marker.ADD
        marker.scale = Vector3(x=0.0, y=0.0, z=0.015)
        marker.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=0.9)

        # Place text above the print area
        bb_min, bb_max = self.toolpath.bounding_box_robot_frame()
        marker.pose.position = Point(
            x=float((bb_min[0] + bb_max[0]) / 2),
            y=float((bb_min[1] + bb_max[1]) / 2),
            z=float(bb_max[2] + 0.03),
        )
        marker.pose.orientation.w = 1.0
        marker.text = (
            f'Layer {self.current_layer + 1}/{total_layers}  '
            f'{pct:.0f}%'
        )

        return marker


# ── Entry Point ──────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = DepositionVisualizer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
