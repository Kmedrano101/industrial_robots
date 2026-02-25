#!/usr/bin/env python3
"""Calibration test: move TCP nozzle tip to the center of the print bed.

Computes IK for the bed center with nozzle-down orientation, then sends
a FollowJointTrajectory action to move the robot there.  This verifies
that print_origin, tool_offset, and orientation parameters are correct.

The nozzle tip should end up touching (or just above) the center of the
print bed surface visible in RViz.

Usage:
    python3 test_calibration.py                  # default: nozzle on bed surface
    python3 test_calibration.py --z-above 0.01   # 10 mm above bed surface
"""

import argparse
import sys
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from builtin_interfaces.msg import Duration

from ur_kinematics_node.robot_parameters import load_robot_parameters
from ur_kinematics_node.screw_kinematics import URScrewKinematics

JOINT_NAMES = [
    'shoulder_pan_joint',
    'shoulder_lift_joint',
    'elbow_joint',
    'wrist_1_joint',
    'wrist_2_joint',
    'wrist_3_joint',
]

# IK seed: manually positioned nozzle-down at bed center.
# Captured from the robot after manual teach to bed center.
PRINT_SEED = np.array([-0.4612, -1.3625, 2.7248, -2.9332, -1.5708, -2.0312])


class CalibrationNode(Node):
    def __init__(self, args):
        super().__init__('calibration_test')
        self.args = args

        # Parameters matching print_params.yaml
        self.print_origin = np.array([-0.3, 0.0, -0.01])  # bed center
        self.tool_offset_xyz = np.array([0.0, 0.0, 0.105])  # matches extruder URDF

        # Nozzle-down orientation: Rx(pi) = [[1,0,0],[0,-1,0],[0,0,-1]]
        self.nozzle_down_R = np.array([
            [1, 0, 0],
            [0, -1, 0],
            [0, 0, -1],
        ], dtype=np.float64)

        # IK solver (corrected model matches URDF exactly)
        params = load_robot_parameters(model_name='ur5e')
        self.kinematics = URScrewKinematics(params)

        # Tool offset: just the physical geometry (no FK-to-URDF correction needed).
        self.tool_offset = np.eye(4)
        self.tool_offset[:3, 3] = self.tool_offset_xyz

        # Current joints
        self.current_joints = None
        self.joint_sub = self.create_subscription(
            JointState, '/joint_states', self._joint_cb, 10
        )

        # Trajectory action client
        self.traj_client = ActionClient(
            self, FollowJointTrajectory,
            '/joint_trajectory_controller/follow_joint_trajectory'
        )

    def _joint_cb(self, msg):
        positions = []
        for name in JOINT_NAMES:
            if name in msg.name:
                idx = msg.name.index(name)
                positions.append(msg.position[idx])
        if len(positions) == 6:
            self.current_joints = np.array(positions)

    def _solve_ik(self, T_target):
        """Solve IK with multiple seed attempts."""
        seeds = []
        if self.current_joints is not None:
            seeds.append(self.current_joints)
        seeds.append(PRINT_SEED)

        for i, seed in enumerate(seeds):
            solution = self.kinematics.ik_levenberg_marquardt(
                T_target, seed, tolerance=1e-6, max_iterations=200,
            )
            if solution.is_valid:
                joints = solution.joints.copy()
                # Normalize relative to seed
                for j in range(6):
                    while joints[j] - seed[j] > np.pi:
                        joints[j] -= 2 * np.pi
                    while joints[j] - seed[j] < -np.pi:
                        joints[j] += 2 * np.pi
                self.get_logger().info(
                    f'IK solved with seed {i} '
                    f'(wrist_3={np.degrees(joints[5]):.1f}°)'
                )
                return joints

        return None

    def run(self):
        self.get_logger().info('Waiting for joint states...')
        while self.current_joints is None:
            rclpy.spin_once(self, timeout_sec=0.5)

        self.get_logger().info(
            f'Current joints (deg): '
            f'{np.round(np.degrees(self.current_joints), 2).tolist()}'
        )

        # Compute current TCP position for comparison
        T_tool0_now = self.kinematics.fk(self.current_joints)
        T_nozzle_now = T_tool0_now @ self.tool_offset
        self.get_logger().info(
            f'Current nozzle tip position: '
            f'{np.round(T_nozzle_now[:3, 3], 4).tolist()}'
        )

        # Target: nozzle tip at bed center, z_above meters above surface
        z_above = self.args.z_above
        target_nozzle_pos = self.print_origin.copy()
        target_nozzle_pos[2] += z_above

        self.get_logger().info(
            f'Target nozzle tip position: {np.round(target_nozzle_pos, 4).tolist()}'
        )
        self.get_logger().info(
            f'  bed center = {self.print_origin.tolist()}, '
            f'z_above = {z_above*1000:.1f} mm, '
            f'tool_offset = {self.tool_offset_xyz[2]}m'
        )

        # Build target nozzle pose (4x4)
        T_nozzle_target = np.eye(4)
        T_nozzle_target[:3, :3] = self.nozzle_down_R
        T_nozzle_target[:3, 3] = target_nozzle_pos

        # Compute tool0 pose: T_tool0 = T_nozzle @ inv(T_tool)
        T_tool_inv = np.linalg.inv(self.tool_offset)
        T_tool0_target = T_nozzle_target @ T_tool_inv

        tool0_pos = T_tool0_target[:3, 3]
        self.get_logger().info(
            f'Target tool0 position: {np.round(tool0_pos, 4).tolist()}'
        )
        self.get_logger().info(
            f'Target tool0 orientation:')
        for row in T_tool0_target[:3, :3]:
            self.get_logger().info(
                f'  [{row[0]:8.4f} {row[1]:8.4f} {row[2]:8.4f}]'
            )

        # Compute IK
        self.get_logger().info('Computing IK...')
        target_joints = self._solve_ik(T_tool0_target)

        if target_joints is None:
            self.get_logger().error('IK failed! Target may be unreachable.')
            return False

        self.get_logger().info(
            f'IK solution (deg): '
            f'{np.round(np.degrees(target_joints), 2).tolist()}'
        )

        # Normalize to current joints for smooth motion
        for j in range(6):
            while target_joints[j] - self.current_joints[j] > np.pi:
                target_joints[j] -= 2 * np.pi
            while target_joints[j] - self.current_joints[j] < -np.pi:
                target_joints[j] += 2 * np.pi

        # Verify FK of the IK solution
        T_fk = self.kinematics.fk(target_joints)
        T_nozzle_fk = T_fk @ self.tool_offset
        nozzle_pos_fk = T_nozzle_fk[:3, 3]
        pos_err = np.linalg.norm(nozzle_pos_fk - target_nozzle_pos)
        self.get_logger().info(
            f'FK verification — nozzle tip: {np.round(nozzle_pos_fk, 5).tolist()}'
        )
        self.get_logger().info(f'  Position error: {pos_err*1000:.3f} mm')

        # Check that tool Z-axis points down
        tool_z = T_nozzle_fk[:3, 2]
        self.get_logger().info(
            f'  Nozzle Z-axis direction: {np.round(tool_z, 4).tolist()}'
        )
        if tool_z[2] > -0.99:
            self.get_logger().warn(
                f'Nozzle Z-axis is NOT pointing straight down! '
                f'z-component = {tool_z[2]:.4f} (should be -1.0)'
            )
        else:
            self.get_logger().info('  Nozzle pointing DOWN — correct!')

        self.get_logger().info(
            f'  Wrist_3: {np.degrees(target_joints[5]):.1f}° '
            f'(should be near 0° for no cable wrap)'
        )

        joint_diff = np.max(np.abs(target_joints - self.current_joints))
        self.get_logger().info(
            f'Max joint move: {np.degrees(joint_diff):.1f} deg '
            f'({joint_diff:.3f} rad)'
        )

        if pos_err > 0.001:
            self.get_logger().error(
                f'Position error {pos_err*1000:.1f}mm too large — aborting'
            )
            return False

        # Send trajectory
        self.get_logger().info('Waiting for trajectory action server...')
        if not self.traj_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('Trajectory action server not available')
            return False

        duration = max(4.0, joint_diff * 2.0)
        trajectory = JointTrajectory()
        trajectory.joint_names = JOINT_NAMES
        point = JointTrajectoryPoint()
        point.positions = target_joints.tolist()
        point.velocities = [0.0] * 6
        point.time_from_start = Duration(
            sec=int(duration),
            nanosec=int((duration % 1) * 1e9),
        )
        trajectory.points = [point]

        self.get_logger().info(
            f'Sending calibration move (duration={duration:.1f}s)...'
        )
        goal = FollowJointTrajectory.Goal()
        goal.trajectory = trajectory

        future = self.traj_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)

        if not future.done():
            self.get_logger().error('Goal send timeout')
            return False

        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected')
            return False

        self.get_logger().info('Goal accepted — waiting for completion...')
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(
            self, result_future, timeout_sec=duration + 30.0
        )

        if not result_future.done():
            self.get_logger().error('Trajectory execution timeout')
            return False

        result = result_future.result()
        if result.result.error_code != 0:
            self.get_logger().error(
                f'Trajectory failed: error_code={result.result.error_code} '
                f'{result.result.error_string}'
            )
            return False

        # Wait for joint state to settle
        time.sleep(0.5)
        rclpy.spin_once(self, timeout_sec=0.5)

        # Verify final position
        if self.current_joints is not None:
            T_final = self.kinematics.fk(self.current_joints)
            T_nozzle_final = T_final @ self.tool_offset
            final_pos = T_nozzle_final[:3, 3]
            final_err = np.linalg.norm(final_pos - target_nozzle_pos)
            final_z = T_nozzle_final[:3, 2]

            self.get_logger().info('=== CALIBRATION RESULT ===')
            self.get_logger().info(
                f'  Nozzle tip position: {np.round(final_pos, 4).tolist()}'
            )
            self.get_logger().info(
                f'  Target position:     {np.round(target_nozzle_pos, 4).tolist()}'
            )
            self.get_logger().info(
                f'  Position error:      {final_err*1000:.2f} mm'
            )
            self.get_logger().info(
                f'  Nozzle Z-axis:       {np.round(final_z, 4).tolist()}'
            )
            self.get_logger().info(
                f'  Pointing down:       {"YES" if final_z[2] < -0.99 else "NO"}'
            )
            self.get_logger().info(
                f'  Wrist_3:             '
                f'{np.degrees(self.current_joints[5]):.1f}°'
            )
            self.get_logger().info(
                f'  Final joints (deg):  '
                f'{np.round(np.degrees(self.current_joints), 2).tolist()}'
            )

        self.get_logger().info('Calibration move complete!')
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Move TCP to print bed center for calibration'
    )
    parser.add_argument(
        '--z-above', type=float, default=0.0,
        help='Height above bed surface in meters (default: 0.0 = on surface)'
    )
    args = parser.parse_args()

    rclpy.init()
    node = CalibrationNode(args)
    try:
        success = node.run()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
