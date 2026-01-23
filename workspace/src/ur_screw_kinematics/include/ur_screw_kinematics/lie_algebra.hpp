/**
 * @file lie_algebra.hpp
 * @brief Lie algebra operations for screw theory kinematics
 *
 * Implements fundamental operations on SO(3) and SE(3) Lie groups
 * including the exponential map, logarithm, and adjoint representations.
 */

#ifndef UR_SCREW_KINEMATICS_LIE_ALGEBRA_HPP
#define UR_SCREW_KINEMATICS_LIE_ALGEBRA_HPP

#include "ur_screw_kinematics/types.hpp"

namespace ur_kinematics {
namespace lie {

/**
 * @brief Create skew-symmetric matrix from 3-vector (so(3) representation)
 *
 * Given ω = [ω1, ω2, ω3], returns:
 * [ω]× = |  0  -ω3   ω2 |
 *        |  ω3   0  -ω1 |
 *        | -ω2  ω1   0  |
 *
 * @param v Input 3-vector
 * @return 3x3 skew-symmetric matrix
 */
Matrix3d skew3(const Vector3d& v);

/**
 * @brief Extract vector from skew-symmetric matrix (inverse of skew3)
 *
 * @param m 3x3 skew-symmetric matrix
 * @return 3-vector
 */
Vector3d unskew3(const Matrix3d& m);

/**
 * @brief Create 4x4 se(3) matrix from twist vector
 *
 * Given twist V = [ω, v], returns:
 * [V]∧ = | [ω]×  v |
 *        |  0    0 |
 *
 * @param twist 6-vector twist [ω (3), v (3)]
 * @return 4x4 se(3) matrix
 */
Matrix4d twist_to_se3(const Twist& twist);

/**
 * @brief Extract twist vector from se(3) matrix
 *
 * @param se3_matrix 4x4 se(3) matrix
 * @return 6-vector twist
 */
Twist se3_to_twist(const Matrix4d& se3_matrix);

/**
 * @brief Rodrigues' formula for rotation matrix exponential
 *
 * Computes exp([ω]×θ) = I + sin(θ)[ω̂]× + (1 - cos(θ))[ω̂]×²
 * where ω̂ is the unit rotation axis and θ is the rotation angle.
 *
 * @param omega_hat Unit rotation axis (3-vector, ||ω̂|| = 1)
 * @param theta Rotation angle in radians
 * @return 3x3 rotation matrix in SO(3)
 */
Matrix3d rodrigues(const Vector3d& omega_hat, double theta);

/**
 * @brief Matrix exponential for so(3) → SO(3)
 *
 * Given ω (not necessarily unit), computes exp([ω]×)
 * where θ = ||ω|| and ω̂ = ω/θ
 *
 * @param omega Rotation vector (axis * angle)
 * @return 3x3 rotation matrix in SO(3)
 */
Matrix3d exp_so3(const Vector3d& omega);

/**
 * @brief Matrix logarithm for SO(3) → so(3)
 *
 * Extracts the rotation vector ω from rotation matrix R
 * such that R = exp([ω]×)
 *
 * @param R 3x3 rotation matrix in SO(3)
 * @return Rotation vector ω (axis * angle)
 */
Vector3d log_so3(const Matrix3d& R);

/**
 * @brief Matrix exponential for se(3) → SE(3) (screw motion)
 *
 * Given screw axis S = [ω, v] and angle θ, computes:
 * exp([S]θ) = | exp([ω]×θ)   G(θ)v |
 *             |     0          1   |
 *
 * where G(θ) = Iθ + (1-cos(θ))[ω̂]× + (θ-sin(θ))[ω̂]×²
 *
 * For pure translation (ω = 0): exp([S]θ) = | I  vθ |
 *                                           | 0  1  |
 *
 * @param screw_axis Screw axis [ω (3), v (3)]
 * @param theta Joint angle/displacement
 * @return 4x4 transformation matrix in SE(3)
 */
Matrix4d exp_screw(const ScrewAxis& screw_axis, double theta);

/**
 * @brief Matrix logarithm for SE(3) → se(3)
 *
 * Extracts the screw coordinates from transformation matrix T
 *
 * @param T 4x4 transformation matrix in SE(3)
 * @return Twist vector [ω, v] such that T = exp([V]∧)
 */
Twist log_se3(const Matrix4d& T);

/**
 * @brief Compute the 6x6 adjoint representation of SE(3)
 *
 * For T = | R  p |, the adjoint is:
 *         | 0  1 |
 *
 * Ad_T = | R     0   |
 *        | [p]×R  R  |
 *
 * Used to change the frame of reference of twists/wrenches.
 *
 * @param T 4x4 transformation matrix
 * @return 6x6 adjoint matrix
 */
Matrix6d adjoint(const Matrix4d& T);

/**
 * @brief Compute the adjoint representation from rotation and translation
 *
 * @param R 3x3 rotation matrix
 * @param p 3-vector translation
 * @return 6x6 adjoint matrix
 */
Matrix6d adjoint(const Matrix3d& R, const Vector3d& p);

/**
 * @brief Inverse adjoint representation
 *
 * Ad_{T^{-1}} = | R^T      0    |
 *               | -R^T[p]×  R^T |
 *
 * @param T 4x4 transformation matrix
 * @return 6x6 inverse adjoint matrix
 */
Matrix6d adjoint_inverse(const Matrix4d& T);

/**
 * @brief Small adjoint (ad) for Lie bracket computation
 *
 * Given twist V = [ω, v]:
 * ad_V = | [ω]×   0   |
 *        | [v]×  [ω]× |
 *
 * @param twist 6-vector twist
 * @return 6x6 small adjoint matrix
 */
Matrix6d ad_twist(const Twist& twist);

/**
 * @brief Check if matrix is a valid rotation matrix
 *
 * Verifies: R^T R = I and det(R) = 1
 *
 * @param R Matrix to check
 * @param tolerance Numerical tolerance
 * @return true if R ∈ SO(3)
 */
bool is_rotation_matrix(const Matrix3d& R, double tolerance = EPSILON);

/**
 * @brief Check if matrix is a valid transformation matrix
 *
 * Verifies rotation part is valid and bottom row is [0 0 0 1]
 *
 * @param T Matrix to check
 * @param tolerance Numerical tolerance
 * @return true if T ∈ SE(3)
 */
bool is_transformation_matrix(const Matrix4d& T, double tolerance = EPSILON);

/**
 * @brief Normalize rotation matrix to ensure orthogonality
 *
 * Uses SVD to project matrix to nearest rotation matrix
 *
 * @param R Matrix to normalize
 * @return Normalized rotation matrix
 */
Matrix3d normalize_rotation(const Matrix3d& R);

/**
 * @brief Compute rotation matrix for rotation about X axis
 */
Matrix3d rotx(double theta);

/**
 * @brief Compute rotation matrix for rotation about Y axis
 */
Matrix3d roty(double theta);

/**
 * @brief Compute rotation matrix for rotation about Z axis
 */
Matrix3d rotz(double theta);

}  // namespace lie
}  // namespace ur_kinematics

#endif  // UR_SCREW_KINEMATICS_LIE_ALGEBRA_HPP
