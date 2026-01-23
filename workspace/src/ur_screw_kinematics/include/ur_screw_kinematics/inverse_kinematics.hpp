/**
 * @file inverse_kinematics.hpp
 * @brief Inverse kinematics solvers for Universal Robots
 *
 * Implements both analytical (using Paden-Kahan subproblems) and
 * numerical (Newton-Raphson) inverse kinematics solvers.
 */

#ifndef UR_SCREW_KINEMATICS_INVERSE_KINEMATICS_HPP
#define UR_SCREW_KINEMATICS_INVERSE_KINEMATICS_HPP

#include "ur_screw_kinematics/types.hpp"

namespace ur_kinematics {

// ============================================================================
// Paden-Kahan Canonical Subproblems
// ============================================================================

/**
 * @brief Paden-Kahan Subproblem 1: Rotation about a single axis
 *
 * Find θ such that: e^{[ω̂]θ} · p = q
 *
 * Given:
 * - ω̂: Unit rotation axis
 * - p: Initial point
 * - q: Target point (must be on same circle as p about ω̂)
 * - r: Point on rotation axis
 *
 * @param omega_hat Unit rotation axis
 * @param p Initial point
 * @param q Target point
 * @param r Point on axis
 * @return Angle θ (or NaN if no solution)
 */
double subproblem1(
    const Vector3d& omega_hat,
    const Vector3d& p,
    const Vector3d& q,
    const Vector3d& r);

/**
 * @brief Paden-Kahan Subproblem 2: Two consecutive rotations
 *
 * Find θ₁, θ₂ such that: e^{[ω̂₁]θ₁} · e^{[ω̂₂]θ₂} · p = q
 *
 * Given two intersecting axes ω̂₁ and ω̂₂, find angles to rotate p to q.
 * May have 0, 1, or 2 solutions.
 *
 * @param omega1_hat First unit rotation axis
 * @param omega2_hat Second unit rotation axis
 * @param p Initial point
 * @param q Target point
 * @param r Intersection point of axes
 * @param theta1 Output: first angle(s)
 * @param theta2 Output: second angle(s)
 * @return Number of solutions (0, 1, or 2)
 */
int subproblem2(
    const Vector3d& omega1_hat,
    const Vector3d& omega2_hat,
    const Vector3d& p,
    const Vector3d& q,
    const Vector3d& r,
    std::vector<double>& theta1,
    std::vector<double>& theta2);

/**
 * @brief Paden-Kahan Subproblem 3: Rotation to a distance
 *
 * Find θ such that: ||e^{[ω̂]θ} · p - q|| = d
 *
 * Find angle to rotate p about ω̂ so distance to q equals d.
 * May have 0, 1, or 2 solutions.
 *
 * @param omega_hat Unit rotation axis
 * @param p Point to rotate
 * @param q Reference point
 * @param r Point on axis
 * @param d Target distance
 * @param theta Output: angle(s)
 * @return Number of solutions (0, 1, or 2)
 */
int subproblem3(
    const Vector3d& omega_hat,
    const Vector3d& p,
    const Vector3d& q,
    const Vector3d& r,
    double d,
    std::vector<double>& theta);

/**
 * @brief Paden-Kahan Subproblem 4: Rotation with known projection
 *
 * Find θ such that: ω̂^T · e^{[ω̂₁]θ} · p = d
 *
 * @param omega_hat Direction for projection
 * @param omega1_hat Rotation axis
 * @param p Point to rotate
 * @param r Point on axis
 * @param d Target projection value
 * @param theta Output: angle(s)
 * @return Number of solutions (0, 1, or 2)
 */
int subproblem4(
    const Vector3d& omega_hat,
    const Vector3d& omega1_hat,
    const Vector3d& p,
    const Vector3d& r,
    double d,
    std::vector<double>& theta);

// ============================================================================
// Inverse Kinematics Solvers
// ============================================================================

/**
 * @brief Analytical IK solver for 6-DOF UR robots
 *
 * Uses closed-form solution based on Paden-Kahan subproblems.
 * Returns up to 8 solutions for the UR robot structure.
 *
 * @param params Robot parameters
 * @param T_target Target end-effector pose
 * @return IKSolutions containing all valid solutions
 */
IKSolutions ik_analytical(
    const RobotParameters& params,
    const Matrix4d& T_target);

/**
 * @brief Numerical IK using Newton-Raphson iteration
 *
 * Iteratively solves: T(θ) = T_target
 * using the body Jacobian for updates.
 *
 * @param params Robot parameters
 * @param T_target Target end-effector pose
 * @param theta_init Initial joint configuration guess
 * @param tolerance Convergence tolerance
 * @param max_iterations Maximum iterations
 * @return IKSolution with result and convergence info
 */
IKSolution ik_newton_raphson(
    const RobotParameters& params,
    const Matrix4d& T_target,
    const JointConfiguration& theta_init,
    double tolerance = IK_TOLERANCE,
    int max_iterations = MAX_IK_ITERATIONS);

/**
 * @brief Numerical IK using Levenberg-Marquardt
 *
 * More robust than Newton-Raphson, especially far from solution.
 *
 * @param params Robot parameters
 * @param T_target Target end-effector pose
 * @param theta_init Initial guess
 * @param tolerance Convergence tolerance
 * @param max_iterations Maximum iterations
 * @return IKSolution
 */
IKSolution ik_levenberg_marquardt(
    const RobotParameters& params,
    const Matrix4d& T_target,
    const JointConfiguration& theta_init,
    double tolerance = IK_TOLERANCE,
    int max_iterations = MAX_IK_ITERATIONS);

/**
 * @brief IK with joint limit enforcement
 *
 * Wraps analytical or numerical IK with joint limit checking.
 *
 * @param params Robot parameters (must include joint_limits)
 * @param T_target Target end-effector pose
 * @param method "analytical", "newton", or "lm"
 * @param theta_init Initial guess (for numerical methods)
 * @return IKSolutions with only limit-respecting solutions
 */
IKSolutions ik_with_limits(
    const RobotParameters& params,
    const Matrix4d& T_target,
    const std::string& method = "analytical",
    const JointConfiguration& theta_init = JointConfiguration::Zero());

/**
 * @brief Position-only IK (3-DOF constraint)
 *
 * Finds joint configuration to reach target position.
 * Orientation is unconstrained (useful for redundancy).
 *
 * @param params Robot parameters
 * @param target_position Target 3D position
 * @param theta_init Initial guess
 * @return IKSolution
 */
IKSolution ik_position_only(
    const RobotParameters& params,
    const Vector3d& target_position,
    const JointConfiguration& theta_init = JointConfiguration::Zero());

/**
 * @brief Compute pose error between current and target
 *
 * Returns 6-vector error [ω_error, v_error] suitable for IK iteration.
 *
 * @param T_current Current end-effector pose
 * @param T_target Target end-effector pose
 * @return 6-vector twist error
 */
Vector6d pose_error(const Matrix4d& T_current, const Matrix4d& T_target);

/**
 * @brief Normalize joint angles to [-π, π] range
 *
 * @param theta Joint angles
 * @return Normalized angles
 */
JointConfiguration normalize_angles(const JointConfiguration& theta);

/**
 * @brief Normalize joint angles to [0, 2π] range
 *
 * @param theta Joint angles
 * @return Normalized angles
 */
JointConfiguration normalize_angles_positive(const JointConfiguration& theta);

/**
 * @brief Check if joint configuration respects limits
 *
 * @param theta Joint configuration
 * @param limits Joint limits [(min, max), ...]
 * @return true if all joints within limits
 */
bool check_joint_limits(
    const JointConfiguration& theta,
    const std::vector<std::pair<double, double>>& limits);

/**
 * @brief Find nearest valid configuration respecting limits
 *
 * Clamps joints that exceed limits to their boundaries.
 *
 * @param theta Joint configuration
 * @param limits Joint limits
 * @return Clamped configuration
 */
JointConfiguration clamp_to_limits(
    const JointConfiguration& theta,
    const std::vector<std::pair<double, double>>& limits);

}  // namespace ur_kinematics

#endif  // UR_SCREW_KINEMATICS_INVERSE_KINEMATICS_HPP
