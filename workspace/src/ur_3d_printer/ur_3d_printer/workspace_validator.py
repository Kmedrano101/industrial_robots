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
Workspace Validator

Pre-flight reachability checks for 3D printing toolpaths.
Validates IK feasibility, workspace bounds, and singularity proximity.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose

from ur_kinematics_msgs.srv import ComputeIK, ComputeJacobian, GetRobotInfo

from .toolpath import Toolpath, Waypoint
from .trajectory_planner import rotation_matrix_to_quaternion


@dataclass
class ValidationResult:
    """Result of workspace validation."""
    is_valid: bool = True
    unreachable_waypoints: List[int] = field(default_factory=list)  # line numbers
    unreachable_positions: List[np.ndarray] = field(default_factory=list)
    singular_waypoints: List[int] = field(default_factory=list)  # line numbers
    out_of_bounds_waypoints: List[int] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    total_checked: int = 0
    total_reachable: int = 0

    @property
    def reachability_pct(self) -> float:
        if self.total_checked == 0:
            return 0.0
        return 100.0 * self.total_reachable / self.total_checked


class WorkspaceValidator:
    """Validate toolpath reachability before printing.

    Checks performed:
      - Rectangular workspace envelope (workspace_bounds)
      - Radial reach envelope (min/max reach from robot base)
      - IK feasibility for sampled waypoints
      - Jacobian singularity proximity via minimum singular value

    Args:
        node: ROS2 node for service clients and logging.
        tool_offset: 4x4 flange-to-nozzle transform.
        workspace_bounds: ((x_min, y_min, z_min), (x_max, y_max, z_max)) in robot frame.
        singularity_threshold: Minimum acceptable Jacobian singular value (sigma_min).
            Values approaching 0 indicate a kinematic singularity.
            Typical range: 0.02 (very close) to 0.1 (comfortably clear).
        sample_every_n: Check every Nth waypoint (1 = all, 10 = fast sampling).
        min_reach_radius: Minimum radial distance from robot base_link (m).
            Points inside this sphere are near the shoulder singularity.
        max_reach_radius: Maximum radial distance from robot base_link (m).
            Points outside are beyond the arm's reach.
    """

    def __init__(
        self,
        node: Node,
        tool_offset: Optional[np.ndarray] = None,
        workspace_bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None,
        singularity_threshold: float = 0.05,
        sample_every_n: int = 10,
        min_reach_radius: float = 0.0,
        max_reach_radius: float = float('inf'),
    ):
        self.node = node
        self.tool_offset = tool_offset if tool_offset is not None else np.eye(4)
        self.workspace_bounds = workspace_bounds
        self.singularity_threshold = singularity_threshold
        self.sample_every_n = sample_every_n
        self.min_reach_radius = min_reach_radius
        self.max_reach_radius = max_reach_radius

        self.ik_client = node.create_client(
            ComputeIK, '/ur_kinematics_server/compute_ik'
        )
        self.jacobian_client = node.create_client(
            ComputeJacobian, '/ur_kinematics_server/compute_jacobian'
        )
        self.robot_info_client = node.create_client(
            GetRobotInfo, '/ur_kinematics_server/get_robot_info'
        )

    def validate(
        self,
        toolpath: Toolpath,
        seed: np.ndarray,
    ) -> ValidationResult:
        """Run full validation on a toolpath.

        Args:
            toolpath: Toolpath to validate.
            seed: Initial joint configuration for IK.

        Returns:
            ValidationResult with details.
        """
        result = ValidationResult()

        # Transform waypoints to robot frame
        robot_waypoints = toolpath.transform_to_robot_frame()

        if not robot_waypoints:
            result.messages.append('Empty toolpath')
            result.is_valid = False
            return result

        # Check bounding box and reach radius against workspace bounds
        self._check_bounds(toolpath, result)
        self._check_reach(toolpath, result)

        # Sample waypoints and check IK + singularity
        sampled = robot_waypoints[::self.sample_every_n]
        result.total_checked = len(sampled)
        current_seed = seed.copy()

        for wp in sampled:
            # Check IK feasibility
            joints = self._check_ik(wp, current_seed)

            if joints is None:
                result.unreachable_waypoints.append(wp.line_number)
                result.unreachable_positions.append(wp.position.copy())
                result.is_valid = False
            else:
                result.total_reachable += 1
                current_seed = joints

                # Check singularity
                if self._check_singularity(joints):
                    result.singular_waypoints.append(wp.line_number)

        # Summary messages
        if result.unreachable_waypoints:
            result.messages.append(
                f'{len(result.unreachable_waypoints)} unreachable waypoints '
                f'(lines: {result.unreachable_waypoints[:5]}...)'
            )
        if result.singular_waypoints:
            result.messages.append(
                f'{len(result.singular_waypoints)} waypoints near singularity '
                f'(lines: {result.singular_waypoints[:5]}...)'
            )
        if result.out_of_bounds_waypoints:
            result.messages.append(
                f'{len(result.out_of_bounds_waypoints)} waypoints out of workspace bounds'
            )

        result.messages.append(
            f'Reachability: {result.reachability_pct:.1f}% '
            f'({result.total_reachable}/{result.total_checked})'
        )

        self.node.get_logger().info(
            f'Validation complete: {"PASS" if result.is_valid else "FAIL"} - '
            + '; '.join(result.messages)
        )

        return result

    def _check_bounds(self, toolpath: Toolpath, result: ValidationResult):
        """Check bounding box against rectangular workspace bounds."""
        if self.workspace_bounds is None:
            return

        bb_min, bb_max = toolpath.bounding_box_robot_frame()
        ws_min, ws_max = self.workspace_bounds

        for i, axis in enumerate(['X', 'Y', 'Z']):
            if bb_min[i] < ws_min[i]:
                result.messages.append(
                    f'Toolpath {axis}_min ({bb_min[i]:.3f}m) below '
                    f'workspace bound ({ws_min[i]:.3f}m)'
                )
                result.is_valid = False
            if bb_max[i] > ws_max[i]:
                result.messages.append(
                    f'Toolpath {axis}_max ({bb_max[i]:.3f}m) above '
                    f'workspace bound ({ws_max[i]:.3f}m)'
                )
                result.is_valid = False

    def _check_reach(self, toolpath: Toolpath, result: ValidationResult):
        """Check radial reach envelope — arm-robot specific.

        Unlike a Cartesian printer whose workspace is a rectangular box, an
        arm robot's reachable space is approximately a thick shell between
        min_reach_radius and max_reach_radius.  The inner dead zone exists
        because the wrist must pass through the shoulder axis to reach points
        directly above/below the base, creating a wrist singularity.
        """
        if self.min_reach_radius <= 0.0 and np.isinf(self.max_reach_radius):
            return

        robot_wps = toolpath.transform_to_robot_frame()
        too_close, too_far = [], []

        for wp in robot_wps[::self.sample_every_n]:
            r = float(np.linalg.norm(wp.position))
            if r < self.min_reach_radius:
                too_close.append(wp.line_number)
            elif r > self.max_reach_radius:
                too_far.append(wp.line_number)

        if too_close:
            result.messages.append(
                f'{len(too_close)} waypoints inside minimum reach radius '
                f'{self.min_reach_radius:.3f}m (shoulder singularity zone): '
                f'lines {too_close[:3]}'
            )
            result.is_valid = False

        if too_far:
            result.messages.append(
                f'{len(too_far)} waypoints outside maximum reach radius '
                f'{self.max_reach_radius:.3f}m: lines {too_far[:3]}'
            )
            result.is_valid = False

    def _check_ik(
        self, waypoint: Waypoint, seed: np.ndarray
    ) -> Optional[np.ndarray]:
        """Check if IK is feasible for a waypoint."""
        # Build target pose with tool offset
        T_nozzle = np.eye(4)
        T_nozzle[:3, :3] = waypoint.orientation
        T_nozzle[:3, 3] = waypoint.position
        T_tool_inv = np.linalg.inv(self.tool_offset)
        T_flange = T_nozzle @ T_tool_inv

        pose = Pose()
        pose.position.x = float(T_flange[0, 3])
        pose.position.y = float(T_flange[1, 3])
        pose.position.z = float(T_flange[2, 3])
        pose.orientation = rotation_matrix_to_quaternion(T_flange[:3, :3])

        request = ComputeIK.Request()
        request.target_pose = pose
        request.seed_configuration = seed.tolist()
        request.method = 'lm'
        request.max_iterations = 100
        request.tolerance = 1e-6
        request.check_limits = True

        future = self.ik_client.call_async(request)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=2.0)

        if not future.done():
            return None

        response = future.result()
        if not response.success or response.num_solutions == 0:
            return None

        return np.array(response.solutions[0].joints)

    def _check_singularity(self, joints: np.ndarray) -> bool:
        """Check if joint configuration is near a singularity.

        Returns True if near singularity.
        """
        request = ComputeJacobian.Request()
        request.joint_positions = joints.tolist()
        request.frame = 'space'

        future = self.jacobian_client.call_async(request)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=2.0)

        if not future.done():
            return False

        response = future.result()
        if not response.success:
            return False

        # Use the minimum singular value of the Jacobian as the singularity
        # metric.  sigma_min → 0 means singular (unbounded joint velocities
        # for finite Cartesian velocities).  This is more physically
        # meaningful than the condition number (which is sigma_max/sigma_min
        # and grows unboundedly near singularity).
        J = np.array(response.jacobian.data).reshape(6, 6)
        sigma_min = float(np.linalg.svd(J, compute_uv=False)[-1])
        return sigma_min < self.singularity_threshold
