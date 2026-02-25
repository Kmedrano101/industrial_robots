#!/usr/bin/env python3
"""Thorough IK test: find what orientations actually work."""
import rclpy
from rclpy.node import Node
from ur_kinematics_msgs.srv import ComputeIK, ComputeFK
from geometry_msgs.msg import Pose
import numpy as np

rclpy.init()
node = Node('ik_test3')

fk_cli = node.create_client(ComputeFK, '/compute_fk')
ik_cli = node.create_client(ComputeIK, '/compute_ik')
fk_cli.wait_for_service(timeout_sec=10.0)
ik_cli.wait_for_service(timeout_sec=10.0)

def call_ik(pos, quat, seed, method='lm', check_limits=True):
    req = ComputeIK.Request()
    req.target_pose.position.x = pos[0]
    req.target_pose.position.y = pos[1]
    req.target_pose.position.z = pos[2]
    req.target_pose.orientation.x = quat[0]
    req.target_pose.orientation.y = quat[1]
    req.target_pose.orientation.z = quat[2]
    req.target_pose.orientation.w = quat[3]
    req.seed_configuration = list(seed)
    req.method = method
    req.max_iterations = 200
    req.tolerance = 1e-6
    req.check_limits = check_limits
    future = ik_cli.call_async(req)
    rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
    return future.result()

def call_fk(joints):
    req = ComputeFK.Request()
    req.joint_positions = list(joints)
    future = fk_cli.call_async(req)
    rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
    return future.result()

seed = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]

# Test 1: FK result orientation at different positions
print("=== Test 1: FK orientation at the target position ===")
fk_r = call_fk(seed)
p = fk_r.end_effector_pose
fk_quat = (p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w)
print(f"FK pose: ({p.position.x:.3f}, {p.position.y:.3f}, {p.position.z:.3f})")
print(f"FK quat: {fk_quat}")

# Use FK orientation at a different position
r = call_ik([0.4, 0.0, 0.3], fk_quat, seed)
print(f"\nIK at (0.4, 0, 0.3) with FK orientation: success={r.success}, msg={r.message}")
if r.num_solutions > 0:
    print(f"  joints: {[f'{j:.3f}' for j in r.solutions[0].joints]}")

# Test 2: Various nozzle-down orientations
print("\n=== Test 2: Various nozzle-down quaternions ===")
# Standard nozzle down (180 about X): Z -> -Z, Y -> -Y
quats = {
    '180_about_X': (1.0, 0.0, 0.0, 0.0),
    '180_about_Y': (0.0, 1.0, 0.0, 0.0),
    '135_about_X': (0.924, 0.0, 0.0, 0.383),  # 135 deg
    'FK_orientation': fk_quat,
    # UR convention: nozzle down often is (0, 0.707, 0.707, 0)
    'UR_nozzle_down_1': (0.0, 0.707, 0.707, 0.0),
    'UR_nozzle_down_2': (0.0, -0.707, 0.707, 0.0),
}

for name, q in quats.items():
    r = call_ik([0.4, 0.0, 0.3], q, seed, check_limits=False)
    status = f"OK joints={[f'{j:.2f}' for j in r.solutions[0].joints]}" if r.success else f"FAIL: {r.message}"
    print(f"  {name:20s} quat={q}: {status}")

# Test 3: Find a working nozzle-down config by FK search
print("\n=== Test 3: Search for nozzle-down joints ===")
# Typical UR5e nozzle-down config
nozzle_down_configs = [
    [0.0, -1.0, 1.0, -1.57, -1.57, 0.0],    # conservative reach
    [0.0, -0.5, 0.5, -1.57, -1.57, 0.0],
    [0.0, -1.57, 0.0, -1.57, -1.57, 0.0],    # arm straight out
    [0.0, -1.57, 1.57, 0.0, -1.57, 0.0],
    [0.0, -1.2, 2.0, -2.37, -1.57, 0.0],     # typical print pose
    [1.57, -1.2, 2.0, -2.37, -1.57, 0.0],
]

for joints in nozzle_down_configs:
    fk_r = call_fk(joints)
    if fk_r.success:
        p = fk_r.end_effector_pose
        q = p.orientation
        # Check if tool Z points roughly down (quat Z component)
        # Convert quat to Z-axis direction
        qx, qy, qz, qw = q.x, q.y, q.z, q.w
        z_axis = [2*(qx*qz + qw*qy), 2*(qy*qz - qw*qx), 1 - 2*(qx*qx + qy*qy)]
        is_down = z_axis[2] < -0.5
        print(f"  joints={[f'{j:.2f}' for j in joints]}")
        print(f"    pos=({p.position.x:.3f}, {p.position.y:.3f}, {p.position.z:.3f})")
        print(f"    quat=({q.x:.3f}, {q.y:.3f}, {q.z:.3f}, {q.w:.3f})")
        print(f"    tool_z={[f'{v:.3f}' for v in z_axis]} {'DOWN' if is_down else 'NOT DOWN'}")

        # Try IK with this config as seed for nearby target
        r2 = call_ik([p.position.x, p.position.y, p.position.z],
                     (q.x, q.y, q.z, q.w), joints)
        print(f"    IK round-trip: {'OK' if r2.success else 'FAIL'}")

node.destroy_node()
rclpy.shutdown()
