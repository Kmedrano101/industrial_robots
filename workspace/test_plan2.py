#!/usr/bin/env python3
"""Simulate what print_node does: parse G-code, build target pose, call IK."""
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from ur_kinematics_msgs.srv import ComputeIK
from geometry_msgs.msg import Pose, Quaternion
import numpy as np
import time
import threading
import sys

sys.path.insert(0, '/home/kmedrano/src/industrial_robots/install/ur_3d_printer/lib/python3.12/dist-packages')

from ur_3d_printer.gcode_parser import GCodeParser
from ur_3d_printer.toolpath import Toolpath

rclpy.init()
node = Node('test_plan2')
executor = MultiThreadedExecutor()
executor.add_node(node)
thread = threading.Thread(target=executor.spin, daemon=True)
thread.start()

cb_group = ReentrantCallbackGroup()
ik_cli = node.create_client(ComputeIK, '/compute_ik', callback_group=cb_group)

# Wait for service
while not ik_cli.service_is_ready():
    time.sleep(0.1)
print('IK service ready')

# Parse G-code
parser = GCodeParser()
gcode_file = '/home/kmedrano/src/industrial_robots/workspace/src/ur_3d_printer/resource/chair.gcode'
toolpath = parser.parse_file(gcode_file)
print(f'Parsed: {toolpath.num_layers} layers, {toolpath.num_waypoints} waypoints')

# Set print frame (same as print_node)
def rpy_to_rotation_matrix(r, p, y):
    cr, sr = np.cos(r), np.sin(r)
    cp, sp = np.cos(p), np.sin(p)
    cy, sy = np.cos(y), np.sin(y)
    return np.array([
        [cy*cp, cy*sp*sr - sy*cr, cy*sp*cr + sy*sr],
        [sy*cp, sy*sp*sr + cy*cr, sy*sp*cr - cy*sr],
        [-sp,   cp*sr,            cp*cr]
    ])

print_origin = np.array([0.3, 0.0, 0.3])
print_rpy = np.array([np.pi, 0.0, 0.0])
print_frame = np.eye(4)
print_frame[:3, :3] = rpy_to_rotation_matrix(*print_rpy)
print_frame[:3, 3] = print_origin

toolpath.print_frame = print_frame
print(f'Print frame:\n{print_frame}')

# Tool offset
tool_offset = np.eye(4)
tool_offset[:3, 3] = [0.0, 0.0, 0.15]
tool_offset_inv = np.linalg.inv(tool_offset)

# Transform to robot frame
robot_wps = toolpath.transform_to_robot_frame()
print(f'Robot waypoints: {len(robot_wps)}')

if robot_wps:
    wp = robot_wps[0]
    print(f'First waypoint: pos={wp.position}, orientation=\n{wp.orientation}')
    print(f'  is_travel={wp.is_travel}, line={wp.line_number}')

    # Build target pose (same as trajectory_planner._build_target_pose)
    T_nozzle = np.eye(4)
    T_nozzle[:3, :3] = wp.orientation
    T_nozzle[:3, 3] = wp.position
    T_flange = T_nozzle @ tool_offset_inv

    print(f'Flange pos: ({T_flange[0,3]:.4f}, {T_flange[1,3]:.4f}, {T_flange[2,3]:.4f})')
    print(f'Flange orientation:\n{T_flange[:3,:3]}')

    # Convert orientation to quaternion
    def rot_to_quat(R):
        trace = R[0,0] + R[1,1] + R[2,2]
        if trace > 0:
            s = 0.5 / np.sqrt(trace + 1.0)
            return (R[2,1]-R[1,2])*s, (R[0,2]-R[2,0])*s, (R[1,0]-R[0,1])*s, 0.25/s
        elif R[0,0] > R[1,1] and R[0,0] > R[2,2]:
            s = 2.0 * np.sqrt(1.0 + R[0,0] - R[1,1] - R[2,2])
            return 0.25*s, (R[0,1]+R[1,0])/s, (R[0,2]+R[2,0])/s, (R[2,1]-R[1,2])/s
        elif R[1,1] > R[2,2]:
            s = 2.0 * np.sqrt(1.0 + R[1,1] - R[0,0] - R[2,2])
            return (R[0,1]+R[1,0])/s, 0.25*s, (R[1,2]+R[2,1])/s, (R[0,2]-R[2,0])/s
        else:
            s = 2.0 * np.sqrt(1.0 + R[2,2] - R[0,0] - R[1,1])
            return (R[0,2]+R[2,0])/s, (R[1,2]+R[2,1])/s, 0.25*s, (R[1,0]-R[0,1])/s

    qx, qy, qz, qw = rot_to_quat(T_flange[:3,:3])
    print(f'Flange quat: ({qx:.4f}, {qy:.4f}, {qz:.4f}, {qw:.4f})')

    # Call IK
    seed = [0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]
    req = ComputeIK.Request()
    req.target_pose.position.x = float(T_flange[0,3])
    req.target_pose.position.y = float(T_flange[1,3])
    req.target_pose.position.z = float(T_flange[2,3])
    req.target_pose.orientation.x = float(qx)
    req.target_pose.orientation.y = float(qy)
    req.target_pose.orientation.z = float(qz)
    req.target_pose.orientation.w = float(qw)
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
        print('IK TIMEOUT')
    else:
        r = future.result()
        print(f'IK result: success={r.success}, msg={r.message}')
        if r.success:
            print(f'  joints: {[f"{j:.3f}" for j in r.solutions[0].joints]}')

    # Test first 5 waypoints
    print(f'\n=== Testing first 5 robot waypoints ===')
    for i, wp in enumerate(robot_wps[:5]):
        T_nozzle = np.eye(4)
        T_nozzle[:3, :3] = wp.orientation
        T_nozzle[:3, 3] = wp.position
        T_flange = T_nozzle @ tool_offset_inv

        qx, qy, qz, qw = rot_to_quat(T_flange[:3,:3])

        req = ComputeIK.Request()
        req.target_pose.position.x = float(T_flange[0,3])
        req.target_pose.position.y = float(T_flange[1,3])
        req.target_pose.position.z = float(T_flange[2,3])
        req.target_pose.orientation.x = float(qx)
        req.target_pose.orientation.y = float(qy)
        req.target_pose.orientation.z = float(qz)
        req.target_pose.orientation.w = float(qw)
        req.seed_configuration = list(seed)
        req.method = 'lm'
        req.max_iterations = 200
        req.tolerance = 1e-6
        req.check_limits = True

        future = ik_cli.call_async(req)
        t0 = time.time()
        while not future.done() and (time.time() - t0) < 5:
            time.sleep(0.01)

        if not future.done():
            print(f'  wp[{i}]: TIMEOUT')
        else:
            r = future.result()
            pos_str = f'({T_flange[0,3]:.3f}, {T_flange[1,3]:.3f}, {T_flange[2,3]:.3f})'
            if r.success:
                print(f'  wp[{i}]: OK pos={pos_str}')
                seed = list(r.solutions[0].joints)
            else:
                print(f'  wp[{i}]: FAIL pos={pos_str} quat=({qx:.3f},{qy:.3f},{qz:.3f},{qw:.3f}) msg={r.message}')

executor.shutdown()
rclpy.shutdown()
