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
Toolpath Visualizer

Publishes RViz MarkerArray for toolpath visualization:
- Pre-print: full toolpath with colored line strips
- During print: completed (green), current (yellow), remaining (gray)
- Print bed frame axes and bounding box wireframe
"""

from typing import Optional, List
import math
import numpy as np

import rclpy
from rclpy.node import Node
from std_msgs.msg import Header, ColorRGBA
from geometry_msgs.msg import Point, Vector3
from visualization_msgs.msg import Marker, MarkerArray

from ur_3d_printer.msg import PrintState, PrintProgress
from .gcode_parser import GCodeParser
from .toolpath import Toolpath, Layer


class ToolpathVisualizer(Node):
    """
    RViz visualization node for 3D printing toolpaths.

    Subscribers:
        ~/toolpath: Receives toolpath data (internal)
        /print_node/state: Print state for progress coloring
        /print_node/progress: Print progress

    Publishers:
        ~/markers: MarkerArray for RViz
    """

    def __init__(self):
        super().__init__('toolpath_visualizer')

        self.declare_parameter('publish_rate', 2.0)
        self.declare_parameter('frame_id', 'world')
        self.declare_parameter('line_width', 0.001)
        self.declare_parameter('show_travel', True)
        self.declare_parameter('show_bounding_box', True)
        self.declare_parameter('gcode_file', '')
        self.declare_parameter('print_origin_xyz', [0.4, 0.0, 0.925])
        self.declare_parameter('print_origin_rpy', [0.0, 0.0, 0.0])
        self.declare_parameter('filament_diameter', 1.75)

        self.frame_id = self.get_parameter('frame_id').value
        self.line_width = self.get_parameter('line_width').value
        self.show_travel = self.get_parameter('show_travel').value
        self.show_bounding_box = self.get_parameter('show_bounding_box').value
        publish_rate = self.get_parameter('publish_rate').value
        gcode_file = self.get_parameter('gcode_file').value
        origin_xyz = list(self.get_parameter('print_origin_xyz').value)
        origin_rpy = list(self.get_parameter('print_origin_rpy').value)
        filament_diameter = self.get_parameter('filament_diameter').value

        # State
        self.toolpath: Optional[Toolpath] = None
        self.current_state = PrintState.IDLE
        self.current_layer = 0
        self.overall_progress = 0.0

        # Subscribers
        self.state_sub = self.create_subscription(
            PrintState, '/print_node/state', self.state_callback, 10
        )
        self.progress_sub = self.create_subscription(
            PrintProgress, '/print_node/progress', self.progress_callback, 10
        )

        # Publisher
        self.marker_pub = self.create_publisher(MarkerArray, '~/markers', 10)

        # Timer
        self.timer = self.create_timer(1.0 / publish_rate, self.timer_callback)

        # Auto-load G-code file if provided
        if gcode_file:
            self._load_gcode(gcode_file, origin_xyz, origin_rpy, filament_diameter)

        self.get_logger().info('Toolpath visualizer initialized')

    def set_toolpath(self, toolpath: Toolpath):
        """Set the toolpath to visualize."""
        self.toolpath = toolpath
        self.get_logger().info(
            f'Visualizing toolpath: {toolpath.num_layers} layers, '
            f'{toolpath.num_waypoints} waypoints'
        )

    def _load_gcode(self, gcode_file, origin_xyz, origin_rpy, filament_diameter):
        """Parse a G-code file and set it as the toolpath to visualize."""
        try:
            parser = GCodeParser(filament_diameter=filament_diameter)
            toolpath = parser.parse_file(gcode_file)

            # Build print frame: G-code origin → robot base frame
            roll, pitch, yaw = origin_rpy
            cr, sr = math.cos(roll), math.sin(roll)
            cp, sp = math.cos(pitch), math.sin(pitch)
            cy, sy = math.cos(yaw), math.sin(yaw)
            Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
            Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
            Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
            R = Rz @ Ry @ Rx
            print_frame = np.eye(4)
            print_frame[:3, :3] = R
            print_frame[:3, 3] = origin_xyz
            toolpath.print_frame = print_frame

            self.set_toolpath(toolpath)
            self.get_logger().info(f'Loaded G-code from {gcode_file}')
        except Exception as e:
            self.get_logger().error(f'Failed to load G-code {gcode_file}: {e}')

    def state_callback(self, msg: PrintState):
        self.current_state = msg.state

    def progress_callback(self, msg: PrintProgress):
        self.current_layer = msg.current_layer
        self.overall_progress = msg.overall_progress

    def timer_callback(self):
        if self.toolpath is None:
            return

        markers = MarkerArray()
        marker_id = 0

        # Toolpath line strips per layer
        is_printing = self.current_state in (
            PrintState.PRINTING, PrintState.TRAVEL_MOVE,
            PrintState.LAYER_CHANGE, PrintState.PAUSED,
        )

        for layer in self.toolpath.layers:
            # Extrusion path
            extrusion_marker = self._create_line_strip(
                marker_id, layer, is_travel=False, is_printing=is_printing
            )
            if extrusion_marker is not None:
                markers.markers.append(extrusion_marker)
                marker_id += 1

            # Travel path
            if self.show_travel:
                travel_marker = self._create_line_strip(
                    marker_id, layer, is_travel=True, is_printing=is_printing
                )
                if travel_marker is not None:
                    markers.markers.append(travel_marker)
                    marker_id += 1

        # Bounding box wireframe
        if self.show_bounding_box:
            bb_marker = self._create_bounding_box(marker_id)
            if bb_marker is not None:
                markers.markers.append(bb_marker)
                marker_id += 1

        # Print origin frame
        for axis_marker in self._create_origin_axes(marker_id):
            markers.markers.append(axis_marker)
            marker_id += 1

        self.marker_pub.publish(markers)

    def _create_line_strip(
        self, marker_id: int, layer: Layer, is_travel: bool, is_printing: bool
    ) -> Optional[Marker]:
        """Create line strip marker for a layer's extrusion or travel paths."""
        waypoints = layer.travel_waypoints if is_travel else layer.extrusion_waypoints

        if len(waypoints) < 2:
            return None

        marker = Marker()
        marker.header = Header()
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.header.frame_id = self.frame_id
        marker.ns = 'travel' if is_travel else 'extrusion'
        marker.id = marker_id
        marker.type = Marker.LINE_STRIP
        marker.action = Marker.ADD
        marker.scale = Vector3(x=self.line_width, y=0.0, z=0.0)
        marker.pose.orientation.w = 1.0

        # Transform waypoints to robot frame
        R = self.toolpath.print_frame[:3, :3]
        t = self.toolpath.print_frame[:3, 3]

        for wp in waypoints:
            pos = R @ wp.position + t
            p = Point()
            p.x, p.y, p.z = float(pos[0]), float(pos[1]), float(pos[2])
            marker.points.append(p)

        # Color based on state
        if is_travel:
            marker.color = ColorRGBA(r=1.0, g=0.3, b=0.3, a=0.3)
        elif is_printing:
            if layer.index < self.current_layer:
                # Completed layer
                marker.color = ColorRGBA(r=0.2, g=0.9, b=0.2, a=0.8)
            elif layer.index == self.current_layer:
                # Current layer
                marker.color = ColorRGBA(r=1.0, g=1.0, b=0.2, a=1.0)
            else:
                # Remaining
                marker.color = ColorRGBA(r=0.5, g=0.5, b=0.5, a=0.3)
        else:
            # Pre-print: color by layer height (blue gradient)
            if self.toolpath.num_layers > 1:
                frac = layer.index / (self.toolpath.num_layers - 1)
            else:
                frac = 0.0
            marker.color = ColorRGBA(
                r=0.2 + 0.6 * frac,
                g=0.3 + 0.4 * (1.0 - frac),
                b=0.9 - 0.5 * frac,
                a=0.7,
            )

        return marker

    def _create_bounding_box(self, marker_id: int) -> Optional[Marker]:
        """Create wireframe bounding box marker."""
        if self.toolpath is None:
            return None

        bb_min, bb_max = self.toolpath.bounding_box_robot_frame()
        if np.allclose(bb_min, bb_max):
            return None

        marker = Marker()
        marker.header = Header()
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.header.frame_id = self.frame_id
        marker.ns = 'bounding_box'
        marker.id = marker_id
        marker.type = Marker.LINE_LIST
        marker.action = Marker.ADD
        marker.scale = Vector3(x=0.002, y=0.0, z=0.0)
        marker.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=0.3)
        marker.pose.orientation.w = 1.0

        # 8 corners of the bounding box
        corners = []
        for x in (bb_min[0], bb_max[0]):
            for y in (bb_min[1], bb_max[1]):
                for z in (bb_min[2], bb_max[2]):
                    corners.append(Point(x=x, y=y, z=z))

        # 12 edges
        edges = [
            (0, 1), (2, 3), (4, 5), (6, 7),  # Z edges
            (0, 2), (1, 3), (4, 6), (5, 7),  # Y edges
            (0, 4), (1, 5), (2, 6), (3, 7),  # X edges
        ]
        for i, j in edges:
            marker.points.append(corners[i])
            marker.points.append(corners[j])

        return marker

    def _create_origin_axes(self, start_id: int) -> List[Marker]:
        """Create XYZ axis markers at print origin."""
        markers = []
        origin = self.toolpath.print_frame[:3, 3] if self.toolpath else np.zeros(3)
        R = self.toolpath.print_frame[:3, :3] if self.toolpath else np.eye(3)
        axis_length = 0.05

        colors = [
            ColorRGBA(r=1.0, g=0.0, b=0.0, a=1.0),  # X red
            ColorRGBA(r=0.0, g=1.0, b=0.0, a=1.0),  # Y green
            ColorRGBA(r=0.0, g=0.0, b=1.0, a=1.0),  # Z blue
        ]

        for i, color in enumerate(colors):
            marker = Marker()
            marker.header = Header()
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.header.frame_id = self.frame_id
            marker.ns = 'print_origin'
            marker.id = start_id + i
            marker.type = Marker.ARROW
            marker.action = Marker.ADD
            marker.scale = Vector3(x=0.003, y=0.006, z=0.0)
            marker.color = color

            start = Point(x=float(origin[0]), y=float(origin[1]), z=float(origin[2]))
            end_pos = origin + R[:, i] * axis_length
            end = Point(x=float(end_pos[0]), y=float(end_pos[1]), z=float(end_pos[2]))
            marker.points = [start, end]

            markers.append(marker)

        return markers


def main(args=None):
    rclpy.init(args=args)
    node = ToolpathVisualizer()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
