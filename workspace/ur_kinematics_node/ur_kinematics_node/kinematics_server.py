#!/usr/bin/env python3
"""
ROS2 Kinematics Server Node

Provides FK/IK services and kinematic state publishing for Universal Robots.
"""

import numpy as np
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from geometry_msgs.msg import Pose, Point, Quaternion, Twist, Vector3
from sensor_msgs.msg import JointState
from std_msgs.msg import Header

from ur_kinematics_msgs.msg import KinematicState, IKSolution as IKSolutionMsg, Jacobian
from ur_kinematics_msgs.srv import ComputeFK, ComputeIK, ComputeJacobian, GetRobotInfo

from .robot_parameters import load_robot_parameters, get_supported_models
from .screw_kinematics import URScrewKinematics


def rotation_matrix_to_quaternion(R: np.ndarray) -> Quaternion:
    """Convert 3x3 rotation matrix to quaternion."""
    trace = np.trace(R)

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

    return Quaternion(x=x, y=y, z=z, w=w)


def quaternion_to_rotation_matrix(q: Quaternion) -> np.ndarray:
    """Convert quaternion to 3x3 rotation matrix."""
    x, y, z, w = q.x, q.y, q.z, q.w

    # Normalize
    n = np.sqrt(x*x + y*y + z*z + w*w)
    x, y, z, w = x/n, y/n, z/n, w/n

    R = np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]
    ])

    return R


def pose_to_matrix(pose: Pose) -> np.ndarray:
    """Convert geometry_msgs/Pose to 4x4 transformation matrix."""
    T = np.eye(4)
    T[:3, :3] = quaternion_to_rotation_matrix(pose.orientation)
    T[:3, 3] = [pose.position.x, pose.position.y, pose.position.z]
    return T


def matrix_to_pose(T: np.ndarray) -> Pose:
    """Convert 4x4 transformation matrix to geometry_msgs/Pose."""
    pose = Pose()
    pose.position = Point(x=T[0, 3], y=T[1, 3], z=T[2, 3])
    pose.orientation = rotation_matrix_to_quaternion(T[:3, :3])
    return pose


