#!/usr/bin/env python3
"""Test trajectory planning with a simple 2-point G-code."""
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from ur_kinematics_msgs.srv import ComputeIK
from geometry_msgs.msg import Pose
import numpy as np
import time
import threading

rclpy.init()
node = Node('test_plan')
executor = MultiThreadedExecutor()
executor.add_node(node)

# Spin in background
thread = threading.Thread(target=executor.spin, daemon=True)
thread.start()

cb_group = ReentrantCallbackGroup()
ik_cli = node.create_client(ComputeIK, '/compute_ik', callback_group=cb_group)

# Wait for service
print('Waiting for IK service...')
start = time.time()
while not ik_cli.service_is_ready():
    if time.time() - start > 10:
        print('IK service not found!')
        rclpy.shutdown()
        exit(1)
    time.sleep(0.1)
print(f'IK service ready after {time.time()-start:.1f}s')

seed = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]

# Test: nozzle at (0.3, 0, 0.3) with tool offset 0.15m
# Flange position should be at (0.3, 0, 0.45) with nozzle-down
# Using print_origin_rpy = [pi, 0, 0] -> quat (1, 0, 0, 0)
# But with tool offset applied: T_flange = T_nozzle @ inv(T_tool)
# T_tool = [[1,0,0,0],[0,1,0,0],[0,0,1,0.15],[0,0,0,1]]
# T_nozzle orientation = Rx(pi) = [[1,0,0],[0,-1,0],[0,0,-1]]
# flange_z = nozzle_z + R[2,:] @ [0,0,-0.15] = 0.3 + (-1)*(-0.15) = 0.45

test_cases = [
    ("Flange directly (0.3, 0, 0.45) quat=(1,0,0,0)",
     (0.3, 0.0, 0.45), (1.0, 0.0, 0.0, 0.0)),
    ("Flange directly (0.3, 0, 0.3) quat=(1,0,0,0)",
     (0.3, 0.0, 0.3), (1.0, 0.0, 0.0, 0.0)),
    ("Offset target (0.337, 0.037, 0.375) quat=(1,0,0,0)",
     (0.337, 0.037, 0.375), (1.0, 0.0, 0.0, 0.0)),
]

for name, pos, quat in test_cases:
    req = ComputeIK.Request()
    req.target_pose.position.x = pos[0]
    req.target_pose.position.y = pos[1]
    req.target_pose.position.z = pos[2]
    req.target_pose.orientation.x = quat[0]
    req.target_pose.orientation.y = quat[1]
    req.target_pose.orientation.z = quat[2]
    req.target_pose.orientation.w = quat[3]
    req.seed_configuration = list(seed)
    req.method = 'lm'
    req.max_iterations = 200
    req.tolerance = 1e-6
    req.check_limits = True

    future = ik_cli.call_async(req)
    t0 = time.time()
    while not future.done() and (time.time() - t0) < 10:
        time.sleep(0.01)

    if not future.done():
        print(f'{name}: TIMEOUT after 10s')
        continue

    r = future.result()
    if r.success:
        print(f'{name}: OK joints={[f"{j:.3f}" for j in r.solutions[0].joints]}')
        seed = list(r.solutions[0].joints)  # Chain seed
    else:
        print(f'{name}: FAIL - {r.message}')

executor.shutdown()
rclpy.shutdown()
