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
Print Node - Main 3D Printing State Machine

ROS2 node implementing the 3D print executive. Coordinates G-code parsing,
trajectory planning, extruder control, and robot motion.

Follows the PickPlaceNode state machine pattern from ur_pick_place.
"""

import time
from enum import Enum
from typing import Optional, List, Tuple
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.task import Future
from rclpy.action import ActionClient, ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from control_msgs.msg import JointTolerance
from builtin_interfaces.msg import Duration
from std_msgs.msg import Header, ColorRGBA
from geometry_msgs.msg import Point, Vector3
from visualization_msgs.msg import Marker, MarkerArray

from ur_kinematics_msgs.srv import ComputeFK, ComputeIK, ComputeJacobian

from ur_3d_printer.msg import PrintState, PrintProgress
from ur_3d_printer.srv import (
    StartPrint, PausePrint, ResumePrint, CancelPrint, CalibrateOrigin, SetExtruder,
)
from ur_3d_printer.action import ExecutePrint

from .gcode_parser import GCodeParser
from .toolpath import Toolpath
from .trajectory_planner import TrajectoryPlanner, JOINT_NAMES
from .workspace_validator import WorkspaceValidator


def wait_for_future(future: Future, timeout_sec: float = 5.0) -> bool:
    """Wait for an async future to complete without re-spinning the executor.

    Use this instead of rclpy.spin_until_future_complete() when the node
    is already being spun by a MultiThreadedExecutor.
    """
    start = time.time()
    while not future.done() and (time.time() - start) < timeout_sec:
        time.sleep(0.01)
    return future.done()


class State(Enum):
    """Print state machine states."""
    IDLE = 0
    LOADING_GCODE = 1
    VALIDATING = 2
    HOMING = 3
    CALIBRATING = 4
    PRINTING = 5
    TRAVEL_MOVE = 6
    LAYER_CHANGE = 7
    COMPLETED = 8
    PAUSED = 9
    CANCELLING = 10
    ERROR = 11


STATE_NAMES = {
    State.IDLE: 'Idle',
    State.LOADING_GCODE: 'Loading G-code',
    State.VALIDATING: 'Validating toolpath',
    State.HOMING: 'Homing robot',
    State.CALIBRATING: 'Calibrating origin',
    State.PRINTING: 'Printing',
    State.TRAVEL_MOVE: 'Travel move',
    State.LAYER_CHANGE: 'Layer change',
    State.COMPLETED: 'Print completed',
    State.PAUSED: 'Paused',
    State.CANCELLING: 'Cancelling',
    State.ERROR: 'Error',
}


def rpy_to_rotation_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Convert roll-pitch-yaw to 3x3 rotation matrix."""
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)

    R = np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ])
    return R