class KinematicsServer(Node):
    """
    ROS2 node providing kinematics services for Universal Robots.

    Services:
        - compute_fk: Forward kinematics
        - compute_ik: Inverse kinematics
        - compute_jacobian: Jacobian computation
        - get_robot_info: Robot model information

    Publishers:
        - ~/kinematic_state: Current kinematic state

    Subscribers:
        - /joint_states: Joint state feedback
    """

    def __init__(self):
        super().__init__('ur_kinematics_server')

        # Declare parameters
        self.declare_parameter('robot_model', 'ur7e')
        self.declare_parameter('config_file', '')
        self.declare_parameter('publish_rate', 100.0)

        # Get parameters
        robot_model = self.get_parameter('robot_model').get_parameter_value().string_value
        config_file = self.get_parameter('config_file').get_parameter_value().string_value
        publish_rate = self.get_parameter('publish_rate').get_parameter_value().double_value

        # Load robot parameters
        if config_file:
            self.get_logger().info(f'Loading robot from config: {config_file}')
            self.params = load_robot_parameters(config_path=config_file)
        else:
            self.get_logger().info(f'Loading robot model: {robot_model}')
            self.params = load_robot_parameters(model_name=robot_model)

        # Initialize kinematics
        self.kinematics = URScrewKinematics(self.params)

        # Current joint state
        self.current_joints: Optional[np.ndarray] = None
        self.current_velocities: Optional[np.ndarray] = None

        # Callback group for concurrent service handling
        self.callback_group = ReentrantCallbackGroup()

        # Create services
        self.fk_service = self.create_service(
            ComputeFK, 'compute_fk', self.compute_fk_callback,
            callback_group=self.callback_group
        )
        self.ik_service = self.create_service(
            ComputeIK, 'compute_ik', self.compute_ik_callback,
            callback_group=self.callback_group
        )
        self.jacobian_service = self.create_service(
            ComputeJacobian, 'compute_jacobian', self.compute_jacobian_callback,
            callback_group=self.callback_group
        )
        self.info_service = self.create_service(
            GetRobotInfo, 'get_robot_info', self.get_robot_info_callback,
            callback_group=self.callback_group
        )

        # Create subscriber for joint states
        self.joint_state_sub = self.create_subscription(
            JointState, '/joint_states', self.joint_state_callback, 10
        )

        # Create publisher for kinematic state
        self.state_pub = self.create_publisher(KinematicState, '~/kinematic_state', 10)

        # Timer for state publishing
        self.state_timer = self.create_timer(
            1.0 / publish_rate, self.publish_state_callback
        )

        self.get_logger().info(
            f'Kinematics server initialized for {self.params.model_name}'
        )

    def joint_state_callback(self, msg: JointState):
        """Handle incoming joint state messages."""
        # Extract UR joint positions (assuming standard naming)
        ur_joint_names = [
            'shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
            'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint'
        ]

        positions = []
        velocities = []

        for name in ur_joint_names:
            if name in msg.name:
                idx = msg.name.index(name)
                positions.append(msg.position[idx])
                if len(msg.velocity) > idx:
                    velocities.append(msg.velocity[idx])
                else:
                    velocities.append(0.0)

        if len(positions) == 6:
            self.current_joints = np.array(positions)
            self.current_velocities = np.array(velocities)

    def publish_state_callback(self):
        """Publish kinematic state periodically."""
        if self.current_joints is None:
            return

        # Compute FK
        T = self.kinematics.fk(self.current_joints)

        # Compute Jacobian
        J = self.kinematics.jacobian_space(self.current_joints)

        # Compute twist if velocities available
        twist = Twist()
        if self.current_velocities is not None:
            V = J @ self.current_velocities
            twist.angular = Vector3(x=V[0], y=V[1], z=V[2])
            twist.linear = Vector3(x=V[3], y=V[4], z=V[5])

        # Create message
        msg = KinematicState()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'

        msg.joint_positions = self.current_joints.tolist()
        msg.joint_velocities = (self.current_velocities.tolist()
                                if self.current_velocities is not None
                                else [0.0] * 6)
        msg.end_effector_pose = matrix_to_pose(T)
        msg.end_effector_twist = twist

        msg.condition_number = float(self.kinematics.condition_number(J))
        msg.manipulability = float(self.kinematics.manipulability(J))
        msg.near_singularity = bool(self.kinematics.is_near_singularity(J))

        self.state_pub.publish(msg)

    def compute_fk_callback(self, request: ComputeFK.Request,
                            response: ComputeFK.Response) -> ComputeFK.Response:
        """Handle FK service request."""
        try:
            joints = np.array(request.joint_positions)
            T = self.kinematics.fk(joints)

            response.end_effector_pose = matrix_to_pose(T)
            response.success = True
            response.message = "FK computed successfully"

        except Exception as e:
            response.success = False
            response.message = f"FK computation failed: {str(e)}"

        return response

    def compute_ik_callback(self, request: ComputeIK.Request,
                            response: ComputeIK.Response) -> ComputeIK.Response:
        """Handle IK service request."""
        try:
            T_target = pose_to_matrix(request.target_pose)

            # Get method
            method = request.method if request.method else "lm"

            # Get initial guess
            seed = (np.array(request.seed_configuration)
                    if len(request.seed_configuration) == 6
                    else (self.current_joints if self.current_joints is not None
                          else np.zeros(6)))

            # Get parameters
            max_iter = request.max_iterations if request.max_iterations > 0 else 100
            tolerance = request.tolerance if request.tolerance > 0 else 1e-6

            # Compute IK
            if method == "newton":
                solution = self.kinematics.ik_newton_raphson(
                    T_target, seed, tolerance, max_iter
                )
            else:
                solution = self.kinematics.ik_levenberg_marquardt(
                    T_target, seed, tolerance, max_iter
                )

            # Check limits if requested
            if request.check_limits and solution.is_valid:
                if not self.kinematics.check_joint_limits(solution.joints):
                    solution.is_valid = False

            # Build response
            if solution.is_valid:
                sol_msg = IKSolutionMsg()
                sol_msg.joints = solution.joints.tolist()
                sol_msg.is_valid = solution.is_valid
                sol_msg.error = solution.error
                sol_msg.iterations = solution.iterations
                sol_msg.method = solution.method
                response.solutions = [sol_msg]
                response.num_solutions = 1
            else:
                response.solutions = []
                response.num_solutions = 0

            response.success = solution.is_valid
            response.message = ("IK found valid solution" if solution.is_valid
                               else f"IK failed to converge (error: {solution.error:.6f})")

        except Exception as e:
            response.success = False
            response.message = f"IK computation failed: {str(e)}"
            response.num_solutions = 0
            response.solutions = []

        return response

    def compute_jacobian_callback(self, request: ComputeJacobian.Request,
                                  response: ComputeJacobian.Response) -> ComputeJacobian.Response:
        """Handle Jacobian service request."""
        try:
            joints = np.array(request.joint_positions)
            frame = request.frame if request.frame else "space"

            if frame == "body":
                J = self.kinematics.jacobian_body(joints)
            else:
                J = self.kinematics.jacobian_space(joints)

            # Build response
            jac_msg = Jacobian()
            jac_msg.header = Header()
            jac_msg.header.stamp = self.get_clock().now().to_msg()
            jac_msg.data = J.flatten().tolist()
            jac_msg.frame = frame
            jac_msg.condition_number = self.kinematics.condition_number(J)
            jac_msg.manipulability = self.kinematics.manipulability(J)

            response.jacobian = jac_msg
            response.success = True
            response.message = "Jacobian computed successfully"

        except Exception as e:
            response.success = False
            response.message = f"Jacobian computation failed: {str(e)}"

        return response

    def get_robot_info_callback(self, request: GetRobotInfo.Request,
                                response: GetRobotInfo.Response) -> GetRobotInfo.Response:
        """Handle robot info service request."""
        try:
            response.model_name = self.params.model_name
            response.num_joints = self.params.num_joints
            response.dh_a = self.params.a.tolist()
            response.dh_d = self.params.d.tolist()
            response.dh_alpha = self.params.alpha.tolist()

            response.joint_min = [lim[0] for lim in self.params.joint_limits]
            response.joint_max = [lim[1] for lim in self.params.joint_limits]

            response.home_configuration = self.params.M_home.flatten().tolist()

            response.success = True
            response.message = f"Robot info for {self.params.model_name}"

        except Exception as e:
            response.success = False
            response.message = f"Failed to get robot info: {str(e)}"

        return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = KinematicsServer()

    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
