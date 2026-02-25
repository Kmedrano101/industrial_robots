#!/usr/bin/env python3
"""Quick IK test — run with: python3 test_ik.py"""
import rclpy
from rclpy.node import Node
from ur_kinematics_msgs.srv import ComputeIK
import time

rclpy.init()
node = Node('ik_test')
cli = node.create_client(ComputeIK, '/compute_ik')

print('Waiting for /compute_ik service...')
if not cli.wait_for_service(timeout_sec=10.0):
    print('Service not available!')
    rclpy.shutdown()
    exit(1)
print('Service ready.')

req = ComputeIK.Request()
# Flange pose: nozzle at (0.3, 0, 0.3) with tool offset 0.15m
# Flange ends up at (0.3, 0, 0.45) pointing down
req.target_pose.position.x = 0.3
req.target_pose.position.y = 0.0
req.target_pose.position.z = 0.45
req.target_pose.orientation.x = 1.0
req.target_pose.orientation.y = 0.0
req.target_pose.orientation.z = 0.0
req.target_pose.orientation.w = 0.0
req.seed_configuration = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]
req.method = 'lm'
req.max_iterations = 100
req.tolerance = 1e-6
req.check_limits = True

print(f'Calling IK: pos=({req.target_pose.position.x}, {req.target_pose.position.y}, {req.target_pose.position.z})')
print(f'  orientation=({req.target_pose.orientation.x}, {req.target_pose.orientation.y}, {req.target_pose.orientation.z}, {req.target_pose.orientation.w})')
print(f'  seed={req.seed_configuration}')

future = cli.call_async(req)
rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)

if future.done():
    resp = future.result()
    print(f'Response: success={resp.success}, num_solutions={resp.num_solutions}')
    if hasattr(resp, 'message'):
        print(f'  message: {resp.message}')
    if resp.num_solutions > 0:
        print(f'  solution: {list(resp.solutions[0].joints)}')
else:
    print('TIMEOUT - no response')

# Also try without check_limits
req.check_limits = False
print('\nRetrying without check_limits...')
future = cli.call_async(req)
rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
if future.done():
    resp = future.result()
    print(f'Response: success={resp.success}, num_solutions={resp.num_solutions}')
    if resp.num_solutions > 0:
        print(f'  solution: {list(resp.solutions[0].joints)}')

# Try a different orientation - maybe tool pointing down via pitch rotation
from geometry_msgs.msg import Quaternion
import numpy as np
# Try quaternion for 180 deg about Y axis instead
req.target_pose.orientation.x = 0.0
req.target_pose.orientation.y = 1.0
req.target_pose.orientation.z = 0.0
req.target_pose.orientation.w = 0.0
req.check_limits = True
print(f'\nTrying orientation quat=(0,1,0,0) [180 about Y]...')
future = cli.call_async(req)
rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
if future.done():
    resp = future.result()
    print(f'Response: success={resp.success}, num_solutions={resp.num_solutions}')
    if resp.num_solutions > 0:
        print(f'  solution: {list(resp.solutions[0].joints)}')

node.destroy_node()
rclpy.shutdown()
