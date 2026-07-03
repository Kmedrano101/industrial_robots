/**
 * Forward kinematics for the UR7e built from the OFFICIAL Denavit–Hartenberg
 * parameters (Universal Robots lists UR5e/UR7e with identical kinematics).
 * Standard DH convention. Verified against the ROS `ur_kinematics_server`:
 * the center bed pose resolves to (0.0023, -0.5326, 0.1113) m in base_link.
 */
import * as THREE from 'three';

// a,d in metres; alpha in radians. Order: base..wrist3.
export const UR7E_DH = {
  d: [0.1625, 0, 0, 0.1333, 0.0997, 0.0996],
  a: [0, -0.425, -0.3922, 0, 0, 0],
  alpha: [Math.PI / 2, 0, 0, Math.PI / 2, -Math.PI / 2, 0],
};

export const UR_JOINT_NAMES = [
  'shoulder_pan_joint',
  'shoulder_lift_joint',
  'elbow_joint',
  'wrist_1_joint',
  'wrist_2_joint',
  'wrist_3_joint',
];

function dhMatrix(theta: number, d: number, a: number, alpha: number): THREE.Matrix4 {
  const ct = Math.cos(theta);
  const st = Math.sin(theta);
  const ca = Math.cos(alpha);
  const sa = Math.sin(alpha);
  // THREE.Matrix4.set() takes row-major arguments.
  return new THREE.Matrix4().set(
    ct, -st * ca, st * sa, a * ct,
    st, ct * ca, -ct * sa, a * st,
    0, sa, ca, d,
    0, 0, 0, 1,
  );
}

/**
 * Cumulative transforms [base_link, J1, J2, J3, J4, J5, J6=tool0].
 * The leading Rz(π) maps the DH "base" frame onto base_link, matching the
 * ROS kinematics server (and the bed coordinates we verified).
 */
export function fkFrames(joints: number[]): THREE.Matrix4[] {
  let T = new THREE.Matrix4().makeRotationZ(Math.PI);
  const frames = [T.clone()];
  for (let i = 0; i < 6; i++) {
    T = T.clone().multiply(dhMatrix(joints[i], UR7E_DH.d[i], UR7E_DH.a[i], UR7E_DH.alpha[i]));
    frames.push(T.clone());
  }
  return frames;
}

/** TCP (tool0) position [m] and roll-pitch-yaw [rad] in base_link. */
export function tcpPose(joints: number[]): {
  pos: [number, number, number];
  rpy: [number, number, number];
} {
  if (!joints || joints.length < 6) {
    return { pos: [0, 0, 0], rpy: [0, 0, 0] };
  }
  const T = fkFrames(joints)[6];
  const p = new THREE.Vector3().setFromMatrixPosition(T);
  const e = new THREE.Euler().setFromRotationMatrix(T, 'XYZ');
  return { pos: [p.x, p.y, p.z], rpy: [e.x, e.y, e.z] };
}
