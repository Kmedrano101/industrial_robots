#!/usr/bin/env python3
"""
Test script to verify TCP nozzle-tip positions and orientations during/after a print.

Reads current joint states, computes FK to get flange pose, applies tool offset
to get nozzle tip pose, and checks that the nozzle is pointing straight down.
"""
import sys
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from ur_kinematics_msgs.srv import ComputeFK

# Tool offset: from tool0 (flange) to nozzle tip
TOOL_OFFSET = np.eye(4)
TOOL_OFFSET[2, 3] = 0.105  # 105mm along tool Z


def rotation_to_axis_angle(R):
    """Extract axis and angle from rotation matrix."""
    angle = np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if abs(angle) < 1e-6:
        return np.array([0, 0, 1]), 0.0
    axis = np.array([
        R[2, 1] - R[1, 2],
        R[0, 2] - R[2, 0],
        R[1, 0] - R[0, 1],
    ]) / (2 * np.sin(angle))
    return axis / np.linalg.norm(axis), angle


class TCPChecker(Node):
    def __init__(self):
        super().__init__('tcp_checker')
        self.joints = None
        self.joint_names = None
        self.sub = self.create_subscription(
            JointState, '/joint_states', self.joint_cb, 10
        )
        self.fk_client = self.create_client(ComputeFK, '/compute_fk')

    def joint_cb(self, msg):
        # UR driver may publish more joints; grab the 6 arm joints
        ur_names = [
            'shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
            'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint'
        ]
        positions = []
        for name in ur_names:
            if name in msg.name:
                idx = list(msg.name).index(name)
                positions.append(msg.position[idx])
        if len(positions) == 6:
            self.joints = np.array(positions)
            self.joint_names = ur_names

    def compute_fk_and_check(self):
        """Use the kinematics server FK service to get flange pose."""
        if not self.fk_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('FK service not available')
            return False

        from ur_kinematics_msgs.srv import ComputeFK
        req = ComputeFK.Request()
        req.joint_positions = self.joints.tolist()

        future = self.fk_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if future.result() is None:
            self.get_logger().error('FK service call failed')
            return False

        result = future.result()
        if not result.success:
            self.get_logger().error(f'FK failed: {result.message}')
            return False

        # Build 4x4 from geometry_msgs/Pose (position + quaternion)
        pose = result.end_effector_pose
        p = pose.position
        q = pose.orientation  # x, y, z, w

        # Quaternion to rotation matrix
        qx, qy, qz, qw = q.x, q.y, q.z, q.w
        R_flange = np.array([
            [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
            [2*(qx*qy + qz*qw), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qx*qw)],
            [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx**2 + qy**2)],
        ])

        T_flange = np.eye(4)
        T_flange[:3, :3] = R_flange
        T_flange[:3, 3] = [p.x, p.y, p.z]

        # Apply tool offset to get nozzle tip pose
        T_nozzle = T_flange @ TOOL_OFFSET

        print("\n" + "=" * 60)
        print("TCP (Nozzle Tip) Pose Verification")
        print("=" * 60)

        print(f"\nJoint positions (deg): {np.degrees(self.joints).round(2)}")

        print(f"\nFlange (tool0) position: "
              f"x={T_flange[0,3]:.4f}, y={T_flange[1,3]:.4f}, z={T_flange[2,3]:.4f}")

        print(f"\nNozzle tip position: "
              f"x={T_nozzle[0,3]:.4f}, y={T_nozzle[1,3]:.4f}, z={T_nozzle[2,3]:.4f}")

        # Check orientation: nozzle-down means tool Z-axis = [0, 0, -1]
        R_nozzle = T_nozzle[:3, :3]
        tool_z = R_nozzle[:3, 2]  # third column = Z-axis of tool frame
        tool_x = R_nozzle[:3, 0]
        tool_y = R_nozzle[:3, 1]

        print(f"\nNozzle orientation (rotation matrix):")
        for row in R_nozzle:
            print(f"  [{row[0]:8.4f} {row[1]:8.4f} {row[2]:8.4f}]")

        print(f"\nTool X-axis: [{tool_x[0]:.4f}, {tool_x[1]:.4f}, {tool_x[2]:.4f}]")
        print(f"Tool Y-axis: [{tool_y[0]:.4f}, {tool_y[1]:.4f}, {tool_y[2]:.4f}]")
        print(f"Tool Z-axis: [{tool_z[0]:.4f}, {tool_z[1]:.4f}, {tool_z[2]:.4f}]")

        # Expected nozzle-down: Rx(pi) = [[1,0,0],[0,-1,0],[0,0,-1]]
        expected_R = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=float)
        R_error = R_nozzle @ expected_R.T  # should be identity if perfect
        axis, angle_err = rotation_to_axis_angle(R_error)

        print(f"\nOrientation error from Rx(pi) [nozzle-down]: {np.degrees(angle_err):.4f} deg")

        # Check nozzle Z pointing down
        z_dot = np.dot(tool_z, [0, 0, -1])
        print(f"Nozzle Z dot [0,0,-1]: {z_dot:.6f}  (1.0 = perfect nozzle-down)")

        # Check if nozzle position is in expected rectangle print range
        # Expected: X=[-0.320,-0.280], Y=[-0.010,0.010], Z=[-0.0095,-0.0005]
        x, y, z = T_nozzle[0, 3], T_nozzle[1, 3], T_nozzle[2, 3]
        in_print_area = (-0.35 <= x <= -0.25) and (-0.02 <= y <= 0.02) and (-0.015 <= z <= 0.02)

        print(f"\nPosition in expected print area: {'YES' if in_print_area else 'NO'}")
        print(f"  Expected X: [-0.350, -0.250], got: {x:.4f}")
        print(f"  Expected Y: [-0.020,  0.020], got: {y:.4f}")
        print(f"  Expected Z: [-0.015,  0.020], got: {z:.4f}")

        nozzle_down = z_dot > 0.999
        print(f"\n{'PASS' if nozzle_down else 'FAIL'}: Nozzle pointing down (Z dot > 0.999): {nozzle_down}")
        print(f"  Orientation error from Rx(pi): {np.degrees(angle_err):.1f} deg")
        print(f"  (rotation about nozzle axis is OK for axially symmetric tool)")
        print("=" * 60)

        return nozzle_down


def main():
    rclpy.init()
    node = TCPChecker()

    # Wait for joint states
    print("Waiting for joint states...")
    for _ in range(50):
        rclpy.spin_once(node, timeout_sec=0.1)
        if node.joints is not None:
            break

    if node.joints is None:
        print("ERROR: No joint states received")
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(1)

    success = node.compute_fk_and_check()

    node.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
