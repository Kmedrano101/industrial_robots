#!/usr/bin/env python3
"""
Pick and Place Node

Main ROS2 node implementing pick and place state machine for UR robots.
"""

import time
from enum import Enum
from typing import Optional, List
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup

from sensor_msgs.msg import JointState
from geometry_msgs.msg import Pose, Point, Quaternion
from visualization_msgs.msg import MarkerArray
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from builtin_interfaces.msg import Duration
from std_msgs.msg import Header

from ur_kinematics_msgs.srv import ComputeFK, ComputeIK
from ur_pick_place.srv import SetGripper, PickPlace
from ur_pick_place.msg import PickPlaceState, GripperState
from ur_pick_place.scene_objects import SceneObjectManager


class State(Enum):
    """Pick and place state machine states."""
    IDLE = 0
    MOVING_TO_PICK = 1
    APPROACHING_PICK = 2
    GRASPING = 3
    RETRACTING_PICK = 4
    MOVING_TO_PLACE = 5
    APPROACHING_PLACE = 6
    RELEASING = 7
    RETRACTING_PLACE = 8
    RETURNING_HOME = 9
    SUCCESS = 10
    ERROR = 11


STATE_NAMES = {
    State.IDLE: 'Idle',
    State.MOVING_TO_PICK: 'Moving to pick position',
    State.APPROACHING_PICK: 'Approaching pick',
    State.GRASPING: 'Grasping object',
    State.RETRACTING_PICK: 'Retracting from pick',
    State.MOVING_TO_PLACE: 'Moving to place position',
    State.APPROACHING_PLACE: 'Approaching place',
    State.RELEASING: 'Releasing object',
    State.RETRACTING_PLACE: 'Retracting from place',
    State.RETURNING_HOME: 'Returning to home',
    State.SUCCESS: 'Success',
    State.ERROR: 'Error',
}


