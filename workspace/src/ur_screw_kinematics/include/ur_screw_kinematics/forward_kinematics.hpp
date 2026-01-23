/**
 * @file forward_kinematics.hpp
 * @brief Forward kinematics using Product of Exponentials (PoE)
 *
 * Implements forward kinematics for Universal Robots using the
 * screw theory Product of Exponentials formulation.
 */

#ifndef UR_SCREW_KINEMATICS_FORWARD_KINEMATICS_HPP
#define UR_SCREW_KINEMATICS_FORWARD_KINEMATICS_HPP

#include "ur_screw_kinematics/types.hpp"
#include "ur_screw_kinematics/lie_algebra.hpp"

namespace ur_kinematics {

/**
 * @brief Forward Kinematics using Product of Exponentials (Space Frame)
 *
 * Computes end-effector pose using the space frame PoE formula:
 * T(θ) = e^{[S₁]θ₁} · e^{[S₂]θ₂} · ... · e^{[Sₙ]θₙ} · M
 *
 * where:
 * - Sᵢ are screw axes expressed in the space (base) frame
 * - θᵢ are joint angles
 * - M is the end-effector pose at home (zero) configuration
 *
 * @param screw_axes Vector of screw axes in space frame
 * @param M_home Home configuration transformation
 * @param joint_angles Current joint configuration
 * @return End-effector transformation matrix
 */
Matrix4d fk_space_frame(
    const std::vector<ScrewAxis>& screw_axes,
    const Matrix4d& M_home,
    const JointConfiguration& joint_angles);

/**
 * @brief Forward Kinematics using Product of Exponentials (Body Frame)
 *
 * Computes end-effector pose using the body frame PoE formula:
 * T(θ) = M · e^{[B₁]θ₁} · e^{[B₂]θ₂} · ... · e^{[Bₙ]θₙ}
 *
 * where Bᵢ are screw axes expressed in the end-effector (body) frame
 *
 * @param screw_axes Vector of screw axes in body frame
 * @param M_home Home configuration transformation
 * @param joint_angles Current joint configuration
 * @return End-effector transformation matrix
 */
Matrix4d fk_body_frame(
    const std::vector<ScrewAxis>& screw_axes,
    const Matrix4d& M_home,
    const JointConfiguration& joint_angles);

/**
 * @brief Compute FK with intermediate joint transforms
 *
 * Returns both end-effector pose and transformations at each joint.
 * Useful for visualization and collision checking.
 *
 * @param screw_axes Vector of screw axes in space frame
 * @param M_home Home configuration transformation
 * @param joint_angles Current joint configuration
 * @return FKResult containing end-effector and all joint poses
 */
FKResult fk_with_joint_transforms(
    const std::vector<ScrewAxis>& screw_axes,
    const Matrix4d& M_home,
    const JointConfiguration& joint_angles);

/**
 * @brief Forward Kinematics using robot parameters
 *
 * Convenience function that extracts parameters from RobotParameters struct.
 *
 * @param params Robot parameters containing screw axes and M_home
 * @param joint_angles Current joint configuration
 * @param use_space_frame If true, use space frame formulation; else body frame
 * @return End-effector transformation matrix
 */
Matrix4d fk(
    const RobotParameters& params,
    const JointConfiguration& joint_angles,
    bool use_space_frame = true);

/**
 * @brief Compute position of end-effector (translation only)
 *
 * Faster than full FK when only position is needed.
 *
 * @param params Robot parameters
 * @param joint_angles Current joint configuration
 * @return 3D position of end-effector
 */
Vector3d fk_position(
    const RobotParameters& params,
    const JointConfiguration& joint_angles);

/**
 * @brief Compute orientation of end-effector (rotation only)
 *
 * @param params Robot parameters
 * @param joint_angles Current joint configuration
 * @return 3x3 rotation matrix of end-effector
 */
Matrix3d fk_orientation(
    const RobotParameters& params,
    const JointConfiguration& joint_angles);

/**
 * @brief Convert screw axes from space to body frame
 *
 * Bᵢ = Ad_{M⁻¹} · Sᵢ
 *
 * @param screw_axes_space Screw axes in space frame
 * @param M_home Home configuration matrix
 * @return Screw axes in body frame
 */
std::vector<ScrewAxis> space_to_body_screws(
    const std::vector<ScrewAxis>& screw_axes_space,
    const Matrix4d& M_home);

/**
 * @brief Convert screw axes from body to space frame
 *
 * Sᵢ = Ad_M · Bᵢ
 *
 * @param screw_axes_body Screw axes in body frame
 * @param M_home Home configuration matrix
 * @return Screw axes in space frame
 */
std::vector<ScrewAxis> body_to_space_screws(
    const std::vector<ScrewAxis>& screw_axes_body,
    const Matrix4d& M_home);

}  // namespace ur_kinematics

#endif  // UR_SCREW_KINEMATICS_FORWARD_KINEMATICS_HPP
