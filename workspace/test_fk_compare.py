#!/usr/bin/env python3
"""Derive correct PoE screw axes from URDF chain and verify FK match."""
import numpy as np

from ur_kinematics_node.robot_parameters import load_robot_parameters, RobotParameters
from ur_kinematics_node.screw_kinematics import URScrewKinematics


def Rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]])

def Rz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c,-s,0],[s,c,0],[0,0,1]])

def rpy_to_R(roll, pitch, yaw):
    """URDF rpy convention: R = Rz(yaw) Ry(pitch) Rx(roll)"""
    c, s = np.cos(pitch), np.sin(pitch)
    Ry_m = np.array([[c,0,s],[0,1,0],[-s,0,c]])
    return Rz(yaw) @ Ry_m @ Rx(roll)

def T44(R, p):
    T = np.eye(4)
    T[:3,:3] = R
    T[:3,3] = p
    return T


def urdf_fk_tool0(q, joint_origins):
    """URDF FK base_link -> tool0. All joints axis=[0,0,1]."""
    pi = np.pi
    T = np.eye(4)
    for i in range(6):
        xyz, rpy = joint_origins[i]
        T_origin = T44(rpy_to_R(rpy[0], rpy[1], rpy[2]), np.array(xyz))
        T_joint = T44(Rz(q[i]), np.zeros(3))
        T = T @ T_origin @ T_joint
    # wrist_3_link -> flange -> tool0
    T = T @ T44(rpy_to_R(0, -pi/2, -pi/2), np.zeros(3))
    T = T @ T44(rpy_to_R(pi/2, 0, pi/2), np.zeros(3))
    return T


def derive_screw_axes_from_urdf(joint_origins):
    """Derive space-frame screw axes from URDF chain at zero config.

    For each revolute joint (axis=[0,0,1] in local frame):
      1. Trace through chain to find joint position and axis in world frame
      2. Compute screw axis S = [omega; q x omega]
    """
    pi = np.pi
    T = np.eye(4)
    screw_axes = []

    for i in range(6):
        xyz, rpy = joint_origins[i]
        T_origin = T44(rpy_to_R(rpy[0], rpy[1], rpy[2]), np.array(xyz))
        T = T @ T_origin

        # Joint axis in world frame
        R = T[:3, :3]
        omega = R @ np.array([0, 0, 1])  # all joints are Z-axis
        q = T[:3, 3]  # joint position

        # Screw axis: S = [omega; q x omega]
        v = np.cross(q, omega)
        S = np.concatenate([omega, v])
        screw_axes.append(S)

        print(f"Joint {i+1}: pos={np.round(q, 5).tolist()}, "
              f"axis={np.round(omega, 5).tolist()}, "
              f"v={np.round(v, 5).tolist()}")

        # Apply zero rotation (identity at zero config)
        T_joint = T44(Rz(0), np.zeros(3))
        T = T @ T_joint

    return np.array(screw_axes).T  # 6x6, columns are screw axes


def _adjoint(T):
    R = T[:3, :3]
    p = T[:3, 3]
    pskew = np.array([[0,-p[2],p[1]],[p[2],0,-p[0]],[-p[1],p[0],0]])
    Ad = np.zeros((6, 6))
    Ad[:3, :3] = R
    Ad[3:, :3] = pskew @ R
    Ad[3:, 3:] = R
    return Ad


def space_to_body_screws(S_space, M_home):
    R = M_home[:3, :3]
    p = M_home[:3, 3]
    M_inv = np.eye(4)
    M_inv[:3, :3] = R.T
    M_inv[:3, 3] = -R.T @ p
    return _adjoint(M_inv) @ S_space


# UR5e joint origins from default_kinematics.yaml
pi = np.pi
ur5e_origins = [
    ((0, 0, 0.1625), (0, 0, 0)),
    ((0, 0, 0), (pi/2, 0, 0)),
    ((-0.425, 0, 0), (0, 0, 0)),
    ((-0.3922, 0, 0.1333), (0, 0, 0)),
    ((0, -0.0997, 0), (pi/2, 0, 0)),
    ((0, 0.0996, 0), (pi/2, pi, pi)),
]