class PickPlaceNode(Node):
    """
    ROS2 node for pick and place operations.

    Services:
        ~/pick_place: Execute a pick and place operation

    Publishers:
        ~/state: Current state machine state
        ~/markers: Visualization markers

    Subscribers:
        /joint_states: Current robot joint state

    Clients:
        /ur_kinematics_server/compute_ik: IK computation
        /ur_kinematics_server/compute_fk: FK computation
        /joint_trajectory_controller/follow_joint_trajectory: Motion execution
        /gripper_controller/set_gripper: Gripper control
    """

    # UR5e joint names
    JOINT_NAMES = [
        'shoulder_pan_joint',
        'shoulder_lift_joint',
        'elbow_joint',
        'wrist_1_joint',
        'wrist_2_joint',
        'wrist_3_joint'
    ]

    def __init__(self):
        super().__init__('pick_place_node')

        # Declare parameters
        self.declare_parameter('pick_position', [0.4, 0.25, 0.95])
        self.declare_parameter('place_position', [0.4, -0.25, 0.95])
        self.declare_parameter('approach_height', 0.15)
        self.declare_parameter('object_height', 0.04)
        self.declare_parameter('home_joints', [0.0, -1.57, 1.57, -1.57, -1.57, 0.0])
        self.declare_parameter('motion_speed', 0.5)  # Trajectory time multiplier
        self.declare_parameter('publish_rate', 10.0)

        # Load parameters
        self.pick_position = np.array(self.get_parameter('pick_position').value)
        self.place_position = np.array(self.get_parameter('place_position').value)
        self.approach_height = self.get_parameter('approach_height').value
        self.object_height = self.get_parameter('object_height').value
        self.home_joints = np.array(self.get_parameter('home_joints').value)
        self.motion_speed = self.get_parameter('motion_speed').value
        publish_rate = self.get_parameter('publish_rate').value

        # State machine
        self.state = State.IDLE
        self.error_message = ''
        self.operation_start_time = 0.0
        self.goal_in_progress = False

        # Current robot state
        self.current_joints = None
        self.gripper_state = GripperState.OPEN

        # Scene manager
        self.scene_manager = SceneObjectManager(frame_id='world')
        self.scene_markers = None

        # Callback groups
        self.service_cb_group = ReentrantCallbackGroup()
        self.timer_cb_group = MutuallyExclusiveCallbackGroup()

        # Publishers
        self.state_pub = self.create_publisher(PickPlaceState, '~/state', 10)
        self.marker_pub = self.create_publisher(MarkerArray, '~/markers', 10)

        # Subscribers
        self.joint_state_sub = self.create_subscription(
            JointState, '/joint_states', self.joint_state_callback, 10
        )
        self.gripper_state_sub = self.create_subscription(
            GripperState, '/gripper_controller/gripper_state',
            self.gripper_state_callback, 10
        )

        # Service clients
        self.ik_client = self.create_client(
            ComputeIK, '/ur_kinematics_server/compute_ik'
        )
        self.fk_client = self.create_client(
            ComputeFK, '/ur_kinematics_server/compute_fk'
        )
        self.gripper_client = self.create_client(
            SetGripper, '/gripper_controller/set_gripper'
        )

        # Action client for trajectory execution
        self.trajectory_client = ActionClient(
            self, FollowJointTrajectory,
            '/joint_trajectory_controller/follow_joint_trajectory'
        )

        # Services
        self.pick_place_srv = self.create_service(
            PickPlace, '~/pick_place', self.pick_place_callback,
            callback_group=self.service_cb_group
        )

        # Timer for state publishing
        self.timer = self.create_timer(
            1.0 / publish_rate, self.timer_callback,
            callback_group=self.timer_cb_group
        )

        # Create scene markers
        self.scene_markers = self.scene_manager.create_pick_place_markers(
            self.pick_position.tolist(),
            self.place_position.tolist(),
            self.approach_height,
            [self.object_height, self.object_height, self.object_height]
        )

        self.get_logger().info('Pick and place node initialized')
        self.get_logger().info(f'  Pick position: {self.pick_position}')
        self.get_logger().info(f'  Place position: {self.place_position}')
        self.get_logger().info(f'  Approach height: {self.approach_height}')

    def joint_state_callback(self, msg: JointState):
        """Handle joint state updates."""
        positions = []
        for name in self.JOINT_NAMES:
            if name in msg.name:
                idx = msg.name.index(name)
                positions.append(msg.position[idx])

        if len(positions) == 6:
            self.current_joints = np.array(positions)

    def gripper_state_callback(self, msg: GripperState):
        """Handle gripper state updates."""
        self.gripper_state = msg.state

    def timer_callback(self):
        """Publish state and markers."""
        # Publish state
        state_msg = PickPlaceState()
        state_msg.header = Header()
        state_msg.header.stamp = self.get_clock().now().to_msg()
        state_msg.state = self.state.value
        state_msg.state_name = STATE_NAMES[self.state]
        state_msg.progress = 0.0
        state_msg.error_message = self.error_message
        self.state_pub.publish(state_msg)

        # Publish markers
        if self.scene_markers:
            for marker in self.scene_markers.markers:
                marker.header.stamp = self.get_clock().now().to_msg()
            self.marker_pub.publish(self.scene_markers)

    def pick_place_callback(self, request: PickPlace.Request,
                            response: PickPlace.Response) -> PickPlace.Response:
        """Handle pick and place service request."""
        if self.state != State.IDLE:
            response.success = False
            response.message = f'Cannot start: currently in state {STATE_NAMES[self.state]}'
            return response

        # Use request positions or defaults
        pick_pos = self.pick_position.copy()
        place_pos = self.place_position.copy()

        if request.pick_position.x != 0.0 or request.pick_position.y != 0.0:
            pick_pos = np.array([
                request.pick_position.x,
                request.pick_position.y,
                request.pick_position.z if request.pick_position.z != 0.0 else self.pick_position[2]
            ])

        if request.place_position.x != 0.0 or request.place_position.y != 0.0:
            place_pos = np.array([
                request.place_position.x,
                request.place_position.y,
                request.place_position.z if request.place_position.z != 0.0 else self.place_position[2]
            ])

        self.get_logger().info(f'Starting pick and place: {pick_pos} -> {place_pos}')
        self.operation_start_time = time.time()

        # Execute pick and place sequence
        success = self.execute_pick_place(pick_pos, place_pos)

        execution_time = time.time() - self.operation_start_time
        response.success = success
        response.message = 'Pick and place completed' if success else f'Failed: {self.error_message}'
        response.execution_time = execution_time

        self.state = State.IDLE
        return response

    def execute_pick_place(self, pick_pos: np.ndarray, place_pos: np.ndarray) -> bool:
        """Execute the pick and place sequence."""
        try:
            # Wait for services
            if not self.wait_for_services():
                self.error_message = 'Services not available'
                self.state = State.ERROR
                return False

            # 1. Move to pick approach position
            self.state = State.MOVING_TO_PICK
            pick_approach = pick_pos.copy()
            pick_approach[2] += self.approach_height
            if not self.move_to_position(pick_approach):
                return False

            # 2. Approach pick (descend)
            self.state = State.APPROACHING_PICK
            pick_grasp = pick_pos.copy()
            pick_grasp[2] += self.object_height / 2  # Grasp at object center
            if not self.move_to_position(pick_grasp):
                return False

            # 3. Grasp
            self.state = State.GRASPING
            if not self.set_gripper(close=True):
                return False
            time.sleep(0.5)  # Wait for grasp

            # 4. Retract from pick
            self.state = State.RETRACTING_PICK
            if not self.move_to_position(pick_approach):
                return False

            # Update object marker position (attached to gripper)
            # For visualization, we'll move it with place later

            # 5. Move to place approach position
            self.state = State.MOVING_TO_PLACE
            place_approach = place_pos.copy()
            place_approach[2] += self.approach_height
            if not self.move_to_position(place_approach):
                return False

            # 6. Approach place (descend)
            self.state = State.APPROACHING_PLACE
            place_release = place_pos.copy()
            place_release[2] += self.object_height / 2
            if not self.move_to_position(place_release):
                return False

            # 7. Release
            self.state = State.RELEASING
            if not self.set_gripper(close=False):
                return False
            time.sleep(0.5)  # Wait for release

            # Update object marker to place position
            obj_place_pos = [place_pos[0], place_pos[1], place_pos[2] + self.object_height / 2]
            self.scene_manager.update_object_position(self.scene_markers, 6, obj_place_pos)

            # 8. Retract from place
            self.state = State.RETRACTING_PLACE
            if not self.move_to_position(place_approach):
                return False

            # 9. Return to home
            self.state = State.RETURNING_HOME
            if not self.move_to_joints(self.home_joints):
                return False

            self.state = State.SUCCESS
            self.get_logger().info('Pick and place completed successfully')
            return True

        except Exception as e:
            self.error_message = str(e)
            self.state = State.ERROR
            self.get_logger().error(f'Pick and place failed: {e}')
            return False

    def wait_for_services(self, timeout: float = 5.0) -> bool:
        """Wait for required services to be available."""
        services = [
            (self.ik_client, '/ur_kinematics_server/compute_ik'),
            (self.gripper_client, '/gripper_controller/set_gripper'),
        ]

        for client, name in services:
            if not client.wait_for_service(timeout_sec=timeout):
                self.get_logger().error(f'Service {name} not available')
                return False

        if not self.trajectory_client.wait_for_server(timeout_sec=timeout):
            self.get_logger().error('Trajectory action server not available')
            return False

        return True

    def move_to_position(self, position: np.ndarray) -> bool:
        """Move robot end-effector to a Cartesian position."""
        if self.current_joints is None:
            self.error_message = 'No joint state available'
            return False

        # Create target pose (pointing down)
        target_pose = Pose()
        target_pose.position.x = float(position[0])
        target_pose.position.y = float(position[1])
        target_pose.position.z = float(position[2])

        # Orientation: pointing down (rotate 180 deg around X)
        target_pose.orientation.x = 1.0
        target_pose.orientation.y = 0.0
        target_pose.orientation.z = 0.0
        target_pose.orientation.w = 0.0

        # Compute IK
        ik_request = ComputeIK.Request()
        ik_request.target_pose = target_pose
        ik_request.seed_configuration = self.current_joints.tolist()
        ik_request.method = 'lm'
        ik_request.max_iterations = 100
        ik_request.tolerance = 1e-6
        ik_request.check_limits = True

        future = self.ik_client.call_async(ik_request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            self.error_message = 'IK service timeout'
            return False

        response = future.result()
        if not response.success or response.num_solutions == 0:
            self.error_message = f'IK failed: {response.message}'
            self.get_logger().error(self.error_message)
            return False

        target_joints = np.array(response.solutions[0].joints)
        return self.move_to_joints(target_joints)

    def move_to_joints(self, target_joints: np.ndarray) -> bool:
        """Move robot to target joint configuration."""
        if self.current_joints is None:
            self.error_message = 'No joint state available'
            return False

        # Calculate trajectory duration based on max joint displacement
        joint_diff = np.abs(target_joints - self.current_joints)
        max_diff = np.max(joint_diff)
        duration = max(1.0, max_diff * 2.0 / self.motion_speed)  # Min 1 second

        # Create trajectory
        trajectory = JointTrajectory()
        trajectory.joint_names = self.JOINT_NAMES

        point = JointTrajectoryPoint()
        point.positions = target_joints.tolist()
        point.velocities = [0.0] * 6
        point.time_from_start = Duration(
            sec=int(duration),
            nanosec=int((duration % 1) * 1e9)
        )
        trajectory.points = [point]

        # Send goal
        goal = FollowJointTrajectory.Goal()
        goal.trajectory = trajectory

        self.goal_in_progress = True
        future = self.trajectory_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            self.error_message = 'Trajectory goal timeout'
            self.goal_in_progress = False
            return False

        goal_handle = future.result()
        if not goal_handle.accepted:
            self.error_message = 'Trajectory goal rejected'
            self.goal_in_progress = False
            return False

        # Wait for result
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=duration + 10.0)

        self.goal_in_progress = False

        if not result_future.done():
            self.error_message = 'Trajectory execution timeout'
            return False

        result = result_future.result()
        if result.result.error_code != 0:
            self.error_message = f'Trajectory failed with error code {result.result.error_code}'
            return False

        return True

    def set_gripper(self, close: bool) -> bool:
        """Set gripper state."""
        request = SetGripper.Request()
        request.open = not close

        future = self.gripper_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            self.error_message = 'Gripper service timeout'
            return False

        response = future.result()
        if not response.success:
            self.error_message = f'Gripper failed: {response.message}'
            return False

        return True


def main(args=None):
    rclpy.init(args=args)
    node = PickPlaceNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
