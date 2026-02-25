#!/usr/bin/env python3
"""
Verify the Rz(π) correction to PoE model matches the URDF TF.
"""
import numpy as np
import sys
sys.path.insert(0, '/home/kmedrano/src/industrial_robots/workspace/install/ur_kinematics_node/lib/python3.12/site-packages')
from ur_kinematics_node.screw_kinematics import URScrewKinematics
from ur_kinematics_node.robot_parameters import RobotParameters, _space_to_body_screws

# UR5e dimensions
L1, L2 = 0.425, 0.3922
W1, W2 = 0.1333, 0.0997
H1, H2 = 0.1625, 0.0996

# Tool offset
T_tool = np.eye(4)
T_tool[2, 3] = 0.105

# ─── Original (incorrect) model ───
params_old = RobotParameters()
params_old.M_home = np.array([
    [1, 0, 0, -(L1 + L2)],
    [0, 0, -1, -(W1 + H2)],
    [0, 1, 0, H1 - W2],
    [0, 0, 0, 1]
])
params_old.screw_axes_space = np.array([
    [0, 0, 1, 0, 0, 0],
    [0, -1, 0, H1, 0, 0],
    [0, -1, 0, H1, 0, L1],
    [0, -1, 0, H1, 0, L1 + L2],
    [0, 0, -1, W1, -(L1 + L2), 0],
    [0, -1, 0, H1 - W2, 0, L1 + L2],
]).T
params_old.screw_axes_body = _space_to_body_screws(params_old.screw_axes_space, params_old.M_home)
params_old.joint_limits = [(-2*np.pi, 2*np.pi)] * 6
kin_old = URScrewKinematics(params_old)

# ─── Corrected model (Rz(π) applied) ───
# Rz(π) negates X and Y components of both ω and v in each screw axis
# M_home gets pre-multiplied by Rz4x4(π)
params_new = RobotParameters()
params_new.M_home = np.array([
    [-1, 0, 0, (L1 + L2)],
    [0, 0, 1, (W1 + H2)],
    [0, 1, 0, H1 - W2],
    [0, 0, 0, 1]
])
params_new.screw_axes_space = np.array([
    [0, 0, 1, 0, 0, 0],             # S1: Z unchanged
    [0, 1, 0, -H1, 0, 0],           # S2: ω,v X,Y negated
    [0, 1, 0, -H1, 0, L1],          # S3
    [0, 1, 0, -H1, 0, L1 + L2],     # S4
    [0, 0, -1, -W1, (L1 + L2), 0],  # S5
    [0, 1, 0, -(H1 - W2), 0, L1 + L2],  # S6
]).T
params_new.screw_axes_body = _space_to_body_screws(params_new.screw_axes_space, params_new.M_home)
params_new.joint_limits = [(-2*np.pi, 2*np.pi)] * 6
kin_new = URScrewKinematics(params_new)

# Test joint config
joints = np.array([0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0])

print("=" * 70)
print("PoE Model Correction Verification")
print("=" * 70)

# URDF TF expected values (from the TF test):
urdf_tool0_pos = np.array([0.4919, 0.1333, 0.4879])

T_old = kin_old.fk(joints)
T_new = kin_new.fk(joints)

print(f"\nJoints (deg): {np.degrees(joints).round(1)}")
print(f"\nOld PoE FK tool0 pos: {T_old[:3,3].round(4)}")
print(f"New PoE FK tool0 pos: {T_new[:3,3].round(4)}")
print(f"URDF TF tool0 pos:    {urdf_tool0_pos}")

old_err = np.linalg.norm(T_old[:3,3] - urdf_tool0_pos)
new_err = np.linalg.norm(T_new[:3,3] - urdf_tool0_pos)
print(f"\nOld model error vs URDF: {old_err*1000:.3f} mm")
print(f"New model error vs URDF: {new_err*1000:.3f} mm")

# Nozzle position check
T_nozzle_new = T_new @ T_tool
print(f"\nNew nozzle pos: {T_nozzle_new[:3,3].round(4)}")
print(f"New nozzle Z:   {T_nozzle_new[:3,2].round(4)}")