print("="*60)
print("  Deriving correct screw axes from URDF chain")
print("="*60)
S_space = derive_screw_axes_from_urdf(ur5e_origins)

M_home = urdf_fk_tool0(np.zeros(6), ur5e_origins)
print(f"\nCorrect M_home (URDF tool0 at q=0):")
for row in M_home:
    print(f"  [{row[0]:10.6f} {row[1]:10.6f} {row[2]:10.6f} {row[3]:10.6f}]")

print(f"\nScrew axes matrix (columns):")
for i in range(6):
    s = S_space[:, i]
    print(f"  S{i+1} = [{s[0]:8.5f} {s[1]:8.5f} {s[2]:8.5f} "
          f"{s[3]:8.5f} {s[4]:8.5f} {s[5]:8.5f}]")

# Compute body screws
S_body = space_to_body_screws(S_space, M_home)

# Build corrected kinematics
params_corrected = RobotParameters()
params_corrected.model_name = "ur5e"
params_corrected.M_home = M_home
params_corrected.screw_axes_space = S_space
params_corrected.screw_axes_body = S_body
params_corrected.joint_limits = [(-2*np.pi, 2*np.pi)] * 6

kin_corrected = URScrewKinematics(params_corrected)

# Compare
configs = [
    ("Zero config", [0, 0, 0, 0, 0, 0]),
    ("Home config", [0, -90, 90, -90, -90, 0]),
    ("Old calibration", [-43.32, -30.72, 132.3, 78.42, 43.32, 0]),
    ("New calibration", [-43.31, -69.75, 138.91, -159.16, -90.0, -133.31]),
    ("Typical print pose", [-30, -60, 120, -150, -90, 0]),
    ("Random config", [45, -120, 80, -30, -60, 90]),
]

print("\n" + "="*60)
print("  CORRECTED PoE model vs URDF FK comparison")
print("="*60)

all_pass = True
for label, q_deg in configs:
    q_rad = np.radians(q_deg)

    T_poe = kin_corrected.fk(q_rad)
    T_urdf = urdf_fk_tool0(q_rad, ur5e_origins)

    pos_err = np.linalg.norm(T_poe[:3, 3] - T_urdf[:3, 3])
    R_diff = T_poe[:3,:3].T @ T_urdf[:3,:3]
    rot_err = np.arccos(np.clip((np.trace(R_diff) - 1) / 2, -1, 1))

    status = "PASS" if pos_err < 0.001 and rot_err < 0.01 else "FAIL"
    if status == "FAIL":
        all_pass = False

    print(f"\n  [{status}] {label}: q={np.round(q_deg, 1).tolist()}")
    print(f"    PoE pos:  {np.round(T_poe[:3, 3], 5).tolist()}")
    print(f"    URDF pos: {np.round(T_urdf[:3, 3], 5).tolist()}")
    print(f"    Pos err:  {pos_err*1000:.4f} mm,  Rot err: {np.degrees(rot_err):.4f} deg")

print(f"\n{'='*60}")
print(f"  Overall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
print(f"{'='*60}")

# Test IK roundtrip
print(f"\n{'='*60}")
print(f"  IK Roundtrip Test (corrected model)")
print(f"{'='*60}")

# Target: nozzle at bed center pointing down
# With the corrected model, the FK frame is the URDF tool0 frame
target_pos = np.array([-0.3, 0.0, 0.095])  # position in URDF frame
# The URDF tool0 Z-axis points "forward" (Z+ up in flange -> Z+ forward in tool0)
# For nozzle-down: the tool0 frame at zero config has Z=[0,1,0].
# We need to check what orientation makes the physical tool point down.

# At home config, URDF tool0:
T_home = urdf_fk_tool0(np.radians([0, -90, 90, -90, -90, 0]), ur5e_origins)
print(f"\nHome config tool0 orientation:")
for row in T_home[:3,:3]:
    print(f"  [{row[0]:8.4f} {row[1]:8.4f} {row[2]:8.4f}]")
print(f"  Position: {np.round(T_home[:3, 3], 4).tolist()}")
print(f"  tool0 Z axis: {np.round(T_home[:3, 2], 4).tolist()}")
