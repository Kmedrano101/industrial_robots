"""
Screw Theory Kinematics Module

Pure Python implementation of forward and inverse kinematics using
Product of Exponentials (PoE) formulation based on screw theory.

This module provides a fallback when the C++ library is not available.
"""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .robot_parameters import RobotParameters


# Constants
EPSILON = 1e-10
MAX_IK_ITERATIONS = 100
IK_TOLERANCE = 1e-6


@dataclass
class IKSolution:
    """Inverse kinematics solution."""
    joints: np.ndarray
    is_valid: bool = False
    error: float = 0.0
    iterations: int = 0
    method: str = "numerical"


class URScrewKinematics:
    """
    Screw theory kinematics for Universal Robots.

    Implements forward and inverse kinematics using the Product of
    Exponentials (PoE) formulation.
    """

    def __init__(self, params: RobotParameters):
        """
        Initialize kinematics with robot parameters.

        Args:
            params: Robot kinematic parameters
        """
        self.params = params
        self.M_home = params.M_home
        self.screw_axes_space = params.screw_axes_space
        self.screw_axes_body = params.screw_axes_body
        self.joint_limits = params.joint_limits

    # =========================================================================
    # Lie Algebra Operations
    # =========================================================================

    @staticmethod
    def skew3(v: np.ndarray) -> np.ndarray:
        """Create 3x3 skew-symmetric matrix from 3-vector."""
        return np.array([
            [0, -v[2], v[1]],
            [v[2], 0, -v[0]],
            [-v[1], v[0], 0]
        ])

    @staticmethod
    def unskew3(m: np.ndarray) -> np.ndarray:
        """Extract 3-vector from skew-symmetric matrix."""
        return np.array([m[2, 1], m[0, 2], m[1, 0]])

    @staticmethod
    def rodrigues(omega_hat: np.ndarray, theta: float) -> np.ndarray:
        """
        Rodrigues' formula for rotation matrix.

        R = I + sin(θ)[ω̂]× + (1-cos(θ))[ω̂]×²
        """
        if abs(theta) < EPSILON:
            return np.eye(3)

        omega_skew = URScrewKinematics.skew3(omega_hat)
        s = np.sin(theta)
        c = np.cos(theta)

        return np.eye(3) + s * omega_skew + (1 - c) * omega_skew @ omega_skew

    @staticmethod
    def exp_so3(omega: np.ndarray) -> np.ndarray:
        """Matrix exponential so(3) -> SO(3)."""
        theta = np.linalg.norm(omega)
        if theta < EPSILON:
            return np.eye(3)
        omega_hat = omega / theta
        return URScrewKinematics.rodrigues(omega_hat, theta)

    @staticmethod
    def log_so3(R: np.ndarray) -> np.ndarray:
        """Matrix logarithm SO(3) -> so(3)."""
        cos_theta = np.clip((np.trace(R) - 1) / 2, -1, 1)
        theta = np.arccos(cos_theta)

        if abs(theta) < EPSILON:
            return np.array([R[2, 1] - R[1, 2],
                            R[0, 2] - R[2, 0],
                            R[1, 0] - R[0, 1]]) / 2

        if abs(theta - np.pi) < EPSILON:
            # Near π rotation
            RpI = R + np.eye(3)
            max_col = np.argmax([np.linalg.norm(RpI[:, i]) for i in range(3)])
            omega_hat = RpI[:, max_col] / np.linalg.norm(RpI[:, max_col])
            return omega_hat * theta

        omega_hat = URScrewKinematics.unskew3(R - R.T) / (2 * np.sin(theta))
        return omega_hat * theta

    @staticmethod
    def exp_screw(screw_axis: np.ndarray, theta: float) -> np.ndarray:
        """
        Matrix exponential for screw motion se(3) -> SE(3).

        Given screw S = [ω, v] and angle θ, computes exp([S]θ).
        """
        omega = screw_axis[:3]
        v = screw_axis[3:]

        T = np.eye(4)
        omega_norm = np.linalg.norm(omega)

        if omega_norm < EPSILON:
            # Pure translation
            T[:3, 3] = v * theta
        else:
            omega_hat = omega / omega_norm
            theta_scaled = theta * omega_norm

            # Rotation
            T[:3, :3] = URScrewKinematics.rodrigues(omega_hat, theta_scaled)

            # Translation: G(θ)v
            omega_skew = URScrewKinematics.skew3(omega_hat)
            s = np.sin(theta_scaled)
            c = np.cos(theta_scaled)

            G = (np.eye(3) * theta_scaled +
                 (1 - c) * omega_skew +
                 (theta_scaled - s) * omega_skew @ omega_skew)

            T[:3, 3] = G @ (v / omega_norm)

        return T

    @staticmethod
    def log_se3(T: np.ndarray) -> np.ndarray:
        """Matrix logarithm SE(3) -> se(3) (returns twist)."""
        R = T[:3, :3]
        p = T[:3, 3]

        omega = URScrewKinematics.log_so3(R)
        theta = np.linalg.norm(omega)

        twist = np.zeros(6)

        if theta < EPSILON:
            twist[:3] = np.zeros(3)
            twist[3:] = p
        else:
            omega_hat = omega / theta
            omega_skew = URScrewKinematics.skew3(omega_hat)

            half_theta = theta / 2
            cot_half = np.cos(half_theta) / np.sin(half_theta)

            G_inv = (np.eye(3) / theta -
                     omega_skew / 2 +
                     (1 / theta - cot_half / 2) * omega_skew @ omega_skew)

            twist[:3] = omega_hat
            twist[3:] = G_inv @ p

        return twist

    @staticmethod
    def adjoint(T: np.ndarray) -> np.ndarray:
        """Compute 6x6 adjoint representation of SE(3)."""
        R = T[:3, :3]
        p = T[:3, 3]

        Ad = np.zeros((6, 6))
        Ad[:3, :3] = R
        Ad[3:, :3] = URScrewKinematics.skew3(p) @ R
        Ad[3:, 3:] = R

        return Ad

    # =========================================================================
    # Forward Kinematics
    # =========================================================================

    def fk_space_frame(self, joint_angles: np.ndarray) -> np.ndarray:
        """
        Forward kinematics using space frame PoE.

        T(θ) = e^{[S₁]θ₁} · e^{[S₂]θ₂} · ... · e^{[Sₙ]θₙ} · M
        """
        T = np.eye(4)
        for i in range(6):
            T = T @ self.exp_screw(self.screw_axes_space[:, i], joint_angles[i])
        return T @ self.M_home

    def fk_body_frame(self, joint_angles: np.ndarray) -> np.ndarray:
        """
        Forward kinematics using body frame PoE.

        T(θ) = M · e^{[B₁]θ₁} · e^{[B₂]θ₂} · ... · e^{[Bₙ]θₙ}
        """
        T = self.M_home.copy()
        for i in range(6):
            T = T @ self.exp_screw(self.screw_axes_body[:, i], joint_angles[i])
        return T

    def fk(self, joint_angles: np.ndarray,
           use_space_frame: bool = True) -> np.ndarray:
        """
        Compute forward kinematics.

        Args:
            joint_angles: 6-element array of joint angles (radians)
            use_space_frame: Use space frame (True) or body frame (False)

        Returns:
            4x4 end-effector transformation matrix
        """
        if use_space_frame:
            return self.fk_space_frame(joint_angles)
        return self.fk_body_frame(joint_angles)

    def fk_position(self, joint_angles: np.ndarray) -> np.ndarray:
        """Compute end-effector position only."""
        T = self.fk(joint_angles)
        return T[:3, 3]

    def fk_orientation(self, joint_angles: np.ndarray) -> np.ndarray:
        """Compute end-effector orientation only."""
        T = self.fk(joint_angles)
        return T[:3, :3]

    # =========================================================================
    # Jacobian
    # =========================================================================

    def jacobian_space(self, joint_angles: np.ndarray) -> np.ndarray:
        """
        Compute space Jacobian.

        Jₛᵢ = Ad_{e^{[S₁]θ₁}...e^{[Sᵢ₋₁]θᵢ₋₁}} · Sᵢ
        """
        J = np.zeros((6, 6))
        J[:, 0] = self.screw_axes_space[:, 0]

        T = self.exp_screw(self.screw_axes_space[:, 0], joint_angles[0])
        for i in range(1, 6):
            Ad_T = self.adjoint(T)
            J[:, i] = Ad_T @ self.screw_axes_space[:, i]
            T = T @ self.exp_screw(self.screw_axes_space[:, i], joint_angles[i])

        return J

    def jacobian_body(self, joint_angles: np.ndarray) -> np.ndarray:
        """
        Compute body Jacobian.

        Jᵦᵢ = Ad_{e^{-[Bₙ]θₙ}...e^{-[Bᵢ₊₁]θᵢ₊₁}} · Bᵢ
        """
        J = np.zeros((6, 6))
        J[:, 5] = self.screw_axes_body[:, 5]

        T = self.exp_screw(self.screw_axes_body[:, 5], -joint_angles[5])
        for i in range(4, -1, -1):
            Ad_T = self.adjoint(T)
            J[:, i] = Ad_T @ self.screw_axes_body[:, i]
            T = T @ self.exp_screw(self.screw_axes_body[:, i], -joint_angles[i])

        return J

    def jacobian(self, joint_angles: np.ndarray,
                 use_space_frame: bool = True) -> np.ndarray:
        """Compute Jacobian matrix."""
        if use_space_frame:
            return self.jacobian_space(joint_angles)
        return self.jacobian_body(joint_angles)

    @staticmethod
    def manipulability(J: np.ndarray) -> float:
        """Compute manipulability measure."""
        return np.sqrt(max(0, np.linalg.det(J @ J.T)))

    @staticmethod
    def condition_number(J: np.ndarray) -> float:
        """Compute Jacobian condition number."""
        s = np.linalg.svd(J, compute_uv=False)
        if s[-1] < EPSILON:
            return np.inf
        return s[0] / s[-1]

    @staticmethod
    def is_near_singularity(J: np.ndarray, threshold: float = 1e-3) -> bool:
        """Check if near singularity."""
        return URScrewKinematics.manipulability(J) < threshold

    # =========================================================================
    # Inverse Kinematics
    # =========================================================================

    def _pose_error(self, T_current: np.ndarray,
                    T_target: np.ndarray) -> np.ndarray:
        """Compute pose error as body twist."""
        R_c = T_current[:3, :3]
        p_c = T_current[:3, 3]

        R_t = T_target[:3, :3]
        p_t = T_target[:3, 3]

        T_error = np.eye(4)
        T_error[:3, :3] = R_c.T @ R_t
        T_error[:3, 3] = R_c.T @ (p_t - p_c)

        return self.log_se3(T_error)

    def ik_newton_raphson(self, T_target: np.ndarray,
                          theta_init: np.ndarray = None,
                          tolerance: float = IK_TOLERANCE,
                          max_iterations: int = MAX_IK_ITERATIONS) -> IKSolution:
        """
        Numerical IK using Newton-Raphson iteration.

        Args:
            T_target: Target end-effector pose (4x4)
            theta_init: Initial joint configuration guess
            tolerance: Convergence tolerance
            max_iterations: Maximum iterations

        Returns:
            IKSolution with result
        """
        if theta_init is None:
            theta_init = np.zeros(6)

        theta = theta_init.copy()

        for iter_count in range(max_iterations):
            T_current = self.fk_space_frame(theta)
            error = self._pose_error(T_current, T_target)
            error_norm = np.linalg.norm(error)

            if error_norm < tolerance:
                return IKSolution(
                    joints=self._normalize_angles(theta),
                    is_valid=True,
                    error=error_norm,
                    iterations=iter_count + 1,
                    method="newton_raphson"
                )

            J_b = self.jacobian_body(theta)

            # Damped pseudoinverse
            damping = 0.01
            JJT = J_b @ J_b.T + damping**2 * np.eye(6)
            delta_theta = J_b.T @ np.linalg.solve(JJT, error)

            theta += delta_theta

        return IKSolution(
            joints=self._normalize_angles(theta),
            is_valid=False,
            error=np.linalg.norm(self._pose_error(self.fk(theta), T_target)),
            iterations=max_iterations,
            method="newton_raphson"
        )

    def ik_levenberg_marquardt(self, T_target: np.ndarray,
                               theta_init: np.ndarray = None,
                               tolerance: float = IK_TOLERANCE,
                               max_iterations: int = MAX_IK_ITERATIONS) -> IKSolution:
        """
        Numerical IK using Levenberg-Marquardt algorithm.

        More robust than Newton-Raphson, especially far from solution.
        """
        if theta_init is None:
            theta_init = np.zeros(6)

        theta = theta_init.copy()
        lambda_val = 0.01
        lambda_factor = 10.0
        prev_error = np.inf

        for iter_count in range(max_iterations):
            T_current = self.fk_space_frame(theta)
            error = self._pose_error(T_current, T_target)
            error_norm = np.linalg.norm(error)

            if error_norm < tolerance:
                return IKSolution(
                    joints=self._normalize_angles(theta),
                    is_valid=True,
                    error=error_norm,
                    iterations=iter_count + 1,
                    method="levenberg_marquardt"
                )

            J_b = self.jacobian_body(theta)
            JtJ = J_b.T @ J_b
            damped = JtJ + lambda_val * np.eye(6)

            delta_theta = np.linalg.solve(damped, J_b.T @ error)

            theta_new = theta + delta_theta
            T_new = self.fk(theta_new)
            new_error = np.linalg.norm(self._pose_error(T_new, T_target))

            if new_error < prev_error:
                theta = theta_new
                lambda_val /= lambda_factor
                prev_error = new_error
            else:
                lambda_val *= lambda_factor

        return IKSolution(
            joints=self._normalize_angles(theta),
            is_valid=False,
            error=np.linalg.norm(self._pose_error(self.fk(theta), T_target)),
            iterations=max_iterations,
            method="levenberg_marquardt"
        )

    def ik(self, T_target: np.ndarray,
           theta_init: np.ndarray = None,
           method: str = "lm") -> IKSolution:
        """
        Compute inverse kinematics.

        Args:
            T_target: Target end-effector pose (4x4)
            theta_init: Initial guess (optional)
            method: "newton" or "lm" (Levenberg-Marquardt)

        Returns:
            IKSolution with result
        """
        if method == "newton":
            return self.ik_newton_raphson(T_target, theta_init)
        return self.ik_levenberg_marquardt(T_target, theta_init)

    def ik_with_limits(self, T_target: np.ndarray,
                       theta_init: np.ndarray = None,
                       method: str = "lm") -> IKSolution:
        """IK with joint limit checking."""
        solution = self.ik(T_target, theta_init, method)

        if solution.is_valid:
            if not self.check_joint_limits(solution.joints):
                solution.is_valid = False
                solution.error = np.inf

        return solution

    # =========================================================================
    # Utility Functions
    # =========================================================================

    @staticmethod
    def _normalize_angles(theta: np.ndarray) -> np.ndarray:
        """Normalize angles to [-π, π]."""
        return np.mod(theta + np.pi, 2 * np.pi) - np.pi

    def check_joint_limits(self, theta: np.ndarray) -> bool:
        """Check if configuration respects joint limits."""
        for i, (min_val, max_val) in enumerate(self.joint_limits):
            if theta[i] < min_val or theta[i] > max_val:
                return False
        return True

    def clamp_to_limits(self, theta: np.ndarray) -> np.ndarray:
        """Clamp configuration to joint limits."""
        result = theta.copy()
        for i, (min_val, max_val) in enumerate(self.joint_limits):
            result[i] = np.clip(theta[i], min_val, max_val)
        return result
