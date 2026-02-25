#!/usr/bin/env python3
"""
Compare our PoE FK model vs URDF TF tree to check for visualization mismatch.

Reads current joint_states, computes FK with our model, and compares
against the TF tool0 frame from the robot_state_publisher.
"""
import sys
import time
import threading
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from sensor_msgs.msg import JointState
import tf2_ros

sys.path.insert(0, '/home/kmedrano/src/industrial_robots/workspace/install/ur_kinematics_node/lib/python3.12/site-packages')
from ur_kinematics_node.robot_parameters import load_robot_parameters
from ur_kinematics_node.screw_kinematics import URScrewKinematics

# Tool offset
T_tool = np.eye(4)
T_tool[2, 3] = 0.105

params = load_robot_parameters(model_name='ur5e')
kin = URScrewKinematics(params)


def quat_to_matrix(q):
    """tf2 quaternion (x,y,z,w) to 3x3 rotation matrix."""
    x, y, z, w = q.x, q.y, q.z, q.w
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ])


class FKvsTF(Node):
    def __init__(self):
        super().__init__('fk_vs_tf')
        self.cb = ReentrantCallbackGroup()
        self.joints = None
        self.sub = self.create_subscription(
            JointState, '/joint_states', self.js_cb, 10, callback_group=self.cb)
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

    def js_cb(self, msg):
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


def main():
    rclpy.init()
    node = FKvsTF()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    print("Waiting for joint states and TF...")
    time.sleep(2.0)

    if node.joints is None:
        print("No joint states")
        rclpy.shutdown()
        sys.exit(1)

    joints = node.joints.copy()
    print(f"\nJoint positions (deg): {np.degrees(joints).round(2)}")

    # Our PoE FK
    T_flange_poe = kin.fk(joints)
    T_nozzle_poe = T_flange_poe @ T_tool

    print(f"\n--- Our PoE FK ---")
    print(f"  Flange pos: [{T_flange_poe[0,3]:.4f}, {T_flange_poe[1,3]:.4f}, {T_flange_poe[2,3]:.4f}]")
    print(f"  Flange R:")
    for row in T_flange_poe[:3, :3]:
        print(f"    [{row[0]:8.4f} {row[1]:8.4f} {row[2]:8.4f}]")
    print(f"  Nozzle pos: [{T_nozzle_poe[0,3]:.4f}, {T_nozzle_poe[1,3]:.4f}, {T_nozzle_poe[2,3]:.4f}]")
    print(f"  Nozzle Z:   [{T_nozzle_poe[0,2]:.4f}, {T_nozzle_poe[1,2]:.4f}, {T_nozzle_poe[2,2]:.4f}]")

    # URDF TF: world → tool0
    try:
        tf_tool0 = node.tf_buffer.lookup_transform('world', 'tool0', rclpy.time.Time())
        t = tf_tool0.transform.translation
        q = tf_tool0.transform.rotation
        R_tf = quat_to_matrix(q)

        T_flange_tf = np.eye(4)
        T_flange_tf[:3, :3] = R_tf
        T_flange_tf[:3, 3] = [t.x, t.y, t.z]
        T_nozzle_tf = T_flange_tf @ T_tool

        print(f"\n--- URDF TF (world→tool0) ---")
        print(f"  Flange pos: [{t.x:.4f}, {t.y:.4f}, {t.z:.4f}]")
        print(f"  Flange R:")
        for row in R_tf:
            print(f"    [{row[0]:8.4f} {row[1]:8.4f} {row[2]:8.4f}]")
        print(f"  Nozzle pos: [{T_nozzle_tf[0,3]:.4f}, {T_nozzle_tf[1,3]:.4f}, {T_nozzle_tf[2,3]:.4f}]")
        print(f"  Nozzle Z:   [{T_nozzle_tf[0,2]:.4f}, {T_nozzle_tf[1,2]:.4f}, {T_nozzle_tf[2,2]:.4f}]")

        # Difference
        pos_err = np.linalg.norm(T_flange_poe[:3, 3] - T_flange_tf[:3, 3])
        nozzle_err = np.linalg.norm(T_nozzle_poe[:3, 3] - T_nozzle_tf[:3, 3])
        R_err = T_flange_poe[:3, :3] @ T_flange_tf[:3, :3].T
        angle_err = np.arccos(np.clip((np.trace(R_err) - 1) / 2, -1, 1))

        print(f"\n--- Difference (PoE vs URDF) ---")
        print(f"  Flange position error: {pos_err*1000:.3f} mm")
        print(f"  Nozzle position error: {nozzle_err*1000:.3f} mm")
        print(f"  Orientation error:     {np.degrees(angle_err):.4f} deg")

        if pos_err > 0.001 or angle_err > np.radians(1):
            print(f"\n  *** MISMATCH DETECTED ***")
            print(f"  PoE FK and URDF TF disagree!")
            print(f"  This explains why the robot model in RViz doesn't match the green path.")
        else:
            print(f"\n  Models agree (< 1mm, < 1 deg)")

    except Exception as e:
        print(f"\nTF lookup failed: {e}")

    # Also check: what does TF say about base_link → tool0?
    try:
        tf_base_tool = node.tf_buffer.lookup_transform('base_link', 'tool0', rclpy.time.Time())
        t2 = tf_base_tool.transform.translation
        print(f"\n--- URDF TF (base_link→tool0) ---")
        print(f"  Flange pos: [{t2.x:.4f}, {t2.y:.4f}, {t2.z:.4f}]")
    except Exception as e:
        print(f"\nTF base_link→tool0 failed: {e}")

    # Check world → base_link
    try:
        tf_world_base = node.tf_buffer.lookup_transform('world', 'base_link', rclpy.time.Time())
        tw = tf_world_base.transform.translation
        qw = tf_world_base.transform.rotation
        print(f"\n--- URDF TF (world→base_link) ---")
        print(f"  Translation: [{tw.x:.4f}, {tw.y:.4f}, {tw.z:.4f}]")
        print(f"  Rotation:    [{qw.x:.4f}, {qw.y:.4f}, {qw.z:.4f}, {qw.w:.4f}]")
    except Exception as e:
        print(f"\nTF world→base_link failed: {e}")

    executor.shutdown()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
