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
Mock Trajectory Controller

Standalone simulation node that serves the FollowJointTrajectory action and
replays received joint trajectories as joint state publications so RViz shows
the simulated robot actually following the print toolpath.

Usage:
    ros2 run ur_3d_printer mock_controller
    ros2 run ur_3d_printer mock_controller --ros-args -p speed_scale:=5.0
"""

import threading
import time

import rclpy
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Header

from control_msgs.action import FollowJointTrajectory


def _to_sec(duration_msg):
    """Convert ROS duration message to seconds float."""
    return duration_msg.sec + duration_msg.nanosec * 1e-9


class MockTrajectoryController(Node):
    """
    Mock joint trajectory controller for standalone 3D printer simulation.

    Accepts FollowJointTrajectory action goals from print_node and replays
    each trajectory by stepping through waypoints at the correct timing,
    publishing joint states so the robot model in RViz animates along the
    toolpath.

    Parameters:
        publish_rate: Rate at which joint states are published (Hz).
        speed_scale: Trajectory playback speed multiplier.
            1.0 = real time, 5.0 = 5× faster (useful for long prints).
        home_joints: Initial joint positions (6 values, radians).
    """

    JOINT_NAMES = [
        'shoulder_pan_joint',
        'shoulder_lift_joint',
        'elbow_joint',
        'wrist_1_joint',
        'wrist_2_joint',
        'wrist_3_joint',
    ]

    HOME = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]

    def __init__(self):
        super().__init__('mock_trajectory_controller')

        self.declare_parameter('publish_rate', 50.0)
        self.declare_parameter('speed_scale', 1.0)
        self.declare_parameter('home_joints', self.HOME)

        publish_rate = self.get_parameter('publish_rate').value
        self._speed_scale = self.get_parameter('speed_scale').value
        home = list(self.get_parameter('home_joints').value)
        if len(home) == 6:
            self._positions = home
        else:
            self._positions = list(self.HOME)

        self._lock = threading.Lock()
        self._executing = False

        # Joint state publisher
        self._js_pub = self.create_publisher(JointState, '/joint_states', 10)

        # Action server — ReentrantCallbackGroup so execute_cb can block
        # while the timer callback keeps publishing joint states.
        self._action_server = ActionServer(
            self,
            FollowJointTrajectory,
            '/joint_trajectory_controller/follow_joint_trajectory',
            self._execute_cb,
            callback_group=ReentrantCallbackGroup(),
        )

        # Periodic joint state publisher
        self._timer = self.create_timer(
            1.0 / publish_rate, self._publish_cb
        )

        self.get_logger().info(
            f'Mock trajectory controller ready '
            f'(speed_scale={self._speed_scale:.1f}x, '
            f'publish_rate={publish_rate:.0f} Hz)'
        )

    # ── Publishers ────────────────────────────────────────────────────────────

    def _publish_cb(self):
        msg = JointState()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.JOINT_NAMES
        with self._lock:
            msg.position = list(self._positions)
        msg.velocity = [0.0] * 6
        msg.effort = [0.0] * 6
        self._js_pub.publish(msg)

    # ── Action server ─────────────────────────────────────────────────────────

    def _execute_cb(self, goal_handle):
        """Replay a JointTrajectory goal, publishing joint states over time."""
        traj = goal_handle.request.trajectory
        joint_names = list(traj.joint_names)

        # Sort trajectory points by time
        points = sorted(
            traj.points,
            key=lambda p: _to_sec(p.time_from_start)
        )

        if not points:
            goal_handle.succeed()
            result = FollowJointTrajectory.Result()
            result.error_code = FollowJointTrajectory.Result.SUCCESSFUL
            return result

        # Map our JOINT_NAMES → trajectory indices
        idx_map = []
        for name in self.JOINT_NAMES:
            idx_map.append(
                joint_names.index(name) if name in joint_names else None
            )

        n_pts = len(points)
        total_dur = _to_sec(points[-1].time_from_start)
        scaled_dur = total_dur / self._speed_scale
        self.get_logger().info(
            f'Executing trajectory: {n_pts} points, '
            f'{total_dur:.1f}s ({scaled_dur:.1f}s scaled)'
        )

        self._executing = True
        start = time.monotonic()

        for pt in points:
            t_target = _to_sec(pt.time_from_start) / self._speed_scale

            # Sleep until this waypoint's target time
            remaining = t_target - (time.monotonic() - start)
            if remaining > 0.0:
                time.sleep(remaining)

            # Respect cancellation requests
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                self._executing = False
                result = FollowJointTrajectory.Result()
                result.error_code = FollowJointTrajectory.Result.GOAL_TOLERANCE_VIOLATED
                return result

            # Update joint positions
            with self._lock:
                for i, traj_idx in enumerate(idx_map):
                    if traj_idx is not None and traj_idx < len(pt.positions):
                        self._positions[i] = pt.positions[traj_idx]

        self._executing = False
        goal_handle.succeed()
        result = FollowJointTrajectory.Result()
        result.error_code = FollowJointTrajectory.Result.SUCCESSFUL
        return result


def main(args=None):
    rclpy.init(args=args)
    node = MockTrajectoryController()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
