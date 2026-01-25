#!/usr/bin/env python3
"""
Simulated Gripper Controller Node

Provides gripper control service and publishes gripper state/joint positions.
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from sensor_msgs.msg import JointState
from std_msgs.msg import Header

from ur_pick_place.srv import SetGripper
from ur_pick_place.msg import GripperState


class GripperController(Node):
    """
    Simulated gripper controller for parallel gripper.

    Services:
        ~/set_gripper: Open or close the gripper

    Publishers:
        ~/gripper_state: Current gripper state
        /gripper_joint_states: Joint positions for visualization
    """

    def __init__(self):
        super().__init__('gripper_controller')

        # Parameters
        self.declare_parameter('open_position', 0.04)
        self.declare_parameter('closed_position', 0.002)
        self.declare_parameter('transition_time', 0.5)
        self.declare_parameter('publish_rate', 50.0)

        self.open_position = self.get_parameter('open_position').value
        self.closed_position = self.get_parameter('closed_position').value
        self.transition_time = self.get_parameter('transition_time').value
        publish_rate = self.get_parameter('publish_rate').value

        # State
        self.current_position = self.open_position  # Start open
        self.target_position = self.open_position
        self.is_moving = False
        self.object_detected = False

        # Callback group for concurrent service calls
        self.callback_group = ReentrantCallbackGroup()

        # Service
        self.set_gripper_srv = self.create_service(
            SetGripper,
            '~/set_gripper',
            self.set_gripper_callback,
            callback_group=self.callback_group
        )

        # Publishers
        self.state_pub = self.create_publisher(GripperState, '~/gripper_state', 10)
        self.joint_state_pub = self.create_publisher(JointState, '/gripper_joint_states', 10)

        # Timer for state publishing and position updates
        self.timer = self.create_timer(1.0 / publish_rate, self.timer_callback)

        self.get_logger().info('Gripper controller initialized (open)')

    def set_gripper_callback(self, request: SetGripper.Request,
                             response: SetGripper.Response) -> SetGripper.Response:
        """Handle gripper open/close requests."""
        if request.open:
            self.target_position = self.open_position
            action = "Opening"
        else:
            self.target_position = self.closed_position
            action = "Closing"

        self.is_moving = True
        self.get_logger().info(f'{action} gripper')

        response.success = True
        response.message = f'{action} gripper'
        return response

    def timer_callback(self):
        """Update gripper position and publish state."""
        # Simulate gripper motion
        if self.is_moving:
            step = (self.open_position - self.closed_position) / (self.transition_time * 50.0)

            if self.target_position > self.current_position:
                self.current_position = min(self.current_position + step, self.target_position)
            else:
                self.current_position = max(self.current_position - step, self.target_position)

            if abs(self.current_position - self.target_position) < 0.0001:
                self.current_position = self.target_position
                self.is_moving = False

                # Simulate object detection when closed
                if self.current_position <= self.closed_position + 0.005:
                    self.object_detected = True
                else:
                    self.object_detected = False

        # Publish gripper state
        state_msg = GripperState()
        state_msg.header = Header()
        state_msg.header.stamp = self.get_clock().now().to_msg()
        state_msg.header.frame_id = 'gripper_base_link'

        # Normalize position to 0-1 range
        position_range = self.open_position - self.closed_position
        state_msg.position = (self.current_position - self.closed_position) / position_range

        if self.is_moving:
            state_msg.state = GripperState.MOVING
        elif self.current_position >= self.open_position - 0.001:
            state_msg.state = GripperState.OPEN
        else:
            state_msg.state = GripperState.CLOSED

        state_msg.object_detected = self.object_detected
        self.state_pub.publish(state_msg)

        # Publish joint states for visualization
        joint_msg = JointState()
        joint_msg.header = state_msg.header
        joint_msg.name = ['gripper_left_finger_joint', 'gripper_right_finger_joint']
        joint_msg.position = [self.current_position, self.current_position]
        joint_msg.velocity = [0.0, 0.0]
        joint_msg.effort = [0.0, 0.0]
        self.joint_state_pub.publish(joint_msg)

    def is_open(self) -> bool:
        """Check if gripper is open."""
        return self.current_position >= self.open_position - 0.001

    def is_closed(self) -> bool:
        """Check if gripper is closed."""
        return self.current_position <= self.closed_position + 0.001


def main(args=None):
    rclpy.init(args=args)
    node = GripperController()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
