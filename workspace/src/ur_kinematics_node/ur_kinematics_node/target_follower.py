#!/usr/bin/env python3
"""
Real-time Target Following Demo using Screw Theory IK

This node:
1. Publishes a moving visual target marker in RViz
2. Computes IK in real-time to follow the target
3. Sends trajectory commands to move the robot continuously

The target moves through 3 waypoints in a continuous loop,
demonstrating real-time IK computation and robot tracking.
"""

import rclpy
import rclpy.time
import rclpy.duration
from rclpy.node import Node
from rclpy.action import ActionClient
from sensor_msgs.msg import JointState
from visualization_msgs.msg import Marker, MarkerArray
from geometry_msgs.msg import Point, PoseStamped
from std_msgs.msg import ColorRGBA
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from builtin_interfaces.msg import Duration
from tf2_ros import Buffer, TransformListener
import numpy as np
import math

from .ur5e_kinematics import UR5eKinematics


class TargetFollower(Node):
    """
    Real-time target following using Screw Theory IK.
    """

    def __init__(self):
        super().__init__('target_follower')

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

        # Current state
        self.current_joints = None
        self.current_tool_position = None  # Actual FK-computed tool position
        self.current_tool_orientation = None  # Actual FK-computed tool orientation
        self.last_ik_solution = None
        self.goal_in_progress = False

        # TF2 buffer and listener for reading robot's actual tool position
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Declare ROS2 parameter for pattern selection
        self.declare_parameter('pattern', 'circular')  # 'circular' or 'scan'
        self.pattern = self.get_parameter('pattern').value

        # CIRCULAR PATH - 8 waypoints forming a circle in front of the robot
        # Varying shoulder_pan (J1) and adjusting other joints to maintain circular motion
        self.circular_waypoint_configs = [
            np.array([0.0, -1.47, 1.47, -1.57, -1.57, 0.0]),     # Front center
            np.array([0.25, -1.47, 1.47, -1.57, -1.57, 0.0]),    # Front right
            np.array([0.35, -1.57, 1.57, -1.57, -1.57, 0.0]),    # Right
            np.array([0.25, -1.67, 1.67, -1.57, -1.57, 0.0]),    # Back right
            np.array([0.0, -1.67, 1.67, -1.57, -1.57, 0.0]),     # Back center
            np.array([-0.25, -1.67, 1.67, -1.57, -1.57, 0.0]),   # Back left
            np.array([-0.35, -1.57, 1.57, -1.57, -1.57, 0.0]),   # Left
            np.array([-0.25, -1.47, 1.47, -1.57, -1.57, 0.0]),   # Front left
        ]

        # SCAN PATH - 9 waypoints in zigzag pattern (bottom-to-top, left-to-right)
        # Row 1 (bottom): left → center → right
        # Row 2 (middle): right → center → left (reverse for zigzag)
        # Row 3 (top): left → center → right
        # J1 controls Y (left/right): -0.35, 0.0, +0.35
        # J2/J3 controls Z (up/down): -1.67/1.67 (low), -1.57/1.57 (mid), -1.47/1.47 (high)
        self.scan_waypoint_configs = [
            # Bottom row (low Z) - left to right
            np.array([-0.35, -1.67, 1.67, -1.57, -1.57, 0.0]),   # Bottom-left
            np.array([0.0, -1.67, 1.67, -1.57, -1.57, 0.0]),     # Bottom-center
            np.array([0.35, -1.67, 1.67, -1.57, -1.57, 0.0]),    # Bottom-right
            # Middle row (mid Z) - right to left (zigzag)
            np.array([0.35, -1.57, 1.57, -1.57, -1.57, 0.0]),    # Mid-right
            np.array([0.0, -1.57, 1.57, -1.57, -1.57, 0.0]),     # Mid-center
            np.array([-0.35, -1.57, 1.57, -1.57, -1.57, 0.0]),   # Mid-left
            # Top row (high Z) - left to right
            np.array([-0.35, -1.47, 1.47, -1.57, -1.57, 0.0]),   # Top-left
            np.array([0.0, -1.47, 1.47, -1.57, -1.57, 0.0]),     # Top-center
            np.array([0.35, -1.47, 1.47, -1.57, -1.57, 0.0]),    # Top-right
        ]

        # Select waypoint configs based on pattern parameter
        if self.pattern == 'scan':
            self.waypoint_configs = self.scan_waypoint_configs
            self.loop_path = False  # Scan pattern goes back and forth
        else:
            self.waypoint_configs = self.circular_waypoint_configs
            self.loop_path = True   # Circular pattern loops continuously

        # Direction for scan pattern (1 = forward, -1 = backward)
        self.scan_direction = 1

        # Waypoint positions will be obtained from TF when robot reaches each config
        # Initialize with None - will be populated from TF lookups
        self.waypoints = None
        self.waypoint_orientations = None
        self.waypoints_initialized = False
        self.target_orientation = np.eye(3)

        self.get_logger().info('Waypoints will be initialized from TF after robot moves to configs')

        # Animation state
        self.current_waypoint_idx = 0
        self.interpolation_progress = 0.0
        self.interpolation_speed = 0.3  # Slower for smoother tracking
        self.target_pose = None

        # State machine
        # WAITING_FOR_JOINTS -> CALIBRATING_WAYPOINTS -> INITIALIZING -> TRACKING
        self.state = 'WAITING_FOR_JOINTS'
        self.calibration_waypoint_idx = 0  # For waypoint calibration

        # Publishers
        self.marker_pub = self.create_publisher(MarkerArray, '/target_markers', 10)
        self.target_pose_pub = self.create_publisher(PoseStamped, '/target_pose', 10)

        # Subscriber
        self.joint_state_sub = self.create_subscription(
            JointState, '/joint_states', self.joint_state_callback, 10)

        # Action client
        self.trajectory_client = ActionClient(
            self, FollowJointTrajectory,
            '/joint_trajectory_controller/follow_joint_trajectory')

        # Timers
        self.create_timer(0.05, self.update_target_marker)  # 20 Hz marker
        self.create_timer(0.15, self.track_target)  # ~7 Hz tracking

        self.get_logger().info('=' * 60)
        self.get_logger().info('Target Follower - Screw Theory IK Demo')
        self.get_logger().info(f'Pattern: {self.pattern.upper()}')
        if self.pattern == 'scan':
            self.get_logger().info('  Scan: 9-point zigzag (bottom→top, left↔right)')
        else:
            self.get_logger().info('  Circular: 8-point loop in XY plane')
        self.get_logger().info('=' * 60)
        self.get_logger().info('Waiting for joint states to initialize waypoints...')

    def joint_state_callback(self, msg):
        joint_dict = dict(zip(msg.name, msg.position))
        try:
            self.current_joints = np.array([
                joint_dict[name] for name in self.joint_names
            ])
            # Get tool position from TF (robot's actual tool0 frame)
            self.update_tool_position_from_tf()
        except KeyError:
            pass

    def update_tool_position_from_tf(self):
        """Get the tool position from the robot's TF tree (tool0 frame)."""
        try:
            # Look up tool0 position relative to base_link
            transform = self.tf_buffer.lookup_transform(
                'base_link', 'tool0',
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.1)
            )
            # Extract position
            self.current_tool_position = np.array([
                transform.transform.translation.x,
                transform.transform.translation.y,
                transform.transform.translation.z
            ])
            # Extract orientation as rotation matrix
            q = transform.transform.rotation
            self.current_tool_orientation = self.quaternion_to_rotation_matrix(
                q.x, q.y, q.z, q.w
            )
        except Exception:
            # Fallback to FK if TF not available
            if self.current_joints is not None:
                T = self.kinematics.forward_kinematics(self.current_joints)
                self.current_tool_position = T[:3, 3].copy()
                self.current_tool_orientation = T[:3, :3].copy()

    def quaternion_to_rotation_matrix(self, x, y, z, w):
        """Convert quaternion to 3x3 rotation matrix."""
        # Normalize quaternion
        n = np.sqrt(x*x + y*y + z*z + w*w)
        x, y, z, w = x/n, y/n, z/n, w/n

        return np.array([
            [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
            [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
            [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]
        ])

    def get_interpolated_position(self):
        if self.waypoints is None or len(self.waypoints) == 0:
            return None
        # Interpolate between FK-computed waypoint positions
        idx1 = self.current_waypoint_idx
        if self.loop_path:
            idx2 = (self.current_waypoint_idx + 1) % len(self.waypoints)
        else:
            # For scan pattern, use scan_direction to determine next waypoint
            idx2 = self.current_waypoint_idx + self.scan_direction
            idx2 = max(0, min(idx2, len(self.waypoints) - 1))
        p1, p2 = self.waypoints[idx1], self.waypoints[idx2]
        t = (1 - math.cos(self.interpolation_progress * math.pi)) / 2
        # Update target orientation for smooth interpolation
        self.target_orientation = self.waypoint_orientations[idx1]  # Use orientation of current waypoint
        return p1 + t * (p2 - p1)

    def update_target_marker(self):
        if not self.waypoints_initialized or self.waypoints is None or len(self.waypoints) == 0:
            return

        # Update interpolation
        self.interpolation_progress += self.interpolation_speed * 0.05
        if self.interpolation_progress >= 1.0:
            self.interpolation_progress = 0.0
            if self.loop_path:
                # Circular pattern: loop continuously
                self.current_waypoint_idx = (self.current_waypoint_idx + 1) % len(self.waypoints)
            else:
                # Scan pattern: go back and forth
                next_idx = self.current_waypoint_idx + self.scan_direction
                if next_idx >= len(self.waypoints) - 1:
                    self.scan_direction = -1  # Reverse at end
                    next_idx = len(self.waypoints) - 2
                elif next_idx <= 0:
                    self.scan_direction = 1   # Forward at start
                    next_idx = 1
                self.current_waypoint_idx = max(0, min(next_idx, len(self.waypoints) - 1))
            self.get_logger().info(f'-> Waypoint {self.current_waypoint_idx + 1}')

        target_pos = self.get_interpolated_position()
        if target_pos is None:
            return

        # Build target pose
        self.target_pose = np.eye(4)
        self.target_pose[:3, :3] = self.target_orientation
        self.target_pose[:3, 3] = target_pos

        # Publish markers
        self.publish_markers(target_pos)

        # Publish pose
        pose_msg = PoseStamped()
        pose_msg.header.frame_id = 'base_link'
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.pose.position.x = target_pos[0]
        pose_msg.pose.position.y = target_pos[1]
        pose_msg.pose.position.z = target_pos[2]
        pose_msg.pose.orientation.w = 1.0
        self.target_pose_pub.publish(pose_msg)

    def publish_markers(self, target_pos):
        if not self.waypoints_initialized or self.waypoints is None or len(self.waypoints) == 0:
            return
        markers = MarkerArray()

        # Target sphere (where we want to go)
        m = Marker()
        m.header.frame_id = 'base_link'
        m.header.stamp = self.get_clock().now().to_msg()
        m.ns = 'target'
        m.id = 0
        m.type = Marker.SPHERE
        m.action = Marker.ADD
        m.pose.position.x = target_pos[0]
        m.pose.position.y = target_pos[1]
        m.pose.position.z = target_pos[2]
        m.pose.orientation.w = 1.0
        m.scale.x = m.scale.y = m.scale.z = 0.015
        m.color = ColorRGBA(r=1.0, g=0.2, b=0.2, a=0.9)
        markers.markers.append(m)

        # Actual tool position marker (where the tool actually is from FK)
        if self.current_tool_position is not None:
            tool_marker = Marker()
            tool_marker.header.frame_id = 'base_link'
            tool_marker.header.stamp = self.get_clock().now().to_msg()
            tool_marker.ns = 'tool'
            tool_marker.id = 1
            tool_marker.type = Marker.SPHERE
            tool_marker.action = Marker.ADD
            tool_marker.pose.position.x = self.current_tool_position[0]
            tool_marker.pose.position.y = self.current_tool_position[1]
            tool_marker.pose.position.z = self.current_tool_position[2]
            tool_marker.pose.orientation.w = 1.0
            tool_marker.scale.x = tool_marker.scale.y = tool_marker.scale.z = 0.012
            tool_marker.color = ColorRGBA(r=0.2, g=1.0, b=0.2, a=0.9)  # Green for actual position
            markers.markers.append(tool_marker)

            # Line connecting target to tool (shows tracking error)
            error_line = Marker()
            error_line.header.frame_id = 'base_link'
            error_line.header.stamp = self.get_clock().now().to_msg()
            error_line.ns = 'error'
            error_line.id = 2
            error_line.type = Marker.LINE_STRIP
            error_line.action = Marker.ADD
            error_line.scale.x = 0.002
            error_line.color = ColorRGBA(r=1.0, g=1.0, b=0.0, a=0.8)  # Yellow
            error_line.points.append(Point(
                x=target_pos[0], y=target_pos[1], z=target_pos[2]))
            error_line.points.append(Point(
                x=self.current_tool_position[0],
                y=self.current_tool_position[1],
                z=self.current_tool_position[2]))
            markers.markers.append(error_line)

        # Waypoint spheres
        for i, wp in enumerate(self.waypoints):
            wm = Marker()
            wm.header.frame_id = 'base_link'
            wm.header.stamp = self.get_clock().now().to_msg()
            wm.ns = 'waypoints'
            wm.id = i + 10
            wm.type = Marker.SPHERE
            wm.action = Marker.ADD
            wm.pose.position.x = wp[0]
            wm.pose.position.y = wp[1]
            wm.pose.position.z = wp[2]
            wm.pose.orientation.w = 1.0
            wm.scale.x = wm.scale.y = wm.scale.z = 0.01
            next_wp = (self.current_waypoint_idx + 1) % len(self.waypoints)
            if i == next_wp:
                wm.color = ColorRGBA(r=0.0, g=1.0, b=0.0, a=0.8)
            else:
                wm.color = ColorRGBA(r=0.5, g=0.5, b=0.5, a=0.5)
            markers.markers.append(wm)

        # Path lines
        path = Marker()
        path.header.frame_id = 'base_link'
        path.header.stamp = self.get_clock().now().to_msg()
        path.ns = 'path'
        path.id = 100
        path.type = Marker.LINE_STRIP
        path.action = Marker.ADD
        path.scale.x = 0.004
        path.color = ColorRGBA(r=0.3, g=0.3, b=1.0, a=0.6)
        for wp in self.waypoints:
            path.points.append(Point(x=wp[0], y=wp[1], z=wp[2]))
        # Only close the loop for circular pattern
        if self.loop_path:
            path.points.append(Point(x=self.waypoints[0][0], y=self.waypoints[0][1], z=self.waypoints[0][2]))
        markers.markers.append(path)

        self.marker_pub.publish(markers)

    def send_goal_async(self, target_joints, duration=0.2):
        """Send trajectory goal without blocking."""
        if self.goal_in_progress:
            return

        trajectory = JointTrajectory()
        trajectory.joint_names = self.joint_names
        point = JointTrajectoryPoint()
        point.positions = target_joints.tolist()
        point.velocities = [0.0] * 6
        point.time_from_start = Duration(sec=0, nanosec=int(duration * 1e9))
        trajectory.points = [point]

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = trajectory

        self.goal_in_progress = True
        future = self.trajectory_client.send_goal_async(goal)
        future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.goal_in_progress = False
            return
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.goal_result_callback)

    def goal_result_callback(self, future):
        self.goal_in_progress = False

    def track_target(self):
        if self.current_joints is None:
            return

        if not self.trajectory_client.wait_for_server(timeout_sec=0.05):
            return

        # State machine
        if self.state == 'WAITING_FOR_JOINTS':
            self.get_logger().info('Got joint states, starting waypoint calibration from TF...')
            self.state = 'CALIBRATING_WAYPOINTS'
            self.calibration_waypoint_idx = 0
            self.waypoints = []
            self.waypoint_orientations = []
            # Move to first waypoint config
            self.send_goal_async(self.waypoint_configs[0], duration=2.0)
            return

        if self.state == 'CALIBRATING_WAYPOINTS':
            # Move to each waypoint config and record TF position
            target_config = self.waypoint_configs[self.calibration_waypoint_idx]
            if np.linalg.norm(self.current_joints - target_config) < 0.05:
                # Reached waypoint - capture TF position
                if self.current_tool_position is not None:
                    self.waypoints.append(self.current_tool_position.copy())
                    self.waypoint_orientations.append(self.current_tool_orientation.copy())
                    pos = self.current_tool_position
                    self.get_logger().info(
                        f'Calibrated waypoint {self.calibration_waypoint_idx + 1}: '
                        f'[{pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}] (from TF)'
                    )
                    self.calibration_waypoint_idx += 1

                    if self.calibration_waypoint_idx >= len(self.waypoint_configs):
                        # All waypoints calibrated
                        self.waypoints_initialized = True
                        self.target_orientation = self.waypoint_orientations[0]
                        self.get_logger().info('All waypoints calibrated from TF! Moving to start position...')
                        self.state = 'INITIALIZING'
                        self.send_goal_async(self.waypoint_configs[0], duration=1.5)
                    else:
                        # Move to next waypoint
                        self.send_goal_async(
                            self.waypoint_configs[self.calibration_waypoint_idx],
                            duration=1.5
                        )
            elif not self.goal_in_progress:
                self.send_goal_async(target_config, duration=1.5)
            return

        if self.state == 'INITIALIZING':
            # Check if close to first waypoint
            if np.linalg.norm(self.current_joints - self.waypoint_configs[0]) < 0.1:
                self.get_logger().info('Initialized! Starting tracking...')
                self.state = 'TRACKING'
            elif not self.goal_in_progress:
                self.send_goal_async(self.waypoint_configs[0], duration=1.0)
            return

        # TRACKING state
        if self.goal_in_progress:
            return

        # Get interpolated joint configuration
        idx1 = self.current_waypoint_idx
        if self.loop_path:
            idx2 = (self.current_waypoint_idx + 1) % len(self.waypoint_configs)
        else:
            # For scan pattern, use scan_direction to determine next waypoint
            idx2 = self.current_waypoint_idx + self.scan_direction
            idx2 = max(0, min(idx2, len(self.waypoint_configs) - 1))
        q1 = self.waypoint_configs[idx1]
        q2 = self.waypoint_configs[idx2]
        t = (1 - math.cos(self.interpolation_progress * math.pi)) / 2
        q_target = q1 + t * (q2 - q1)

        # Check if significant movement needed
        if np.linalg.norm(q_target - self.current_joints) < 0.01:
            return

        # Send trajectory
        self.send_goal_async(q_target, duration=0.15)


def main():
    rclpy.init()
    node = TargetFollower()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
