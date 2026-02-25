#!/usr/bin/env python3
"""
Diagnose IK branch issue: check what configuration the solver picks
for print waypoints seeded from home_joints.
"""
import numpy as np
import sys
sys.path.insert(0, '/home/kmedrano/src/industrial_robots/workspace/install/ur_kinematics_node/lib/python3.12/site-packages')
from ur_kinematics_node.robot_parameters import load_robot_parameters
from ur_kinematics_node.screw_kinematics import URScrewKinematics

params = load_robot_parameters(model_name='ur5e')
kin = URScrewKinematics(params)

# Tool offset
T_tool = np.eye(4)
T_tool[2, 3] = 0.105

# Nozzle-down orientation: Rx(pi) = [[1,0,0],[0,-1,0],[0,0,-1]]
Rx_pi = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=float)

# Print origin
print_origin = np.array([-0.3, 0.0, -0.01])

# Current home joints
home_joints = np.array([0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0])

# Alternative: shoulder_pan = pi
home_pi = np.array([np.pi, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0])

print("=" * 70)
print("IK Branch Diagnosis")
print("=" * 70)

# FK at home
T_home = kin.fk(home_joints)
T_nozzle_home = T_home @ T_tool
print(f"\nHome joints (deg): {np.degrees(home_joints).round(1)}")
print(f"Home nozzle pos:   {T_nozzle_home[:3, 3].round(4)}")
print(f"Home nozzle Z-ax:  {T_nozzle_home[:3, 2].round(4)}")

# FK at home with shoulder_pan=pi
T_home_pi = kin.fk(home_pi)
T_nozzle_pi = T_home_pi @ T_tool
print(f"\nHome+pi joints (deg): {np.degrees(home_pi).round(1)}")
print(f"Home+pi nozzle pos:   {T_nozzle_pi[:3, 3].round(4)}")
print(f"Home+pi nozzle Z-ax:  {T_nozzle_pi[:3, 2].round(4)}")

# First print waypoint: G-code origin (0,0,0.5mm) = bed center, first layer
# In robot frame: (-0.3, 0, -0.01 + 0.0005) = (-0.3, 0, -0.0095)
test_points = [
    ("Bed center L1", np.array([-0.3, 0.0, -0.0095])),
    ("Rect corner (-20,-10) L1", np.array([-0.320, -0.010, -0.0095])),
    ("Rect corner (+20,+10) L1", np.array([-0.280, 0.010, -0.0095])),
    ("G28 origin", np.array([-0.3, 0.0, -0.01])),
]

for name, nozzle_pos in test_points:
    print(f"\n--- Target: {name} ---")
    print(f"  Nozzle target: {nozzle_pos}")

    # Build nozzle pose
    T_nozzle = np.eye(4)
    T_nozzle[:3, :3] = Rx_pi
    T_nozzle[:3, 3] = nozzle_pos

    # Compute flange pose: T_flange = T_nozzle @ inv(T_tool)
    T_flange = T_nozzle @ np.linalg.inv(T_tool)
    print(f"  Flange target:  {T_flange[:3, 3].round(4)}")

    # IK seeded from home (shoulder_pan=0)
    sol0 = kin.ik_levenberg_marquardt(T_flange, home_joints, 1e-6, 100)
    if sol0.is_valid:
        j0 = sol0.joints
        T_check = kin.fk(j0)
        T_nozzle_check = T_check @ T_tool
        err = np.linalg.norm(T_nozzle_check[:3, 3] - nozzle_pos)
        print(f"  IK(seed=home):      {np.degrees(j0).round(1)}")
        print(f"    shoulder_pan: {np.degrees(j0[0]):.1f} deg")
        print(f"    FK nozzle:    {T_nozzle_check[:3, 3].round(4)}")
        print(f"    FK error:     {err*1000:.3f} mm")
        print(f"    Nozzle Z-ax:  {T_nozzle_check[:3, 2].round(4)}")
    else:
        print(f"  IK(seed=home):      FAILED")

    # IK seeded from home+pi (shoulder_pan=pi)
    sol_pi = kin.ik_levenberg_marquardt(T_flange, home_pi, 1e-6, 100)
    if sol_pi.is_valid:
        j_pi = sol_pi.joints
        T_check_pi = kin.fk(j_pi)
        T_nozzle_pi = T_check_pi @ T_tool
        err_pi = np.linalg.norm(T_nozzle_pi[:3, 3] - nozzle_pos)
        print(f"  IK(seed=home+pi):   {np.degrees(j_pi).round(1)}")
        print(f"    shoulder_pan: {np.degrees(j_pi[0]):.1f} deg")
        print(f"    FK nozzle:    {T_nozzle_pi[:3, 3].round(4)}")
        print(f"    FK error:     {err_pi*1000:.3f} mm")
        print(f"    Nozzle Z-ax:  {T_nozzle_pi[:3, 2].round(4)}")
    else:
        print(f"  IK(seed=home+pi):   FAILED")

# Also try different home configs
print("\n" + "=" * 70)
print("Testing different shoulder_pan home values")
print("=" * 70)

target_nozzle = np.array([-0.3, 0.0, -0.0095])
T_nozzle_target = np.eye(4)
T_nozzle_target[:3, :3] = Rx_pi
T_nozzle_target[:3, 3] = target_nozzle
T_flange_target = T_nozzle_target @ np.linalg.inv(T_tool)

for pan_deg in [0, 45, 90, 135, 180, -45, -90, -135, -180]:
    seed = np.array([np.radians(pan_deg), -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0])
    sol = kin.ik_levenberg_marquardt(T_flange_target, seed, 1e-6, 200)
    if sol.is_valid:
        j = sol.joints
        T_c = kin.fk(j) @ T_tool
        err = np.linalg.norm(T_c[:3, 3] - target_nozzle) * 1000
        z_ok = np.dot(T_c[:3, 2], [0, 0, -1]) > 0.999
        print(f"  pan_seed={pan_deg:4d}° → pan={np.degrees(j[0]):7.1f}°  "
              f"lift={np.degrees(j[1]):7.1f}°  elbow={np.degrees(j[2]):7.1f}°  "
              f"err={err:.3f}mm  nozzle_down={z_ok}")
    else:
        print(f"  pan_seed={pan_deg:4d}° → FAILED")
