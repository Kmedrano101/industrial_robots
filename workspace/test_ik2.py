#!/usr/bin/env python3
"""Test IK by round-tripping through FK first."""
import rclpy
from rclpy.node import Node
from ur_kinematics_msgs.srv import ComputeIK, ComputeFK
import numpy as np

rclpy.init()
node = Node('ik_test2')

fk_cli = node.create_client(ComputeFK, '/compute_fk')
ik_cli = node.create_client(ComputeIK, '/compute_ik')

print('Waiting for services...')
fk_cli.wait_for_service(timeout_sec=10.0)
ik_cli.wait_for_service(timeout_sec=10.0)
print('Services ready.')

# Step 1: FK for seed joints
seed = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]
fk_req = ComputeFK.Request()
fk_req.joint_positions = seed

print(f'\n=== FK for joints: {seed} ===')
future = fk_cli.call_async(fk_req)
rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
fk_resp = future.result()
p = fk_resp.end_effector_pose
print(f'FK result: success={fk_resp.success}')
print(f'  pos=({p.position.x:.4f}, {p.position.y:.4f}, {p.position.z:.4f})')
print(f'  quat=({p.orientation.x:.4f}, {p.orientation.y:.4f}, {p.orientation.z:.4f}, {p.orientation.w:.4f})')

# Step 2: IK with the FK result (should trivially succeed)
ik_req = ComputeIK.Request()
ik_req.target_pose = p
ik_req.seed_configuration = seed
ik_req.method = 'lm'
ik_req.max_iterations = 100
ik_req.tolerance = 1e-6
ik_req.check_limits = True

print(f'\n=== IK round-trip (should succeed) ===')
future = ik_cli.call_async(ik_req)
rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
ik_resp = future.result()
print(f'IK result: success={ik_resp.success}, num_solutions={ik_resp.num_solutions}')
if hasattr(ik_resp, 'message'):
    print(f'  message: {ik_resp.message}')
if ik_resp.num_solutions > 0:
    print(f'  joints: {[f"{j:.4f}" for j in ik_resp.solutions[0].joints]}')

# Step 3: Try IK with a nozzle-down pose at a reasonable position
from geometry_msgs.msg import Pose
test_pose = Pose()
test_pose.position.x = 0.4
test_pose.position.y = 0.0
test_pose.position.z = 0.3
# Quaternion for 180 deg about X (nozzle down)
test_pose.orientation.x = 1.0
test_pose.orientation.y = 0.0
test_pose.orientation.z = 0.0
test_pose.orientation.w = 0.0

ik_req2 = ComputeIK.Request()
ik_req2.target_pose = test_pose
ik_req2.seed_configuration = seed
ik_req2.method = 'lm'
ik_req2.max_iterations = 100
ik_req2.tolerance = 1e-6
ik_req2.check_limits = True

print(f'\n=== IK for nozzle-down at (0.4, 0, 0.3) ===')
future = ik_cli.call_async(ik_req2)
rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
ik_resp2 = future.result()
print(f'IK result: success={ik_resp2.success}, num_solutions={ik_resp2.num_solutions}')
if hasattr(ik_resp2, 'message'):
    print(f'  message: {ik_resp2.message}')
if ik_resp2.num_solutions > 0:
    print(f'  joints: {[f"{j:.4f}" for j in ik_resp2.solutions[0].joints]}')

# Step 4: Try IK with the analytical method
ik_req3 = ComputeIK.Request()
ik_req3.target_pose = test_pose
ik_req3.seed_configuration = seed
ik_req3.method = 'analytical'
ik_req3.max_iterations = 100
ik_req3.tolerance = 1e-6
ik_req3.check_limits = True

print(f'\n=== IK analytical for nozzle-down at (0.4, 0, 0.3) ===')
future = ik_cli.call_async(ik_req3)
rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
ik_resp3 = future.result()
print(f'IK result: success={ik_resp3.success}, num_solutions={ik_resp3.num_solutions}')
if hasattr(ik_resp3, 'message'):
    print(f'  message: {ik_resp3.message}')
if ik_resp3.num_solutions > 0:
    for i, sol in enumerate(ik_resp3.solutions):
        print(f'  solution {i}: {[f"{j:.4f}" for j in sol.joints]}')

node.destroy_node()
rclpy.shutdown()