class PrintNode(Node):
    """
    Main 3D printing state machine node.

    Services:
        ~/start_print: Load G-code and start printing
        ~/pause_print: Pause current print
        ~/resume_print: Resume paused print
        ~/cancel_print: Cancel current print
        ~/calibrate_origin: Set print bed frame

    Action:
        ~/execute_print: Long-running print with feedback

    Publishers:
        ~/state: Current print state
        ~/progress: Print progress

    Subscribers:
        /joint_states: Current robot joint state

    Clients:
        ComputeIK, ComputeFK, ComputeJacobian, FollowJointTrajectory, SetExtruder
    """

    def __init__(self):
        super().__init__('print_node')

        # ── Declare parameters ────────────────────────────────────────────────
        self.declare_parameter('robot_model', 'ur5e')
        self.declare_parameter('home_joints', [3.1416, -1.5708, 1.5708, -1.5708, -1.5708, 0.0])
        self.declare_parameter('print_origin_xyz', [0.4, 0.0, 0.92])
        self.declare_parameter('print_origin_rpy', [3.14159, 0.0, 0.0])
        self.declare_parameter('tool_offset_xyz', [0.0, 0.0, 0.15])
        self.declare_parameter('tool_offset_rpy', [0.0, 0.0, 0.0])
        # Motion
        self.declare_parameter('max_print_velocity', 0.05)
        self.declare_parameter('max_travel_velocity', 0.15)
        self.declare_parameter('max_acceleration', 0.5)
        self.declare_parameter('corner_blend_radius', 0.002)
        self.declare_parameter('waypoint_density', 0.002)
        self.declare_parameter('joint_velocity_limits',
                               [3.14, 3.14, 3.14, 3.14, 3.14, 3.14])
        self.declare_parameter('max_joint_jump', 0.5)
        # Z-hop
        self.declare_parameter('z_hop_enabled', True)
        self.declare_parameter('z_hop_height', 0.005)
        # Collision checking
        self.declare_parameter('enable_collision_check', True)
        self.declare_parameter('collision_safety_margin', 0.02)
        self.declare_parameter('extruder_radius', 0.003)  # 3mm radius (6mm dia)
        # IK solver
        self.declare_parameter('ik_method', 'lm')
        self.declare_parameter('ik_max_iterations', 100)
        self.declare_parameter('ik_tolerance', 1e-6)
        self.declare_parameter('ik_timeout', 5.0)
        # Singularity
        self.declare_parameter('singularity_threshold', 0.05)
        self.declare_parameter('singularity_velocity_scale', 0.3)
        # Workspace
        self.declare_parameter('workspace_min', [-0.8, -0.8, 0.0])
        self.declare_parameter('workspace_max', [0.8, 0.8, 1.5])
        self.declare_parameter('min_reach_radius', 0.17)
        self.declare_parameter('max_reach_radius', 0.85)
        # Arm configuration
        self.declare_parameter('preferred_arm_config', 'elbow_up')
        self.declare_parameter('max_wrist_3_deviation', 3.14)
        # Bed tilt compensation
        self.declare_parameter('bed_tilt_rx', 0.0)
        self.declare_parameter('bed_tilt_ry', 0.0)
        # Validation
        self.declare_parameter('validate_before_print', True)
        self.declare_parameter('validation_sample_rate', 10)
        # Filament
        self.declare_parameter('filament_diameter', 1.75)
        self.declare_parameter('nozzle_diameter', 0.4)
        # Misc
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter(
            'trajectory_controller',
            'scaled_joint_trajectory_controller',
        )

        # ── Load parameters ───────────────────────────────────────────────────
        self.robot_model = self.get_parameter('robot_model').value
        self.home_joints = np.array(self.get_parameter('home_joints').value)
        origin_xyz = np.array(self.get_parameter('print_origin_xyz').value)
        origin_rpy = np.array(self.get_parameter('print_origin_rpy').value)
        tool_xyz = np.array(self.get_parameter('tool_offset_xyz').value)
        tool_rpy = np.array(self.get_parameter('tool_offset_rpy').value)
        self.max_print_velocity = self.get_parameter('max_print_velocity').value
        self.max_travel_velocity = self.get_parameter('max_travel_velocity').value
        self.max_acceleration = self.get_parameter('max_acceleration').value
        self.corner_blend_radius = self.get_parameter('corner_blend_radius').value
        self.waypoint_density = self.get_parameter('waypoint_density').value
        joint_vel_limits = list(self.get_parameter('joint_velocity_limits').value)
        max_joint_jump = self.get_parameter('max_joint_jump').value
        z_hop_enabled = self.get_parameter('z_hop_enabled').value
        z_hop_height = self.get_parameter('z_hop_height').value
        enable_collision_check = self.get_parameter('enable_collision_check').value
        collision_safety_margin = self.get_parameter('collision_safety_margin').value
        extruder_radius = self.get_parameter('extruder_radius').value
        ik_method = self.get_parameter('ik_method').value
        ik_max_iterations = self.get_parameter('ik_max_iterations').value
        ik_tolerance = self.get_parameter('ik_tolerance').value
        ik_timeout = self.get_parameter('ik_timeout').value
        singularity_threshold = self.get_parameter('singularity_threshold').value
        singularity_velocity_scale = self.get_parameter(
            'singularity_velocity_scale').value
        ws_min = np.array(self.get_parameter('workspace_min').value)
        ws_max = np.array(self.get_parameter('workspace_max').value)
        min_reach = self.get_parameter('min_reach_radius').value
        max_reach = self.get_parameter('max_reach_radius').value
        self.preferred_arm_config = self.get_parameter('preferred_arm_config').value
        self.max_wrist_3_deviation = self.get_parameter('max_wrist_3_deviation').value
        bed_tilt_rx = self.get_parameter('bed_tilt_rx').value
        bed_tilt_ry = self.get_parameter('bed_tilt_ry').value
        self.filament_diameter = self.get_parameter('filament_diameter').value
        publish_rate = self.get_parameter('publish_rate').value
        self.validate_before_print = self.get_parameter('validate_before_print').value
        validation_sample_rate = self.get_parameter('validation_sample_rate').value

        # ── Build transforms ──────────────────────────────────────────────────
        # Print frame: G-code origin → robot base_link
        self.print_frame = np.eye(4)
        self.print_frame[:3, :3] = rpy_to_rotation_matrix(*origin_rpy)
        self.print_frame[:3, 3] = origin_xyz

        # Bed tilt compensation: rotate the print frame around X then Y to
        # level a tilted print surface without re-slicing the G-code.
        if abs(bed_tilt_rx) > 1e-6 or abs(bed_tilt_ry) > 1e-6:
            Rx = rpy_to_rotation_matrix(bed_tilt_rx, 0.0, 0.0)
            Ry = rpy_to_rotation_matrix(0.0, bed_tilt_ry, 0.0)
            tilt = np.eye(4)
            tilt[:3, :3] = Ry @ Rx
            self.print_frame = self.print_frame @ tilt
            self.get_logger().info(
                f'Bed tilt compensation applied: '
                f'rx={np.degrees(bed_tilt_rx):.2f}° '
                f'ry={np.degrees(bed_tilt_ry):.2f}°'
            )

        # Tool offset: tool0 → nozzle tip (translation along tool0 Z-axis).
        # The PoE screw model now matches the UR URDF exactly, so no
        # frame correction is needed — just the physical tool geometry.
        self.tool_offset = np.eye(4)
        self.tool_offset[:3, :3] = rpy_to_rotation_matrix(*tool_rpy)
        self.tool_offset[:3, 3] = tool_xyz

        # Arm configuration: choose initial IK seed based on preference
        # ("elbow_up" keeps the elbow above the print, reducing singularity
        # risk for prints positioned in front of the robot).
        if self.preferred_arm_config == 'elbow_up':
            # shoulder_pan=π faces -X (toward the print bed)
            self.home_joints = np.array([np.pi, -1.5708, 1.5708, -1.5708, -1.5708, 0.0])
        elif self.preferred_arm_config == 'elbow_down':
            self.home_joints = np.array([np.pi, -1.5708, -1.5708, -1.5708, -1.5708, 0.0])
        # else: use whatever home_joints was declared

        # Store arm-specific params for logging
        self._arm_params = {
            'z_hop_enabled': z_hop_enabled,
            'z_hop_height': z_hop_height,
            'max_joint_jump': max_joint_jump,
            'min_reach_radius': min_reach,
            'max_reach_radius': max_reach,
            'singularity_threshold': singularity_threshold,
        }

        # State machine
        self.state = State.IDLE
        self.error_message = ''
        self.paused = False

        # Print state
        self.current_toolpath: Optional[Toolpath] = None
        self.planned_trajectories: List[Tuple[JointTrajectory, bool]] = []
        self.continuous_trajectory: Optional[JointTrajectory] = None
        self.extruder_events: List[Tuple[float, bool]] = []
        self.current_segment_idx = 0
        self.current_layer = 0
        self.total_layers = 0
        self.print_start_time = 0.0
        self.estimated_total_time = 0.0

        # Robot state
        self.current_joints: Optional[np.ndarray] = None

        # Callback groups
        self.service_cb_group = ReentrantCallbackGroup()
        self.timer_cb_group = MutuallyExclusiveCallbackGroup()

        # Publishers
        self.state_pub = self.create_publisher(PrintState, '~/state', 10)
        self.progress_pub = self.create_publisher(PrintProgress, '~/progress', 10)
        self.trail_pub = self.create_publisher(MarkerArray, '~/tcp_trail', 10)
        self.planned_path_pub = self.create_publisher(
            MarkerArray, '~/planned_path', 10
        )

        # TCP trail - accumulated nozzle tip positions for RViz visualization
        self.tcp_trail_points: List[Point] = []

        # Subscribers
        self.joint_state_sub = self.create_subscription(
            JointState, '/joint_states', self.joint_state_callback, 10
        )

        # Service clients
        self.ik_client = self.create_client(
            ComputeIK, '/compute_ik'
        )
        self.fk_client = self.create_client(
            ComputeFK, '/compute_fk'
        )
        self.jacobian_client = self.create_client(
            ComputeJacobian, '/compute_jacobian'
        )
        self.extruder_client = self.create_client(
            SetExtruder, '/extruder_controller/set_extruder'
        )

        # Action client for trajectory execution
        controller_name = self.get_parameter('trajectory_controller').value
        self.trajectory_client = ActionClient(
            self, FollowJointTrajectory,
            f'/{controller_name}/follow_joint_trajectory'
        )

        # Action server for long-running print
        self.execute_print_server = ActionServer(
            self, ExecutePrint, '~/execute_print',
            self.execute_print_callback,
            callback_group=self.service_cb_group,
        )

        # Services
        self.start_print_srv = self.create_service(
            StartPrint, '~/start_print', self.start_print_callback,
            callback_group=self.service_cb_group,
        )
        self.pause_print_srv = self.create_service(
            PausePrint, '~/pause_print', self.pause_print_callback,
            callback_group=self.service_cb_group,
        )
        self.resume_print_srv = self.create_service(
            ResumePrint, '~/resume_print', self.resume_print_callback,
            callback_group=self.service_cb_group,
        )
        self.cancel_print_srv = self.create_service(
            CancelPrint, '~/cancel_print', self.cancel_print_callback,
            callback_group=self.service_cb_group,
        )
        self.calibrate_origin_srv = self.create_service(
            CalibrateOrigin, '~/calibrate_origin', self.calibrate_origin_callback,
            callback_group=self.service_cb_group,
        )

        # G-code parser
        self.gcode_parser = GCodeParser(filament_diameter=self.filament_diameter)

        # Trajectory planner (created after node init for service clients)
        self.trajectory_planner = TrajectoryPlanner(
            node=self,
            tool_offset=self.tool_offset,
            robot_model=self.robot_model,
            ik_method=ik_method,
            ik_max_iterations=ik_max_iterations,
            ik_tolerance=ik_tolerance,
            ik_timeout=ik_timeout,
            max_segment_length=self.waypoint_density,
            z_hop_enabled=z_hop_enabled,
            z_hop_height=z_hop_height,
            max_joint_jump=max_joint_jump,
            joint_velocity_limits=joint_vel_limits,
            singularity_velocity_scale=singularity_velocity_scale,
            enable_collision_check=enable_collision_check,
            collision_safety_margin=collision_safety_margin,
            extruder_radius=extruder_radius,
        )
        self.trajectory_planner.configure_profiler(
            max_print_velocity=self.max_print_velocity,
            max_travel_velocity=self.max_travel_velocity,
            max_acceleration=self.max_acceleration,
            corner_blend_radius=self.corner_blend_radius,
        )

        # Workspace validator
        self.workspace_validator = WorkspaceValidator(
            node=self,
            tool_offset=self.tool_offset,
            workspace_bounds=(ws_min, ws_max),
            singularity_threshold=singularity_threshold,
            sample_every_n=validation_sample_rate,
            min_reach_radius=min_reach,
            max_reach_radius=max_reach,
        )

        # Timer for state publishing
        self.timer = self.create_timer(
            1.0 / publish_rate, self.timer_callback,
            callback_group=self.timer_cb_group,
        )

        self.get_logger().info(f'Print node initialized for {self.robot_model}')
        self.get_logger().info(f'  Print origin: {origin_xyz}')
        self.get_logger().info(f'  Tool offset: {tool_xyz}')

    def joint_state_callback(self, msg: JointState):
        """Handle joint state updates."""
        positions = []
        for name in JOINT_NAMES:
            if name in msg.name:
                idx = msg.name.index(name)
                positions.append(msg.position[idx])
        if len(positions) == 6:
            self.current_joints = np.array(positions)

    def timer_callback(self):
        """Publish state and progress."""
        now = self.get_clock().now().to_msg()

        # Publish state
        state_msg = PrintState()
        state_msg.header = Header()
        state_msg.header.stamp = now
        state_msg.state = self.state.value
        state_msg.state_name = STATE_NAMES[self.state]
        state_msg.error_message = self.error_message
        self.state_pub.publish(state_msg)

        # Publish progress
        if self.state in (State.PRINTING, State.TRAVEL_MOVE, State.LAYER_CHANGE, State.PAUSED):
            progress_msg = PrintProgress()
            progress_msg.header = Header()
            progress_msg.header.stamp = now
            progress_msg.current_layer = self.current_layer
            progress_msg.total_layers = self.total_layers
            if self.total_layers > 0:
                progress_msg.overall_progress = float(self.current_layer) / self.total_layers
            progress_msg.elapsed_time = time.time() - self.print_start_time
            if self.estimated_total_time > 0 and progress_msg.overall_progress > 0:
                progress_msg.estimated_remaining = (
                    progress_msg.elapsed_time / progress_msg.overall_progress
                    - progress_msg.elapsed_time
                )
            if self.current_toolpath and self.current_layer < len(self.current_toolpath.layers):
                layer = self.current_toolpath.layers[self.current_layer]
                progress_msg.current_z_height = layer.z_height
            self.progress_pub.publish(progress_msg)

        # Publish TCP trail — compute nozzle tip position from FK + tool offset
        if self.current_joints is not None and self.state in (
            State.PRINTING, State.TRAVEL_MOVE, State.LAYER_CHANGE,
        ):
            self._update_tcp_trail()
        self._publish_tcp_trail(now)

    # ── TCP Trail ─────────────────────────────────────────────────

    def _update_tcp_trail(self):
        """Compute current nozzle tip position and add to trail."""
        T_flange = self.trajectory_planner.kinematics.fk(self.current_joints)
        T_nozzle = T_flange @ self.tool_offset
        pos = T_nozzle[:3, 3]
        self.tcp_trail_points.append(
            Point(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]))
        )

    def _publish_tcp_trail(self, stamp):
        """Publish accumulated TCP trail as RViz markers."""
        markers = MarkerArray()

        if len(self.tcp_trail_points) >= 2:
            trail = Marker()
            trail.header = Header(stamp=stamp, frame_id='world')
            trail.ns = 'tcp_trail'
            trail.id = 0
            trail.type = Marker.LINE_STRIP
            trail.action = Marker.ADD
            trail.scale = Vector3(x=0.002, y=0.0, z=0.0)
            trail.color = ColorRGBA(r=0.0, g=1.0, b=0.5, a=0.9)
            trail.pose.orientation.w = 1.0
            trail.points = list(self.tcp_trail_points)
            markers.markers.append(trail)

            # Sphere at current nozzle position
            tip = Marker()
            tip.header = Header(stamp=stamp, frame_id='world')
            tip.ns = 'tcp_trail'
            tip.id = 1
            tip.type = Marker.SPHERE
            tip.action = Marker.ADD
            tip.scale = Vector3(x=0.005, y=0.005, z=0.005)
            tip.color = ColorRGBA(r=1.0, g=0.2, b=0.0, a=1.0)
            tip.pose.position = self.tcp_trail_points[-1]
            tip.pose.orientation.w = 1.0
            markers.markers.append(tip)
        else:
            # Delete old markers when trail is empty
            delete = Marker()
            delete.header = Header(stamp=stamp, frame_id='world')
            delete.ns = 'tcp_trail'
            delete.id = 0
            delete.action = Marker.DELETE
            markers.markers.append(delete)

        self.trail_pub.publish(markers)

    def _publish_planned_path(self, trajectory: JointTrajectory):
        """Publish the planned trajectory as a cyan line in RViz via FK."""
        markers = MarkerArray()
        points = []
        for pt in trajectory.points:
            joints = np.array(pt.positions)
            T_flange = self.trajectory_planner.kinematics.fk(joints)
            T_nozzle = T_flange @ self.tool_offset
            pos = T_nozzle[:3, 3]
            points.append(
                Point(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]))
            )

        if len(points) >= 2:
            line = Marker()
            line.header = Header(
                stamp=self.get_clock().now().to_msg(),
                frame_id='world',
            )
            line.ns = 'planned_path'
            line.id = 0
            line.type = Marker.LINE_STRIP
            line.action = Marker.ADD
            line.scale = Vector3(x=0.0015, y=0.0, z=0.0)
            line.color = ColorRGBA(r=0.0, g=0.8, b=1.0, a=0.8)
            line.pose.orientation.w = 1.0
            line.points = points
            markers.markers.append(line)

        self.planned_path_pub.publish(markers)
        self.get_logger().info(
            f'Published planned path: {len(points)} points'
        )

    def _clear_planned_path(self):
        """Delete the planned path marker from RViz."""
        markers = MarkerArray()
        delete = Marker()
        delete.header = Header(
            stamp=self.get_clock().now().to_msg(),
            frame_id='world',
        )
        delete.ns = 'planned_path'
        delete.id = 0
        delete.action = Marker.DELETE
        markers.markers.append(delete)
        self.planned_path_pub.publish(markers)

    # ── Service Callbacks ──────────────────────────────────────────

    def start_print_callback(
        self, request: StartPrint.Request, response: StartPrint.Response
    ) -> StartPrint.Response:
        """Handle start print request."""
        # Allow recovery from stuck states (ERROR, COMPLETED, VALIDATING with
        # no active print).  Only truly active states block a new request.
        if self.state in (State.ERROR, State.COMPLETED):
            self.get_logger().warn(
                f'Resetting from {STATE_NAMES[self.state]} → IDLE'
            )
            self.state = State.IDLE

        if self.state != State.IDLE:
            response.success = False
            response.message = f'Cannot start: currently in state {STATE_NAMES[self.state]}'
            return response

        try:
            result = self._load_and_validate(request.gcode_filepath)
            if result is None:
                response.success = False
                response.message = self.error_message
                return response

            toolpath, trajectories = result
            response.num_layers = toolpath.num_layers
            response.estimated_time = toolpath.estimated_time

            if request.validate_only:
                response.success = True
                response.message = 'Validation passed'
                self.state = State.IDLE
                return response

            # Start printing
            self.current_toolpath = toolpath
            self.planned_trajectories = trajectories
            self.current_segment_idx = 0
            self.total_layers = toolpath.num_layers
            self.current_layer = 0
            self.print_start_time = time.time()
            self.estimated_total_time = toolpath.estimated_time
            self.tcp_trail_points.clear()

            success = self._execute_print_loop()
            response.success = success
            response.message = 'Print completed' if success else self.error_message

        except Exception as e:
            self.state = State.ERROR
            self.error_message = str(e)
            response.success = False
            response.message = str(e)
            self.get_logger().error(f'Start print failed: {e}')

        self.state = State.IDLE
        return response

    def pause_print_callback(
        self, request: PausePrint.Request, response: PausePrint.Response
    ) -> PausePrint.Response:
        """Pause the current print."""
        if self.state not in (State.PRINTING, State.TRAVEL_MOVE):
            response.success = False
            response.message = f'Cannot pause in state {STATE_NAMES[self.state]}'
            return response

        self.paused = True
        self.state = State.PAUSED
        # Retract extruder
        self._set_extruder(enable=False, retract=True)
        response.success = True
        response.message = 'Print paused'
        self.get_logger().info('Print paused')
        return response

    def resume_print_callback(
        self, request: ResumePrint.Request, response: ResumePrint.Response
    ) -> ResumePrint.Response:
        """Resume a paused print."""
        if self.state != State.PAUSED:
            response.success = False
            response.message = f'Cannot resume: not paused (state: {STATE_NAMES[self.state]})'
            return response

        self.paused = False
        self.state = State.PRINTING
        response.success = True
        response.message = 'Print resumed'
        self.get_logger().info('Print resumed')
        return response

    def cancel_print_callback(
        self, request: CancelPrint.Request, response: CancelPrint.Response
    ) -> CancelPrint.Response:
        """Cancel the current print."""
        if self.state == State.IDLE:
            response.success = False
            response.message = 'No print in progress'
            return response

        self.state = State.CANCELLING
        self._set_extruder(enable=False, retract=True)

        if request.retract_and_home:
            self._move_to_joints(self.home_joints)

        self.state = State.IDLE
        self.current_toolpath = None
        self.planned_trajectories = []
        response.success = True
        response.message = 'Print cancelled'
        self.get_logger().info('Print cancelled')
        return response

    def calibrate_origin_callback(
        self, request: CalibrateOrigin.Request, response: CalibrateOrigin.Response
    ) -> CalibrateOrigin.Response:
        """Calibrate print origin."""
        if request.use_current_pose:
            if self.current_joints is None:
                response.success = False
                response.message = 'No joint state available'
                return response

            # Get current TCP pose via FK
            fk_request = ComputeFK.Request()
            fk_request.joint_positions = self.current_joints.tolist()
            future = self.fk_client.call_async(fk_request)
            wait_for_future(future, timeout_sec=5.0)

            if not future.done() or not future.result().success:
                response.success = False
                response.message = 'FK computation failed'
                return response

            pose = future.result().end_effector_pose
            self.print_frame[:3, 3] = np.array([
                pose.position.x, pose.position.y, pose.position.z
            ])
            self.get_logger().info(
                f'Print origin set from current pose: {self.print_frame[:3, 3]}'
            )
        else:
            origin = np.array([
                request.origin_xyz.x, request.origin_xyz.y, request.origin_xyz.z
            ])
            rpy = np.array([
                request.origin_rpy.x, request.origin_rpy.y, request.origin_rpy.z
            ])
            self.print_frame[:3, :3] = rpy_to_rotation_matrix(*rpy)
            self.print_frame[:3, 3] = origin
            self.get_logger().info(f'Print origin set manually: {origin}')

        response.success = True
        response.message = 'Origin calibrated'
        response.print_frame = self.print_frame.flatten().tolist()
        return response

    # ── Action Callback ────────────────────────────────────────────

    def execute_print_callback(self, goal_handle):
        """Handle long-running print action."""
        self.get_logger().info(f'Execute print action: {goal_handle.request.gcode_filepath}')

        if self.state != State.IDLE:
            goal_handle.abort()
            result = ExecutePrint.Result()
            result.success = False
            result.message = f'Cannot start: in state {STATE_NAMES[self.state]}'
            return result

        try:
            loaded = self._load_and_validate(goal_handle.request.gcode_filepath)
            if loaded is None:
                goal_handle.abort()
                result = ExecutePrint.Result()
                result.success = False
                result.message = self.error_message
                return result

            toolpath, trajectories = loaded
            self.current_toolpath = toolpath
            self.planned_trajectories = trajectories
            self.current_segment_idx = 0
            self.total_layers = toolpath.num_layers
            self.current_layer = 0
            self.print_start_time = time.time()
            self.estimated_total_time = toolpath.estimated_time
            self.tcp_trail_points.clear()

            # Execute with feedback
            success = self._execute_print_loop(goal_handle=goal_handle)

            result = ExecutePrint.Result()
            result.success = success
            result.message = 'Print completed' if success else self.error_message
            result.layers_completed = self.current_layer
            result.total_time = time.time() - self.print_start_time

            if success:
                goal_handle.succeed()
            else:
                goal_handle.abort()

        except Exception as e:
            self.state = State.ERROR
            self.error_message = str(e)
            goal_handle.abort()
            result = ExecutePrint.Result()
            result.success = False
            result.message = str(e)
            self.get_logger().error(f'Execute print failed: {e}')

        self.state = State.IDLE
        return result

    # ── Core Logic ─────────────────────────────────────────────────

    def _load_and_validate(self, gcode_filepath: str):
        """Load G-code, validate, and plan trajectories.

        Returns (toolpath, trajectories) or None on failure.
        """
        # Load G-code
        self.state = State.LOADING_GCODE
        self.get_logger().info(f'Loading G-code: {gcode_filepath}')

        try:
            toolpath = self.gcode_parser.parse_file(gcode_filepath)
        except Exception as e:
            self.error_message = f'Failed to parse G-code: {e}'
            self.state = State.ERROR
            return None

        toolpath.print_frame = self.print_frame.copy()
        self.get_logger().info(
            f'Parsed {toolpath.num_layers} layers, {toolpath.num_waypoints} waypoints'
        )

        # Validate
        if self.validate_before_print:
            self.state = State.VALIDATING
            if self.current_joints is None:
                self.error_message = 'No joint state available for validation'
                self.state = State.ERROR
                return None

            validation = self.workspace_validator.validate(
                toolpath, self.current_joints
            )
            if not validation.is_valid:
                self.error_message = (
                    f'Validation failed: {"; ".join(validation.messages)}'
                )
                self.state = State.ERROR
                return None

        # Wait for services
        if not self._wait_for_services():
            self.error_message = 'Required services not available'
            self.state = State.ERROR
            return None

        # Plan trajectories
        self.get_logger().info('Planning trajectories...')
        if self.current_joints is None:
            self.error_message = 'No joint state for planning'
            self.state = State.ERROR
            return None

        # Plan as one continuous trajectory for smooth motion
        cont_traj, ext_events = self.trajectory_planner.plan_toolpath_continuous(
            toolpath, self.current_joints
        )

        if cont_traj is None or not cont_traj.points:
            self.error_message = 'Continuous trajectory planning failed'
            self.state = State.ERROR
            return None

        # Also keep segmented trajectories for backwards compatibility
        trajectories = self.trajectory_planner.plan_toolpath(
            toolpath, self.current_joints
        )

        self.continuous_trajectory = cont_traj
        self.extruder_events = ext_events
        self.get_logger().info(
            f'Planned continuous trajectory: {len(cont_traj.points)} points'
        )

        # Publish the planned path in RViz for visual verification
        self._publish_planned_path(cont_traj)

        return toolpath, trajectories

    def _execute_print_loop(self, goal_handle=None) -> bool:
        """Execute the pre-planned continuous trajectory.

        Uses a single JointTrajectory covering the entire print with
        smooth velocity through all layer transitions and z-hops.
        Extruder state changes are scheduled via timed callbacks.

        Returns True on success.
        """
        import threading

        trajectory = self.continuous_trajectory
        extruder_events = self.extruder_events

        if trajectory is None or not trajectory.points:
            self.error_message = 'No continuous trajectory available'
            self.state = State.ERROR
            return False

        # ── Home ─────────────────────────────────────────────────────
        self.state = State.HOMING
        self.get_logger().info(f'Homing to: {self.home_joints.tolist()}')
        if not self._move_to_joints(self.home_joints):
            detail = self.error_message
            self.error_message = f'Failed to home robot: {detail}'
            self.get_logger().error(self.error_message)
            self.state = State.ERROR
            return False

        # ── Normalize the trajectory relative to robot's actual joints ──
        # After homing the actual joint angles may differ by ±2π from the
        # planned values.  Normalize the entire trajectory chain to avoid
        # 2π jumps that cause state-tolerance violations.
        if self.current_joints is not None:
            ref = self.current_joints.copy()
            for pt in trajectory.points:
                normed = self._normalize_joints_to_ref(
                    np.array(pt.positions), ref
                )
                pt.positions = normed.tolist()
                ref = normed

        # ── Move to trajectory start ─────────────────────────────────
        start_joints = np.array(trajectory.points[0].positions)
        diff = np.max(np.abs(start_joints - self.current_joints))
        if diff > 0.01:
            self.get_logger().info(
                f'Moving to print start (diff={diff:.3f} rad)'
            )
            if not self._move_to_joints(start_joints):
                self.error_message = 'Failed to reach print start'
                self.state = State.ERROR
                return False

        # ── Execute with timed extruder events ───────────────────────
        self.state = State.PRINTING
        exec_start = time.time()
        cancel_event = threading.Event()

        def _extruder_scheduler():
            for evt_time, is_ext in extruder_events:
                elapsed = time.time() - exec_start
                wait = evt_time - elapsed
                if wait > 0:
                    if cancel_event.wait(timeout=wait):
                        return
                if is_ext:
                    self._set_extruder(enable=True, prime=True)
                    self.state = State.PRINTING
                else:
                    self._set_extruder(enable=False, retract=True)
                    self.state = State.TRAVEL_MOVE

        ext_thread = threading.Thread(
            target=_extruder_scheduler, daemon=True
        )
        ext_thread.start()

        total_t = (trajectory.points[-1].time_from_start.sec
                   + trajectory.points[-1].time_from_start.nanosec * 1e-9)
        self.get_logger().info(
            f'Executing continuous trajectory: '
            f'{len(trajectory.points)} points, {total_t:.1f}s'
        )

        success = self._execute_trajectory(trajectory)
        cancel_event.set()
        ext_thread.join(timeout=2.0)

        if not success:
            self.error_message = 'Trajectory execution failed'
            self.state = State.ERROR
            self._set_extruder(enable=False)
            return False

        # ── Done — retract above print, then home ─────────────────────
        self._set_extruder(enable=False, retract=True)
        self.state = State.HOMING
        self._retract_above_print()
        self._move_to_joints(self.home_joints)

        self.state = State.COMPLETED
        elapsed = time.time() - self.print_start_time
        self.get_logger().info(f'Print completed in {elapsed:.1f}s')
        return True

    def _wait_for_services(self, timeout: float = 30.0) -> bool:
        """Wait for required services.

        Uses a polling loop instead of wait_for_service() which can
        deadlock when called from inside a service callback.
        """
        services = [
            (self.ik_client, '/compute_ik'),
            (self.extruder_client, '/extruder_controller/set_extruder'),
        ]
        start = time.time()
        for client, name in services:
            self.get_logger().info(f'Checking service {name}...')
            while not client.service_is_ready():
                if (time.time() - start) > timeout:
                    self.get_logger().error(
                        f'Service {name} not available after {timeout}s'
                    )
                    return False
                time.sleep(0.1)
            self.get_logger().info(f'  {name} OK')

        self.get_logger().info('Checking trajectory action server...')
        while not self.trajectory_client.server_is_ready():
            if (time.time() - start) > timeout:
                self.get_logger().error('Trajectory action server not available')
                return False
            time.sleep(0.1)
        self.get_logger().info('  Trajectory action server OK')

        return True

    def _set_extruder(
        self, enable: bool = False, retract: bool = False,
        prime: bool = False, rate: float = 0.0
    ) -> bool:
        """Call extruder service."""
        request = SetExtruder.Request()
        request.enable = enable
        request.rate = rate
        request.retract = retract
        request.prime = prime

        future = self.extruder_client.call_async(request)
        wait_for_future(future, timeout_sec=5.0)

        if not future.done():
            self.get_logger().warn('Extruder service timeout')
            return False

        return future.result().success

    def _retract_above_print(self) -> bool:
        """Retract nozzle straight up above the print before homing.

        Uses FK to find the current nozzle-tip position, then IK to
        move straight up to a safe height.  This prevents the
        joint-space homing move from swinging the TCP through the
        printed part.
        """
        if self.current_joints is None:
            return False

        # Compute current nozzle TCP position via FK
        T_flange = self.trajectory_planner.kinematics.fk(self.current_joints)
        T_nozzle = T_flange @ self.tool_offset
        current_pos = T_nozzle[:3, 3]
        current_orient = T_nozzle[:3, :3]

        # Retract height: at least z_hop above the current Z, and at
        # least 50 mm above the print origin Z (clear the bed fixtures).
        retract_z = max(
            current_pos[2] + self.trajectory_planner.z_hop_height,
            self.print_frame[2, 3] + 0.10,  # 100 mm above print origin
        )

        self.get_logger().info(
            f'Retracting nozzle from Z={current_pos[2]:.4f} '
            f'to Z={retract_z:.4f}'
        )

        # Build retract pose: same XY and orientation, only Z changes
        retract_pos = current_pos.copy()
        retract_pos[2] = retract_z

        target_pose = self.trajectory_planner._build_target_pose(
            retract_pos, current_orient,
        )
        retract_joints = self.trajectory_planner._compute_ik(
            target_pose, self.current_joints, check_jump=False,
        )
        if retract_joints is None:
            self.get_logger().warn(
                'IK failed for retract pose — homing from current position'
            )
            return False

        return self._move_to_joints(retract_joints)

    def _execute_trajectory(self, trajectory: JointTrajectory) -> bool:
        """Execute a single joint trajectory."""
        self.get_logger().info(
            f'Sending trajectory with {len(trajectory.points)} points'
        )
        goal = FollowJointTrajectory.Goal()
        goal.trajectory = trajectory

        # Set generous path tolerance to avoid aborts during large motions.
        # The UR controller's default tolerance is often too strict for
        # arm-robot 3D printing trajectories.
        for jname in JOINT_NAMES:
            tol = JointTolerance()
            tol.name = jname
            tol.position = 0.2   # rad (~11 deg)
            tol.velocity = 0.0   # unchecked
            tol.acceleration = 0.0
            goal.path_tolerance.append(tol)

        future = self.trajectory_client.send_goal_async(goal)
        wait_for_future(future, timeout_sec=10.0)

        if not future.done():
            self.error_message = 'Trajectory goal send timeout'
            self.get_logger().error(self.error_message)
            return False

        goal_handle = future.result()
        if not goal_handle.accepted:
            self.error_message = 'Trajectory goal rejected'
            self.get_logger().error(self.error_message)
            return False

        self.get_logger().info('Trajectory goal accepted')

        # Wait for result
        if trajectory.points:
            last_time = (
                trajectory.points[-1].time_from_start.sec
                + trajectory.points[-1].time_from_start.nanosec * 1e-9
            )
        else:
            last_time = 5.0

        timeout = last_time + 30.0
        self.get_logger().info(
            f'Waiting for trajectory result (duration={last_time:.1f}s, '
            f'timeout={timeout:.1f}s)'
        )
        result_future = goal_handle.get_result_async()
        wait_for_future(result_future, timeout_sec=timeout)

        if not result_future.done():
            self.error_message = (
                f'Trajectory execution timeout after {timeout:.0f}s '
                f'(trajectory duration={last_time:.1f}s)'
            )
            self.get_logger().error(self.error_message)
            return False

        result = result_future.result()
        if result.result.error_code != 0:
            self.error_message = (
                f'Trajectory error code {result.result.error_code}: '
                f'{result.result.error_string}'
            )
            self.get_logger().error(self.error_message)
            return False

        self.get_logger().info('Trajectory segment completed')
        return True

    # UR joint limits: all joints +/- 2*pi (360 deg)
    UR_JOINT_LIMIT = 2 * np.pi

    @staticmethod
    def _normalize_joints_to_ref(joints: np.ndarray, ref: np.ndarray) -> np.ndarray:
        """Normalize each joint angle to within +/-pi of a reference.

        The UR controller and IK solver may represent the same physical
        joint angle with values that differ by 2*pi.  Before computing
        differences or sending trajectories we must ensure continuity.
        After normalization, clamp to UR joint limits (±2*pi).
        """
        out = joints.copy()
        for j in range(len(out)):
            while out[j] - ref[j] > np.pi:
                out[j] -= 2 * np.pi
            while out[j] - ref[j] < -np.pi:
                out[j] += 2 * np.pi
        # Clamp within UR hardware limits to prevent protective stops
        limit = PrintNode.UR_JOINT_LIMIT
        out = np.clip(out, -limit, limit)
        return out

    def _move_to_joints(self, target_joints: np.ndarray) -> bool:
        """Move robot to target joint configuration with intermediate points."""
        if self.current_joints is None:
            self.error_message = 'No joint state available'
            return False

        # Normalize target relative to current to avoid 2*pi wrist wraps
        target_joints = self._normalize_joints_to_ref(
            target_joints, self.current_joints
        )

        joint_diff = np.abs(target_joints - self.current_joints)
        max_diff = np.max(joint_diff)
        # Conservative speed: ~0.3 rad/s max joint velocity
        duration = max(3.0, max_diff / 0.3)

        trajectory = JointTrajectory()
        trajectory.joint_names = JOINT_NAMES

        # Generate intermediate waypoints via linear interpolation for
        # smoother motion that the controller can track without violating
        # path tolerance.  Use trapezoidal velocity profile: ramp up,
        # cruise, ramp down — so the robot moves smoothly instead of
        # stopping at each intermediate point.
        n_points = max(5, int(duration * 2))  # ~2 points per second
        start = self.current_joints
        limit = self.UR_JOINT_LIMIT
        delta = target_joints - start
        for i in range(n_points + 1):
            frac = i / n_points
            t = frac * duration
            positions = start + delta * frac
            # Clamp interpolated positions within UR joint limits
            positions = np.clip(positions, -limit, limit)

            # Compute velocity: zero at start/end, constant cruise in between
            if i == 0 or i == n_points:
                velocities = [0.0] * 6
            else:
                velocities = (delta / duration).tolist()

            pt = JointTrajectoryPoint()
            pt.positions = positions.tolist()
            pt.velocities = velocities
            pt.time_from_start = Duration(
                sec=int(t),
                nanosec=int((t % 1) * 1e9),
            )
            trajectory.points.append(pt)

        return self._execute_trajectory(trajectory)


def main(args=None):
    rclpy.init(args=args)
    node = PrintNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
