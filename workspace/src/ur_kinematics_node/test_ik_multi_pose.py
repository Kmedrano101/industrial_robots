#!/usr/bin/env python3
"""
Multi-pose IK movement test - moves robot through multiple target poses.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from builtin_interfaces.msg import Duration
import numpy as np
import time

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_fk_ik import UR5eKinematics


class MultiPoseIKTest(Node):
    """Test IK by moving through multiple poses."""

    def __init__(self):
        super().__init__('multi_pose_ik_test')

        self.joint_names = [
            'shoulder_pan_joint',
            'shoulder_lift_joint',
            'elbow_joint',
            'wrist_1_joint',
            'wrist_2_joint',
            'wrist_3_joint'
        ]

        self.kinematics = UR5eKinematics()
        self.current_joints = None

        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            10
        )

        self.trajectory_client = ActionClient(
            self,
            FollowJointTrajectory,
            '/joint_trajectory_controller/follow_joint_trajectory'
        )

        self.get_logger().info('Multi-Pose IK Test Node initialized')

    def joint_state_callback(self, msg):
        joint_dict = dict(zip(msg.name, msg.position))
        try:
            self.current_joints = np.array([
                joint_dict[name] for name in self.joint_names
            ])
        except KeyError:
            pass

    def wait_for_joint_state(self, timeout=5.0):
        start = time.time()
        while self.current_joints is None:
            rclpy.spin_once(self, timeout_sec=0.1)
            if time.time() - start > timeout:
                return False
        return True

    def send_trajectory(self, target_joints, duration=2.0):
        if not self.trajectory_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('Trajectory action server not available')
            return False

        trajectory = JointTrajectory()
        trajectory.joint_names = self.joint_names

        point = JointTrajectoryPoint()
        point.positions = target_joints.tolist()
        point.velocities = [0.0] * 6
        point.time_from_start = Duration(sec=int(duration), nanosec=int((duration % 1) * 1e9))
        trajectory.points = [point]

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = trajectory

        future = self.trajectory_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)

        goal_handle = future.result()
        if not goal_handle.accepted:
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result()
        return result.result.error_code == 0

    def test_multi_pose(self):
        """Test IK by moving through multiple poses."""
        self.get_logger().info('=' * 70)
        self.get_logger().info('Multi-Pose IK Movement Test')
        self.get_logger().info('Using Screw Theory Product of Exponentials (PoE) Formula')
        self.get_logger().info('=' * 70)

        if not self.wait_for_joint_state():
            self.get_logger().error('Timeout waiting for joint state')
            return False

        # Define test poses (joint configurations to start from)
        test_configurations = [
            ("Typical Working Pose", np.array([0, -np.pi/4, np.pi/2, -np.pi/4, -np.pi/2, 0])),
            ("Extended Forward", np.array([0, -np.pi/3, np.pi/3, -np.pi/6, -np.pi/2, 0])),
            ("Rotated Left", np.array([np.pi/4, -np.pi/4, np.pi/2, -np.pi/4, -np.pi/2, 0])),
            ("Rotated Right", np.array([-np.pi/4, -np.pi/4, np.pi/2, -np.pi/4, -np.pi/2, 0])),
        ]

        results = []

        for i, (name, q_config) in enumerate(test_configurations):
            self.get_logger().info(f'\n--- Test {i+1}: {name} ---')

            # First move to the configuration
            self.get_logger().info(f'Moving to starting configuration...')
            if not self.send_trajectory(q_config, duration=2.0):
                self.get_logger().error(f'Failed to reach starting configuration')
                results.append((name, False, 0, 0))
                continue

            time.sleep(0.5)
            for _ in range(10):
                rclpy.spin_once(self, timeout_sec=0.1)

            # Get current pose
            q_current = self.current_joints.copy()
            T_current = self.kinematics.fk(q_current)

            self.get_logger().info(f'Current position: [{T_current[0,3]:.4f}, {T_current[1,3]:.4f}, {T_current[2,3]:.4f}] m')

            # Define target pose: offset in different directions
            offsets = [
                (0.05, 0, 0.05),   # Forward and up
                (-0.05, 0, 0.05),  # Back and up
                (0, 0.05, 0),      # Sideways
            ]

            offset = offsets[i % len(offsets)]
            T_target = T_current.copy()
            T_target[0, 3] += offset[0]
            T_target[1, 3] += offset[1]
            T_target[2, 3] += offset[2]

            self.get_logger().info(f'Target position: [{T_target[0,3]:.4f}, {T_target[1,3]:.4f}, {T_target[2,3]:.4f}] m')

            # Compute IK
            q_target, success, iters, err_mm = self.kinematics.ik(T_target, q_current)

            if not success:
                self.get_logger().error(f'IK failed: {iters} iterations, error: {err_mm:.4f} mm')
                results.append((name, False, iters, err_mm))
                continue

            self.get_logger().info(f'IK solved in {iters} iterations, error: {err_mm:.6f} mm')

            # Move to target
            if not self.send_trajectory(q_target, duration=2.0):
                self.get_logger().error(f'Failed to execute trajectory')
                results.append((name, False, iters, err_mm))
                continue

            time.sleep(0.5)
            for _ in range(10):
                rclpy.spin_once(self, timeout_sec=0.1)

            # Verify final pose
            q_final = self.current_joints.copy()
            T_final = self.kinematics.fk(q_final)

            pos_err = np.linalg.norm(T_final[:3, 3] - T_target[:3, 3]) * 1000
            self.get_logger().info(f'Final position error: {pos_err:.4f} mm')

            results.append((name, True, iters, pos_err))

        # Summary
        self.get_logger().info('\n' + '=' * 70)
        self.get_logger().info('TEST SUMMARY')
        self.get_logger().info('=' * 70)

        all_passed = True
        for name, success, iters, err in results:
            status = "PASS" if success and err < 1.0 else "FAIL"
            if not success or err >= 1.0:
                all_passed = False
            self.get_logger().info(f'  {name}: {status} (IK iters: {iters}, error: {err:.4f} mm)')

        self.get_logger().info('=' * 70)

        return all_passed


def main():
    rclpy.init()
    node = MultiPoseIKTest()

    try:
        success = node.test_multi_pose()
        if success:
            print('\n*** ALL MULTI-POSE IK TESTS PASSED ***\n')
        else:
            print('\n*** SOME TESTS FAILED ***\n')
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
