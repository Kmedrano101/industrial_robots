#!/usr/bin/env python3
"""
Test IK with actual robot movement via ROS2 trajectory controller.

This script:
1. Reads current joint states from the robot
2. Computes FK to get current end-effector pose
3. Defines a target pose (small offset from current)
4. Computes IK to find joint angles for target pose
5. Sends trajectory command to move the robot
6. Verifies the robot reached the target
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

# Import our screw theory kinematics
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_fk_ik import UR5eKinematics


class IKMovementTest(Node):
    """Node to test IK-based robot movement."""

    def __init__(self):
        super().__init__('ik_movement_test')

        # Joint names for UR5e
        self.joint_names = [
            'shoulder_pan_joint',
            'shoulder_lift_joint',
            'elbow_joint',
            'wrist_1_joint',
            'wrist_2_joint',
            'wrist_3_joint'
        ]

        # Initialize kinematics
        self.kinematics = UR5eKinematics()

        # Current joint state
        self.current_joints = None

        # Subscribe to joint states
        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            10
        )

        # Action client for trajectory controller
        self.trajectory_client = ActionClient(
            self,
            FollowJointTrajectory,
            '/joint_trajectory_controller/follow_joint_trajectory'
        )

        self.get_logger().info('IK Movement Test Node initialized')

    def joint_state_callback(self, msg):
        """Store current joint state."""
        # Reorder joints according to our naming convention
        joint_dict = dict(zip(msg.name, msg.position))
        try:
            self.current_joints = np.array([
                joint_dict[name] for name in self.joint_names
            ])
        except KeyError:
            pass  # Not all joints available yet

    def wait_for_joint_state(self, timeout=5.0):
        """Wait for valid joint state."""
        start = time.time()
        while self.current_joints is None:
            rclpy.spin_once(self, timeout_sec=0.1)
            if time.time() - start > timeout:
                return False
        return True

    def send_trajectory(self, target_joints, duration=3.0):
        """Send trajectory command to move robot to target joints."""
        if not self.trajectory_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('Trajectory action server not available')
            return False

        # Create trajectory message
        trajectory = JointTrajectory()
        trajectory.joint_names = self.joint_names

        # Single point trajectory to target
        point = JointTrajectoryPoint()
        point.positions = target_joints.tolist()
        point.velocities = [0.0] * 6
        point.time_from_start = Duration(sec=int(duration), nanosec=int((duration % 1) * 1e9))
        trajectory.points = [point]

        # Create goal
        goal = FollowJointTrajectory.Goal()
        goal.trajectory = trajectory

        # Send goal
        self.get_logger().info(f'Sending trajectory to: {np.rad2deg(target_joints).round(1)} deg')
        future = self.trajectory_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)

        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Trajectory goal rejected')
            return False

        self.get_logger().info('Trajectory goal accepted, waiting for result...')

        # Wait for result
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result()
        if result.result.error_code == 0:
            self.get_logger().info('Trajectory execution succeeded')
            return True
        else:
            self.get_logger().error(f'Trajectory execution failed: {result.result.error_code}')
            return False

    def test_ik_movement(self):
        """Test IK by moving robot to computed target pose."""
        self.get_logger().info('=' * 60)
        self.get_logger().info('Starting IK Movement Test')
        self.get_logger().info('=' * 60)

        # Wait for joint state
        self.get_logger().info('Waiting for joint state...')
        if not self.wait_for_joint_state():
            self.get_logger().error('Timeout waiting for joint state')
            return False

        q_current = self.current_joints.copy()
        self.get_logger().info(f'Current joints (deg): {np.rad2deg(q_current).round(2)}')

        # Compute current FK
        T_current = self.kinematics.fk(q_current)
        self.get_logger().info(f'Current position: [{T_current[0,3]:.4f}, {T_current[1,3]:.4f}, {T_current[2,3]:.4f}] m')

        # Define target pose: small offset in x and z
        T_target = T_current.copy()
        T_target[0, 3] += 0.05  # 5cm in x
        T_target[2, 3] += 0.05  # 5cm in z

        self.get_logger().info(f'Target position: [{T_target[0,3]:.4f}, {T_target[1,3]:.4f}, {T_target[2,3]:.4f}] m')

        # Compute IK
        self.get_logger().info('Computing IK...')
        q_target, success, iters, err_mm = self.kinematics.ik(T_target, q_current)

        if not success:
            self.get_logger().error(f'IK failed after {iters} iterations, error: {err_mm:.4f} mm')
            return False

        self.get_logger().info(f'IK succeeded in {iters} iterations, error: {err_mm:.4f} mm')
        self.get_logger().info(f'Target joints (deg): {np.rad2deg(q_target).round(2)}')

        # Verify IK solution with FK
        T_verify = self.kinematics.fk(q_target)
        pos_err = np.linalg.norm(T_verify[:3, 3] - T_target[:3, 3]) * 1000
        self.get_logger().info(f'IK verification position error: {pos_err:.4f} mm')

        # Move robot to target
        self.get_logger().info('Moving robot to target pose...')
        if not self.send_trajectory(q_target, duration=3.0):
            self.get_logger().error('Failed to send trajectory')
            return False

        # Wait a bit for robot to settle
        time.sleep(0.5)

        # Read final joint state
        for _ in range(10):
            rclpy.spin_once(self, timeout_sec=0.1)

        q_final = self.current_joints.copy()
        self.get_logger().info(f'Final joints (deg): {np.rad2deg(q_final).round(2)}')

        # Compute final FK
        T_final = self.kinematics.fk(q_final)
        self.get_logger().info(f'Final position: [{T_final[0,3]:.4f}, {T_final[1,3]:.4f}, {T_final[2,3]:.4f}] m')

        # Calculate errors
        joint_err = np.linalg.norm(q_final - q_target)
        pos_err_final = np.linalg.norm(T_final[:3, 3] - T_target[:3, 3]) * 1000

        self.get_logger().info('=' * 60)
        self.get_logger().info('Test Results:')
        self.get_logger().info(f'  Joint error: {np.rad2deg(joint_err):.4f} deg')
        self.get_logger().info(f'  Position error: {pos_err_final:.4f} mm')

        if pos_err_final < 1.0:  # Less than 1mm
            self.get_logger().info('TEST PASSED: Robot reached target within 1mm')
            return True
        else:
            self.get_logger().warn('TEST WARNING: Position error > 1mm')
            return False


def main():
    rclpy.init()

    node = IKMovementTest()

    try:
        success = node.test_ik_movement()
        if success:
            print('\n*** IK Movement Test PASSED ***\n')
        else:
            print('\n*** IK Movement Test FAILED ***\n')
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
