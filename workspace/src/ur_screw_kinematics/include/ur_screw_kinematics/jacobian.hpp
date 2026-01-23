/**
 * @file jacobian.hpp
 * @brief Jacobian computation for differential kinematics
 *
 * Implements space and body Jacobian calculations using screw theory.
 */

#ifndef UR_SCREW_KINEMATICS_JACOBIAN_HPP
#define UR_SCREW_KINEMATICS_JACOBIAN_HPP

#include "ur_screw_kinematics/types.hpp"

namespace ur_kinematics {

/**
 * @brief Compute the Space Jacobian
 *
 * The space Jacobian Jₛ(θ) relates joint velocities to the end-effector
 * twist expressed in the space (base) frame:
 *
 * Vₛ = Jₛ(θ) · θ̇
 *
 * Column i of Jₛ is: Jₛᵢ = Ad_{e^{[S₁]θ₁}...e^{[Sᵢ₋₁]θᵢ₋₁}} · Sᵢ
 *
 * @param screw_axes_space Screw axes in space frame
 * @param joint_angles Current joint configuration
 * @return 6xn Space Jacobian matrix
 */
Eigen::Matrix<double, 6, 6> jacobian_space(
    const std::vector<ScrewAxis>& screw_axes_space,
    const JointConfiguration& joint_angles);

/**
 * @brief Compute the Body Jacobian
 *
 * The body Jacobian Jᵦ(θ) relates joint velocities to the end-effector
 * twist expressed in the body (end-effector) frame:
 *
 * Vᵦ = Jᵦ(θ) · θ̇
 *
 * Column i of Jᵦ is: Jᵦᵢ = Ad_{e^{-[Bₙ]θₙ}...e^{-[Bᵢ₊₁]θᵢ₊₁}} · Bᵢ
 *
 * @param screw_axes_body Screw axes in body frame
 * @param joint_angles Current joint configuration
 * @return 6xn Body Jacobian matrix
 */
Eigen::Matrix<double, 6, 6> jacobian_body(
    const std::vector<ScrewAxis>& screw_axes_body,
    const JointConfiguration& joint_angles);

/**
 * @brief Compute Jacobian using robot parameters
 *
 * @param params Robot parameters
 * @param joint_angles Current joint configuration
 * @param use_space_frame If true, compute space Jacobian; else body Jacobian
 * @return 6x6 Jacobian matrix
 */
Eigen::Matrix<double, 6, 6> jacobian(
    const RobotParameters& params,
    const JointConfiguration& joint_angles,
    bool use_space_frame = true);

/**
 * @brief Compute the analytical Jacobian (position + Euler angles)
 *
 * Relates joint velocities to Cartesian velocity [ẋ ẏ ż] and
 * Euler angle rates [α̇ β̇ γ̇] instead of angular velocity.
 *
 * @param params Robot parameters
 * @param joint_angles Current joint configuration
 * @param euler_convention "ZYZ", "ZYX", or "RPY"
 * @return 6x6 Analytical Jacobian matrix
 */
Eigen::Matrix<double, 6, 6> jacobian_analytical(
    const RobotParameters& params,
    const JointConfiguration& joint_angles,
    const std::string& euler_convention = "ZYX");

/**
 * @brief Compute the manipulability measure
 *
 * w = sqrt(det(J · J^T))
 *
 * Measures how well the robot can move in all directions.
 * w = 0 indicates a singularity.
 *
 * @param J Jacobian matrix (space or body)
 * @return Manipulability measure
 */
double manipulability(const Eigen::Matrix<double, 6, 6>& J);

/**
 * @brief Compute the condition number of the Jacobian
 *
 * κ(J) = σ_max / σ_min
 *
 * Indicates proximity to singularity (high value = near singular)
 *
 * @param J Jacobian matrix
 * @return Condition number
 */
double condition_number(const Eigen::Matrix<double, 6, 6>& J);

/**
 * @brief Check if configuration is near a singularity
 *
 * @param J Jacobian matrix
 * @param threshold Manipulability threshold
 * @return true if near singularity
 */
bool is_near_singularity(
    const Eigen::Matrix<double, 6, 6>& J,
    double threshold = 1e-3);

/**
 * @brief Compute the pseudoinverse of the Jacobian
 *
 * J⁺ = J^T (J J^T)^{-1} for over-determined systems
 * J⁺ = (J^T J)^{-1} J^T for under-determined systems
 *
 * Uses damped least squares near singularities.
 *
 * @param J Jacobian matrix
 * @param damping Damping factor for singularity robustness
 * @return Pseudoinverse of J
 */
Eigen::Matrix<double, 6, 6> jacobian_pseudoinverse(
    const Eigen::Matrix<double, 6, 6>& J,
    double damping = 0.0);

/**
 * @brief Compute damped least-squares inverse (DLS)
 *
 * J⁺_dls = J^T (J J^T + λ²I)^{-1}
 *
 * More numerically stable near singularities.
 *
 * @param J Jacobian matrix
 * @param lambda Damping factor
 * @return DLS inverse of J
 */
Eigen::Matrix<double, 6, 6> jacobian_damped_inverse(
    const Eigen::Matrix<double, 6, 6>& J,
    double lambda = 0.01);

/**
 * @brief Compute joint velocities from end-effector twist
 *
 * θ̇ = J⁺ · V
 *
 * @param J Jacobian matrix
 * @param twist Desired end-effector twist
 * @param damping Damping factor for pseudoinverse
 * @return Joint velocities
 */
JointConfiguration twist_to_joint_velocities(
    const Eigen::Matrix<double, 6, 6>& J,
    const Twist& twist,
    double damping = 0.01);

}  // namespace ur_kinematics

#endif  // UR_SCREW_KINEMATICS_JACOBIAN_HPP
