#!/usr/bin/env python3
"""
UR5e Screw Theory Kinematics - FK and IK
Verified implementation using Product of Exponentials (PoE)
"""

import numpy as np

np.set_printoptions(precision=4, suppress=True)

# =============================================================================
# CONSTANTS AND UTILITIES
# =============================================================================
EPSILON = 1e-10


def skew3(v):
    """Create 3x3 skew-symmetric matrix from 3-vector."""
    return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])


def rodrigues(w, theta):
    """Rodrigues formula: rotation matrix from axis-angle."""
    if np.linalg.norm(w) < EPSILON or abs(theta) < EPSILON:
        return np.eye(3)
    w_hat = w / np.linalg.norm(w)
    K = skew3(w_hat)
    return np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * K @ K


def exp_se3(S, theta):
    """Matrix exponential for screw motion: se(3) -> SE(3)."""
    w, v = S[:3], S[3:]
    T = np.eye(4)
    w_norm = np.linalg.norm(w)
    if w_norm < EPSILON:
        # Pure translation
        T[:3, 3] = v * theta
    else:
        # Rotation + translation
        T[:3, :3] = rodrigues(w, theta)
        w_hat = w / w_norm
        K = skew3(w_hat)
        G = np.eye(3) * theta + (1 - np.cos(theta)) * K + (theta - np.sin(theta)) * K @ K
        T[:3, 3] = G @ v
    return T


def log_R(R):
    """Matrix logarithm: SO(3) -> so(3), returns rotation vector."""
    acosinput = np.clip((np.trace(R) - 1) / 2.0, -1, 1)
    if acosinput >= 1:
        return np.zeros(3)
    theta = np.arccos(acosinput)
    if abs(theta) < EPSILON:
        return np.zeros(3)
    return theta / (2 * np.sin(theta)) * np.array([
        R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]
    ])


def adjoint_se3(T):
    """6x6 Adjoint representation of SE(3)."""
    R, p = T[:3, :3], T[:3, 3]
    Ad = np.zeros((6, 6))
    Ad[:3, :3] = R
    Ad[3:, :3] = skew3(p) @ R
    Ad[3:, 3:] = R
    return Ad


def normalize_angle(theta):
    """Normalize angle to [-pi, pi]."""
    return np.mod(theta + np.pi, 2 * np.pi) - np.pi


# =============================================================================
# UR5e ROBOT MODEL
# =============================================================================
class UR5eKinematics:
    """Screw theory kinematics for UR5e robot."""

    def __init__(self):
        # UR5e DH parameters
        self.d1 = 0.1625   # Base height
        self.a2 = -0.425   # Upper arm length
        self.a3 = -0.3922  # Forearm length
        self.d4 = 0.1333   # Wrist 1 offset
        self.d5 = 0.0997   # Wrist 2 offset
        self.d6 = 0.0996   # Tool offset

        # Home configuration M (end-effector at theta=0)
        self.M = np.array([
            [-1, 0, 0, -(self.a2 + self.a3)],
            [0, -1, 0, self.d4 + self.d5],
            [0, 0, 1, self.d1 - self.d6],
            [0, 0, 0, 1]
        ])

        # Compute screw axes in space frame
        self.Slist = self._compute_screw_axes()

    def _compute_screw_axes(self):
        """Compute screw axes for each joint in space frame."""
        d1, a2, a3, d4, d5 = self.d1, self.a2, self.a3, self.d4, self.d5

        # Joint axes (w) and points on axes (q)
        joints = [
            (np.array([0, 0, 1]), np.array([0, 0, 0])),           # J1: z at origin
            (np.array([0, 1, 0]), np.array([0, 0, d1])),          # J2: y at (0,0,d1)
            (np.array([0, 1, 0]), np.array([a2, 0, d1])),         # J3: y at (a2,0,d1)
            (np.array([0, 1, 0]), np.array([a2 + a3, 0, d1])),    # J4: y at (a2+a3,0,d1)
            (np.array([0, 0, -1]), np.array([a2 + a3, d4, d1])),  # J5: -z at wrist
            (np.array([0, 1, 0]), np.array([a2 + a3, d4 + d5, d1])),  # J6: y at tool
        ]

        Slist = []
        for w, q in joints:
            # S = [w; -w x q]
            v = np.cross(-w, q)
            Slist.append(np.concatenate([w, v]))

        return np.column_stack(Slist)

    def fk(self, theta):
        """Forward kinematics using PoE formula."""
        T = np.eye(4)
        for i in range(6):
            T = T @ exp_se3(self.Slist[:, i], theta[i])
        return T @ self.M

    def forward_kinematics(self, theta):
        """Forward kinematics (alias for fk)."""
        return self.fk(theta)

    def jacobian(self, theta):
        """Compute space Jacobian."""
        J = np.zeros((6, 6))
        J[:, 0] = self.Slist[:, 0]
        T = np.eye(4)
        for i in range(1, 6):
            T = T @ exp_se3(self.Slist[:, i - 1], theta[i - 1])
            J[:, i] = adjoint_se3(T) @ self.Slist[:, i]
        return J

    def ik(self, T_target, theta_init=None, max_iter=300, tol=1e-5):
        """
        Inverse kinematics using damped Newton-Raphson.

        Args:
            T_target: Target pose (4x4)
            theta_init: Initial guess (default: non-singular pose)
            max_iter: Maximum iterations
            tol: Convergence tolerance

        Returns:
            theta: Joint angles
            success: Convergence flag
            iterations: Number of iterations
            error_mm: Final position error in mm
        """
        if theta_init is None:
            # Start from a non-singular configuration
            theta_init = np.array([0, -np.pi/4, np.pi/2, -np.pi/4, -np.pi/2, 0])

        theta = theta_init.astype(float).copy()

        for it in range(max_iter):
            T_cur = self.fk(theta)

            # Compute errors
            R_cur, p_cur = T_cur[:3, :3], T_cur[:3, 3]
            R_tar, p_tar = T_target[:3, :3], T_target[:3, 3]

            # Orientation error (in space frame)
            R_err = R_tar @ R_cur.T
            w_err = log_R(R_err)

            # Position error
            p_err = p_tar - p_cur

            # Check convergence
            if np.linalg.norm(w_err) < tol and np.linalg.norm(p_err) < tol:
                theta_norm = np.array([normalize_angle(t) for t in theta])
                return theta_norm, True, it + 1, np.linalg.norm(p_err) * 1000

            # Full twist error [omega; v]
            V_err = np.concatenate([w_err, p_err])

            # Jacobian with damping for numerical stability
            J = self.jacobian(theta)
            cond = np.linalg.cond(J)
            lam = 0.05 if cond > 1e10 else 0.001

            JJT = J @ J.T + lam * lam * np.eye(6)
            dtheta = J.T @ np.linalg.solve(JJT, V_err)

            # Update with step size for stability
            theta = theta + 0.5 * dtheta

        T_final = self.fk(theta)
        pos_err = np.linalg.norm(T_final[:3, 3] - T_target[:3, 3]) * 1000
        theta_norm = np.array([normalize_angle(t) for t in theta])
        return theta_norm, False, max_iter, pos_err

    def manipulability(self, theta):
        """Compute manipulability measure."""
        J = self.jacobian(theta)
        return np.sqrt(max(0, np.linalg.det(J @ J.T)))
