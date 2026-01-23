/**
 * @file types.hpp
 * @brief Common type definitions for screw theory kinematics
 *
 * This file defines the fundamental data types used throughout the
 * UR Screw Kinematics library.
 */

#ifndef UR_SCREW_KINEMATICS_TYPES_HPP
#define UR_SCREW_KINEMATICS_TYPES_HPP

#include <Eigen/Dense>
#include <array>
#include <vector>
#include <string>

namespace ur_kinematics {

// Matrix and vector types
using Matrix3d = Eigen::Matrix3d;
using Matrix4d = Eigen::Matrix4d;
using Matrix6d = Eigen::Matrix<double, 6, 6>;
using MatrixXd = Eigen::MatrixXd;

using Vector3d = Eigen::Vector3d;
using Vector6d = Eigen::Matrix<double, 6, 1>;
using VectorXd = Eigen::VectorXd;

// Joint configuration for 6-DOF robot
using JointConfiguration = Eigen::Matrix<double, 6, 1>;

// Screw axis: [omega (3), v (3)]
using ScrewAxis = Vector6d;

// Twist: [omega (3), v (3)]
using Twist = Vector6d;

// Wrench: [moment (3), force (3)]
using Wrench = Vector6d;

/**
 * @brief Homogeneous transformation matrix (SE(3))
 */
struct Transform {
    Matrix4d matrix;

    Transform() : matrix(Matrix4d::Identity()) {}
    explicit Transform(const Matrix4d& m) : matrix(m) {}

    // Extract rotation matrix
    Matrix3d rotation() const { return matrix.block<3, 3>(0, 0); }

    // Extract translation vector
    Vector3d translation() const { return matrix.block<3, 1>(0, 3); }

    // Set rotation
    void setRotation(const Matrix3d& R) { matrix.block<3, 3>(0, 0) = R; }

    // Set translation
    void setTranslation(const Vector3d& p) { matrix.block<3, 1>(0, 3) = p; }

    // Inverse transformation
    Transform inverse() const {
        Matrix4d inv = Matrix4d::Identity();
        Matrix3d R_inv = rotation().transpose();
        inv.block<3, 3>(0, 0) = R_inv;
        inv.block<3, 1>(0, 3) = -R_inv * translation();
        return Transform(inv);
    }

    // Composition
    Transform operator*(const Transform& other) const {
        return Transform(matrix * other.matrix);
    }
};

/**
 * @brief Robot model parameters loaded from configuration
 */
struct RobotParameters {
    std::string model_name;           // e.g., "ur5e", "ur10e"
    int num_joints;                   // Number of joints (6 for UR)

    // DH Parameters (Modified DH convention)
    std::vector<double> a;            // Link lengths
    std::vector<double> d;            // Link offsets
    std::vector<double> alpha;        // Link twists

    // Derived screw theory parameters
    std::vector<double> link_lengths; // L1, L2, etc.
    std::vector<double> offsets;      // W1, W2, H1, H2, etc.

    // Home configuration matrix M (end-effector at zero position)
    Matrix4d M_home;

    // Screw axes in space frame at home position
    std::vector<ScrewAxis> screw_axes_space;

    // Screw axes in body frame
    std::vector<ScrewAxis> screw_axes_body;

    // Joint limits [min, max] in radians
    std::vector<std::pair<double, double>> joint_limits;

    // Dynamic parameters (optional)
    std::vector<double> link_masses;
    std::vector<Vector3d> link_com;   // Center of mass for each link
};

/**
 * @brief IK solution with metadata
 */
struct IKSolution {
    JointConfiguration joints;
    bool is_valid;
    double error;                     // Position/orientation error
    int iterations;                   // For iterative methods
    std::string method;               // "analytical" or "numerical"

    IKSolution() : joints(JointConfiguration::Zero()),
                   is_valid(false), error(0.0), iterations(0) {}
};

/**
 * @brief Collection of IK solutions (up to 8 for 6-DOF)
 */
struct IKSolutions {
    std::vector<IKSolution> solutions;

    size_t validCount() const {
        size_t count = 0;
        for (const auto& sol : solutions) {
            if (sol.is_valid) count++;
        }
        return count;
    }

    // Get solution closest to reference configuration
    IKSolution nearestTo(const JointConfiguration& ref) const;
};

/**
 * @brief Result of forward kinematics computation
 */
struct FKResult {
    Transform end_effector_pose;
    std::vector<Transform> joint_transforms;  // Transform for each joint
    bool is_valid;
};

// Constants
constexpr double PI = 3.14159265358979323846;
constexpr double EPSILON = 1e-10;
constexpr int MAX_IK_ITERATIONS = 100;
constexpr double IK_TOLERANCE = 1e-6;

}  // namespace ur_kinematics

#endif  // UR_SCREW_KINEMATICS_TYPES_HPP