# Now test IK for the print area with the corrected model
Rx_pi = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=float)

print(f"\n{'='*70}")
print("IK Test with Corrected Model")
print(f"{'='*70}")

# Print waypoint: bed center, first layer
target_nozzle_pos = np.array([-0.3, 0.0, -0.0095])
T_nozzle_target = np.eye(4)
T_nozzle_target[:3, :3] = Rx_pi
T_nozzle_target[:3, 3] = target_nozzle_pos
T_flange_target = T_nozzle_target @ np.linalg.inv(T_tool)

print(f"\nTarget nozzle pos: {target_nozzle_pos}")
print(f"Target flange pos: {T_flange_target[:3,3].round(4)}")

# Try different seeds to find the best home config
seeds = {
    "pan=0 (current home)": np.array([0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0]),
    "pan=pi": np.array([np.pi, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0]),
    "pan=-pi": np.array([-np.pi, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0]),
    "pan=pi elbow_down": np.array([np.pi, -np.pi/2, -np.pi/2, -np.pi/2, -np.pi/2, 0.0]),
}

best_seed_name = None
best_joints = None
best_err = float('inf')

for name, seed in seeds.items():
    sol = kin_new.ik_levenberg_marquardt(T_flange_target, seed, 1e-6, 200)
    if sol.is_valid:
        T_check = kin_new.fk(sol.joints) @ T_tool
        err = np.linalg.norm(T_check[:3, 3] - target_nozzle_pos)
        z_ok = np.dot(T_check[:3, 2], [0, 0, -1]) > 0.999

        # FK check with seed
        T_seed_fk = kin_new.fk(seed) @ T_tool

        print(f"\n  Seed: {name}")
        print(f"    Seed FK nozzle: {T_seed_fk[:3,3].round(4)}")
        print(f"    IK solution (deg): {np.degrees(sol.joints).round(1)}")
        print(f"    shoulder_pan: {np.degrees(sol.joints[0]):.1f}°")
        print(f"    FK nozzle pos: {T_check[:3,3].round(4)}")
        print(f"    FK error: {err*1000:.3f} mm")
        print(f"    Nozzle down: {z_ok}")

        if err < best_err:
            best_err = err
            best_joints = sol.joints
            best_seed_name = name
    else:
        print(f"\n  Seed: {name} → IK FAILED")

if best_joints is not None:
    print(f"\n{'='*70}")
    print(f"Best IK seed: {best_seed_name}")
    print(f"Best IK joints (deg): {np.degrees(best_joints).round(2)}")

    # Suggest home joints (above print area with nozzle down)
    # Use the IK solution as starting point, adjust elbow for a good home
    print(f"\nSuggested home_joints (rad): {best_joints.round(4).tolist()}")

# Also check: what does pan=pi home position look like?
print(f"\n{'='*70}")
print("Home Position Candidates (with corrected model)")
print(f"{'='*70}")

candidates = {
    "current [0, -90, 90, -90, -90, 0]": np.array([0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0]),
    "pan=pi [180, -90, 90, -90, -90, 0]": np.array([np.pi, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0]),
    "pan=-pi [-180, -90, 90, -90, -90, 0]": np.array([-np.pi, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0]),
    "pan=pi elbow_neg [180, -90, -90, -90, -90, 0]": np.array([np.pi, -np.pi/2, -np.pi/2, -np.pi/2, -np.pi/2, 0]),
}

for name, j in candidates.items():
    T = kin_new.fk(j) @ T_tool
    pos = T[:3, 3]
    z_ax = T[:3, 2]
    z_down = np.dot(z_ax, [0, 0, -1]) > 0.999
    dist = np.linalg.norm(pos[:2] - np.array([-0.3, 0.0]))
    print(f"\n  {name}")
    print(f"    Nozzle: {pos.round(4)}, Z-down: {z_down}, dist to bed center: {dist*1000:.0f}mm")
