#!/usr/bin/env python3
"""
Simple Joint State Publisher

Publishes joint states for visualization. Combines robot joint states
with gripper joint states from the gripper controller.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Header


class SimpleJointStatePublisher(Node):
    """
    Simple joint state publisher for standalone demo.

    Publishes joint states at a fixed rate, combining:
    - Robot joints (default positions)
    - Gripper joints (from gripper controller)
    """

    # UR5e joint names
    ROBOT_JOINTS = [
        'shoulder_pan_joint',
        'shoulder_lift_joint',
        'elbow_joint',
        'wrist_1_joint',
        'wrist_2_joint',
        'wrist_3_joint'
    ]

    # Default home position
    DEFAULT_POSITIONS = [0.0, -1.57, 1.57, -1.57, -1.57, 0.0]

    def __init__(self):
        super().__init__('simple_joint_state_publisher')

        # Parameters
        self.declare_parameter('publish_rate', 50.0)
        publish_rate = self.get_parameter('publish_rate').value

        # Current joint positions
        self.robot_positions = list(self.DEFAULT_POSITIONS)
        self.gripper_positions = [0.04, 0.04]  # Open position
        self.gripper_joints = ['gripper_left_finger_joint', 'gripper_right_finger_joint']

        # Publisher
        self.joint_state_pub = self.create_publisher(JointState, '/joint_states', 10)

        # Subscriber for gripper states
        self.gripper_sub = self.create_subscription(
            JointState, '/gripper_joint_states',
            self.gripper_callback, 10
        )

        # Timer
        self.timer = self.create_timer(1.0 / publish_rate, self.publish_joint_states)

        self.get_logger().info('Simple joint state publisher started')

    def gripper_callback(self, msg: JointState):
        """Update gripper positions from gripper controller."""
        for i, name in enumerate(msg.name):
            if name in self.gripper_joints:
                idx = self.gripper_joints.index(name)
                if i < len(msg.position):
                    self.gripper_positions[idx] = msg.position[i]

    def publish_joint_states(self):
        """Publish combined joint states."""
        msg = JointState()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()

        # Combine robot and gripper joints
        msg.name = self.ROBOT_JOINTS + self.gripper_joints
        msg.position = self.robot_positions + self.gripper_positions
        msg.velocity = [0.0] * len(msg.name)
        msg.effort = [0.0] * len(msg.name)

        self.joint_state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SimpleJointStatePublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
