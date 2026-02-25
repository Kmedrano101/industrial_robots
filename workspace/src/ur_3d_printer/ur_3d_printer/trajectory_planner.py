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
Trajectory Planner

Converts Cartesian toolpath waypoints to joint-space trajectories via IK.
Uses existing ComputeIK service with seed chaining for continuous solutions.
"""

import time
from typing import List, Optional, Tuple
import numpy as np

from rclpy.node import Node
from geometry_msgs.msg import Pose, Quaternion
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from std_msgs.msg import Header

from ur_kinematics_msgs.srv import ComputeIK, ComputeJacobian

from ur_kinematics_node.robot_parameters import load_robot_parameters
from ur_kinematics_node.screw_kinematics import URScrewKinematics

from .toolpath import Waypoint, Toolpath
from .velocity_profiler import VelocityProfiler


# Default nozzle-down orientation: rotate 180 deg around X axis
# This points the tool Z-axis downward (into the print bed)
NOZZLE_DOWN_QUATERNION = Quaternion(x=1.0, y=0.0, z=0.0, w=0.0)

# UR joint names
JOINT_NAMES = [
    'shoulder_pan_joint',
    'shoulder_lift_joint',
    'elbow_joint',
    'wrist_1_joint',
    'wrist_2_joint',
    'wrist_3_joint',
]


def rotation_matrix_to_quaternion(R: np.ndarray) -> Quaternion:
    """Convert 3x3 rotation matrix to geometry_msgs Quaternion."""
    # Using Shepperd's method
    trace = R[0, 0] + R[1, 1] + R[2, 2]

    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2, 1] - R[1, 2]) * s
        y = (R[0, 2] - R[2, 0]) * s
        z = (R[1, 0] - R[0, 1]) * s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s

    q = Quaternion()
    q.x = float(x)
    q.y = float(y)
    q.z = float(z)
    q.w = float(w)
    return q


class TrajectoryPlanner:
    """Convert Cartesian toolpath to joint trajectories via IK.

    Uses IK seed chaining: first waypoint uses current joint state,
    subsequent waypoints use the previous IK solution as seed.

    Args:
        node: ROS2 node for service clients and logging.
        tool_offset: 4x4 transform from flange to nozzle tip.
        ik_method: IK solver method ('lm', 'newton', 'analytical').
        ik_max_iterations: Max iterations for numerical IK.
        ik_tolerance: Convergence tolerance for IK.
        max_segment_length: Max distance between waypoints for densification (m).
    """

    def __init__(
        self,
        node: Node,
        tool_offset: Optional[np.ndarray] = None,
        robot_model: str = 'ur5e',
        ik_method: str = 'lm',
        ik_max_iterations: int = 100,
        ik_tolerance: float = 1e-6,
        ik_timeout: float = 5.0,
        max_segment_length: float = 0.002,
        # ── Arm-robot specific ──────────────────────────────────────────
        z_hop_enabled: bool = True,
        z_hop_height: float = 0.005,
        max_joint_jump: float = 0.5,
        joint_velocity_limits: Optional[List[float]] = None,
        singularity_velocity_scale: float = 0.3,
    ):
        self.node = node
        self.tool_offset = tool_offset if tool_offset is not None else np.eye(4)
        self.ik_method = ik_method
        self.ik_max_iterations = ik_max_iterations
        self.ik_tolerance = ik_tolerance
        self.ik_timeout = ik_timeout
        self.max_segment_length = max_segment_length

        # Arm-specific
        self.z_hop_enabled = z_hop_enabled
        self.z_hop_height = z_hop_height
        self.max_joint_jump = max_joint_jump
        self.joint_velocity_limits = (
            np.array(joint_velocity_limits)
            if joint_velocity_limits is not None
            else np.full(6, np.pi)   # default: pi rad/s per joint
        )
        self.singularity_velocity_scale = singularity_velocity_scale

        # Local IK solver — avoids ROS service overhead and callback
        # deadlocks when called from inside a service callback.
        params = load_robot_parameters(model_name=robot_model)
        self.kinematics = URScrewKinematics(params)

        # Jacobian service client (still used for singularity checks)
        self.jacobian_client = node.create_client(
            ComputeJacobian, '/compute_jacobian',
        )

        self.velocity_profiler = VelocityProfiler()

    def configure_profiler(self, **kwargs):
        """Update velocity profiler parameters."""
        for key, val in kwargs.items():
            if hasattr(self.velocity_profiler, key):
                setattr(self.velocity_profiler, key, val)

    def plan_toolpath(
        self,
        toolpath: Toolpath,
        current_joints: np.ndarray,
    ) -> List[Tuple[JointTrajectory, bool]]:
        """Convert entire toolpath to joint trajectories.

        Splits toolpath into segments at travel/extrusion boundaries.
        Each segment becomes a separate JointTrajectory.

        Args:
            toolpath: The Cartesian toolpath to convert.
            current_joints: Current robot joint configuration (6,).

        Returns:
            List of (JointTrajectory, is_extrusion) tuples. Each trajectory
            is a multi-point trajectory for one continuous segment.
        """
        # Transform waypoints to robot frame
        robot_waypoints = toolpath.transform_to_robot_frame()

        if not robot_waypoints:
            return []

        # Densify waypoints for smooth Cartesian path
        robot_waypoints = self.velocity_profiler.densify_waypoints(
            robot_waypoints, self.max_segment_length
        )

        # Insert z-hop waypoints around every travel move.
        # This lifts the nozzle above the print before each travel and
        # lowers it back down on arrival — critical for arm robots because
        # travel paths are curved and clearance is not guaranteed.
        if self.z_hop_enabled:
            robot_waypoints = self._apply_z_hop(robot_waypoints)

        # Split into segments at travel/extrusion boundaries
        segments = self._split_into_segments(robot_waypoints)

        # Convert each segment to joint trajectory
        trajectories = []
        seed = current_joints.copy()

        for segment_wps, is_extrusion in segments:
            trajectory = self._plan_segment(segment_wps, seed)
            if trajectory is not None:
                trajectories.append((trajectory, is_extrusion))
                # Update seed to last point of this trajectory
                if trajectory.points:
                    seed = np.array(trajectory.points[-1].positions)

        return trajectories

    def _apply_z_hop(self, waypoints: List[Waypoint]) -> List[Waypoint]:
        """Insert lift/lower waypoints at travel/extrusion boundaries.

        At each extrusion→travel transition a waypoint is inserted that
        lifts the nozzle by z_hop_height in Z before the move starts.
        At each travel→extrusion transition a waypoint is inserted that
        arrives above the target at z_hop_height, then the original
        waypoint lowers to the correct Z.

        The hop waypoints are marked is_travel=True so the velocity
        profiler assigns travel feed rates to them.
        """
        if len(waypoints) < 2:
            return waypoints

        result: List[Waypoint] = []
        for i, wp in enumerate(waypoints):
            result.append(wp)

            if i >= len(waypoints) - 1:
                continue

            next_wp = waypoints[i + 1]
            if not wp.is_travel and next_wp.is_travel:
                # Extrusion → travel: lift above current position
                lift = Waypoint(
                    position=np.array([
                        wp.position[0],
                        wp.position[1],
                        wp.position[2] + self.z_hop_height,
                    ]),
                    orientation=wp.orientation.copy(),
                    feed_rate=self.velocity_profiler.max_travel_velocity,
                    is_travel=True,
                    layer_index=wp.layer_index,
                    line_number=wp.line_number,
                )
                result.append(lift)

            elif wp.is_travel and not next_wp.is_travel:
                # Travel → extrusion: arrive hopped, next waypoint lowers
                lower = Waypoint(
                    position=np.array([
                        next_wp.position[0],
                        next_wp.position[1],
                        next_wp.position[2] + self.z_hop_height,
                    ]),
                    orientation=next_wp.orientation.copy(),
                    feed_rate=self.velocity_profiler.max_travel_velocity,
                    is_travel=True,
                    layer_index=next_wp.layer_index,
                    line_number=next_wp.line_number,
                )
                result.append(lower)

        return result

    def plan_single_waypoint(
        self,
        waypoint: Waypoint,
        seed: np.ndarray,
        print_frame: np.ndarray,
    ) -> Optional[np.ndarray]:
        """Compute IK for a single waypoint.

        Args:
            waypoint: Target waypoint in print frame.
            seed: Seed joint configuration.
            print_frame: 4x4 print-to-robot transform.

        Returns:
            Joint configuration (6,) or None if IK fails.
        """
        # Transform to robot frame
        R = print_frame[:3, :3]
        t = print_frame[:3, 3]
        robot_pos = R @ waypoint.position + t
        robot_orient = R @ waypoint.orientation

        target_pose = self._build_target_pose(robot_pos, robot_orient)
        return self._compute_ik(target_pose, seed)

    def _split_into_segments(
        self, waypoints: List[Waypoint]
    ) -> List[Tuple[List[Waypoint], bool]]:
        """Split waypoints into segments at travel/extrusion boundaries.

        Returns list of (waypoints, is_extrusion) tuples.
        """
        if not waypoints:
            return []

        segments = []
        current_segment = [waypoints[0]]
        current_is_extrusion = not waypoints[0].is_travel

        for i in range(1, len(waypoints)):
            wp = waypoints[i]
            is_extrusion = not wp.is_travel

            if is_extrusion != current_is_extrusion:
                # Boundary: start new segment, include current wp in both
                segments.append((current_segment, current_is_extrusion))
                current_segment = [waypoints[i - 1]]  # Overlap for continuity
                current_is_extrusion = is_extrusion

            current_segment.append(wp)

        if current_segment:
            segments.append((current_segment, current_is_extrusion))

        return segments

    def _plan_segment(
        self, waypoints: List[Waypoint], seed: np.ndarray
    ) -> Optional[JointTrajectory]:
        """Convert a single segment of waypoints to a JointTrajectory.

        Uses IK seed chaining for continuity.
        """
        if not waypoints:
            return None

        # Compute timestamps
        timestamps = self.velocity_profiler.compute_timestamps(waypoints)

        # Compute IK for each waypoint with seed chaining
        joint_configs = []
        current_seed = seed.copy()

        for i, wp in enumerate(waypoints):
            target_pose = self._build_target_pose(wp.position, wp.orientation)
            # Skip joint-jump check for the first waypoint of each segment:
            # the seed comes from a different segment or the home config, so
            # a large jump is expected (travel move) rather than an IK branch
            # switch.
            check_jump = (i > 0)
            joints = self._compute_ik(target_pose, current_seed, check_jump)

            if joints is None:
                self.node.get_logger().warn(
                    f'IK failed for waypoint at line {wp.line_number}, '
                    f'position {wp.position}'
                )
                return None

            joint_configs.append(joints)
            current_seed = joints  # Seed chaining

        # Compute joint velocities via finite differences
        joint_velocities = self._compute_joint_velocities(
            joint_configs, timestamps
        )

        # Build JointTrajectory message
        trajectory = JointTrajectory()
        trajectory.header = Header()
        trajectory.joint_names = JOINT_NAMES

        for i, (joints, vel, t) in enumerate(
            zip(joint_configs, joint_velocities, timestamps)
        ):
            point = JointTrajectoryPoint()
            point.positions = joints.tolist()
            point.velocities = vel.tolist()
            point.time_from_start = Duration(
                sec=int(t),
                nanosec=int((t % 1) * 1e9),
            )
            trajectory.points.append(point)

        return trajectory

    def _build_target_pose(
        self, position: np.ndarray, orientation: np.ndarray
    ) -> Pose:
        """Build IK target pose from position and orientation.

        Applies tool offset (flange-to-nozzle) to get flange pose.
        """
        # Build nozzle pose in robot frame
        T_nozzle = np.eye(4)
        T_nozzle[:3, :3] = orientation
        T_nozzle[:3, 3] = position

        # Account for tool offset: T_flange = T_nozzle * inv(T_tool)
        T_tool_inv = np.linalg.inv(self.tool_offset)
        T_flange = T_nozzle @ T_tool_inv

        # Build ROS Pose message
        pose = Pose()
        pose.position.x = float(T_flange[0, 3])
        pose.position.y = float(T_flange[1, 3])
        pose.position.z = float(T_flange[2, 3])
        pose.orientation = rotation_matrix_to_quaternion(T_flange[:3, :3])

        return pose

    def _compute_ik(
        self, target_pose: Pose, seed: np.ndarray,
        check_jump: bool = True,
    ) -> Optional[np.ndarray]:
        """Compute IK locally (no ROS service overhead)."""
        # Build 4x4 target from Pose
        q = target_pose.orientation
        x, y, z, w = q.x, q.y, q.z, q.w
        n = np.sqrt(x*x + y*y + z*z + w*w)
        x, y, z, w = x/n, y/n, z/n, w/n

        T_target = np.eye(4)
        T_target[:3, :3] = np.array([
            [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
            [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
            [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]
        ])
        T_target[:3, 3] = [
            target_pose.position.x,
            target_pose.position.y,
            target_pose.position.z,
        ]

        if self.ik_method == 'newton':
            solution = self.kinematics.ik_newton_raphson(
                T_target, seed, self.ik_tolerance, self.ik_max_iterations,
            )
        else:
            solution = self.kinematics.ik_levenberg_marquardt(
                T_target, seed, self.ik_tolerance, self.ik_max_iterations,
            )

        if not solution.is_valid:
            return None

        joints = solution.joints.copy()

        # Normalize each joint angle to be within ±π of the seed.
        # The IK solver may return a valid solution that differs from the
        # seed by ±2π (wrist wrap-around).  Without normalization these
        # 2π jumps cause false "joint jump" rejections and violent motion.
        for j in range(6):
            while joints[j] - seed[j] > np.pi:
                joints[j] -= 2 * np.pi
            while joints[j] - seed[j] < -np.pi:
                joints[j] += 2 * np.pi

        if not self.kinematics.check_joint_limits(joints):
            return None

        # Joint-jump check: a large jump from the seed means the IK solver
        # found a solution on a different kinematic branch (elbow flip,
        # wrist flip).  Executing such a jump causes a violent, non-Cartesian
        # motion that is unsafe and will likely collide with the print.
        if check_jump and self.max_joint_jump > 0.0:
            jump = np.max(np.abs(joints - seed))
            if jump > self.max_joint_jump:
                self.node.get_logger().warn(
                    f'IK joint jump {jump:.3f} rad exceeds max_joint_jump '
                    f'{self.max_joint_jump:.3f} rad — possible IK branch '
                    f'switch (elbow/wrist flip).  Skipping waypoint.'
                )
                return None

        return joints

    def _compute_joint_velocities(
        self,
        joint_configs: List[np.ndarray],
        timestamps: List[float],
    ) -> List[np.ndarray]:
        """Compute joint velocities via finite differences, enforcing per-joint limits.

        Uses central differences for interior points,
        forward/backward for endpoints.

        After computing raw velocities the method checks whether any joint
        exceeds joint_velocity_limits.  If so, all inter-point time intervals
        are scaled up uniformly so the fastest joint is at its limit.  This
        preserves Cartesian path shape while keeping hardware within spec.
        """
        n = len(joint_configs)
        velocities = []

        for i in range(n):
            if n == 1:
                velocities.append(np.zeros(6))
            elif i == 0:
                dt = timestamps[1] - timestamps[0]
                vel = (joint_configs[1] - joint_configs[0]) / dt if dt > 1e-9 else np.zeros(6)
                velocities.append(vel)
            elif i == n - 1:
                velocities.append(np.zeros(6))
            else:
                dt = timestamps[i + 1] - timestamps[i - 1]
                diff = joint_configs[i + 1] - joint_configs[i - 1]
                vel = diff / dt if dt > 1e-9 else np.zeros(6)
                velocities.append(vel)

        # Enforce per-joint velocity limits by computing the required time
        # stretch factor: if any joint is too fast, slow down the whole segment.
        max_ratio = 1.0
        for vel in velocities:
            with np.errstate(divide='ignore', invalid='ignore'):
                ratios = np.where(
                    self.joint_velocity_limits > 1e-9,
                    np.abs(vel) / self.joint_velocity_limits,
                    0.0,
                )
            max_ratio = max(max_ratio, float(np.max(ratios)))

        if max_ratio > 1.0:
            self.node.get_logger().debug(
                f'Joint velocity limit reached: scaling segment by {max_ratio:.2f}x'
            )
            # Stretch timestamps to reduce all joint velocities proportionally
            t0 = timestamps[0]
            timestamps_scaled = [t0 + (t - t0) * max_ratio for t in timestamps]
            # Recompute velocities with stretched timestamps
            velocities = []
            for i in range(n):
                if n == 1 or i == n - 1:
                    velocities.append(np.zeros(6))
                elif i == 0:
                    dt = timestamps_scaled[1] - timestamps_scaled[0]
                    diff = joint_configs[1] - joint_configs[0]
                    vel = diff / dt if dt > 1e-9 else np.zeros(6)
                    velocities.append(vel)
                else:
                    dt = timestamps_scaled[i + 1] - timestamps_scaled[i - 1]
                    diff = joint_configs[i + 1] - joint_configs[i - 1]
                    vel = diff / dt if dt > 1e-9 else np.zeros(6)
                    velocities.append(vel)
            # Update timestamps in-place so the caller gets the stretched values
            for i in range(n):
                timestamps[i] = timestamps_scaled[i]

        return velocities
