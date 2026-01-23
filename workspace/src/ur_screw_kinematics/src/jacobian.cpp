/**
 * @file jacobian.cpp
 * @brief Implementation of Jacobian computations
 */

#include "ur_screw_kinematics/jacobian.hpp"
#include "ur_screw_kinematics/lie_algebra.hpp"
#include "ur_screw_kinematics/forward_kinematics.hpp"
#include <Eigen/SVD>

namespace ur_kinematics {

Eigen::Matrix<double, 6, 6> jacobian_space(
    const std::vector<ScrewAxis>& screw_axes_space,
    const JointConfiguration& joint_angles) {

    Eigen::Matrix<double, 6, 6> J = Eigen::Matrix<double, 6, 6>::Zero();

    // First column is just S_1
    J.col(0) = screw_axes_space[0];

    // Subsequent columns: J_i = Ad_{e^{[S_1]θ_1}...e^{[S_{i-1}]θ_{i-1}}} · S_i
    Matrix4d T = lie::exp_screw(screw_axes_space[0], joint_angles(0));

    for (int i = 1; i < 6; ++i) {
        Matrix6d Ad_T = lie::adjoint(T);
        J.col(i) = Ad_T * screw_axes_space[i];
        T = T * lie::exp_screw(screw_axes_space[i], joint_angles(i));
    }

    return J;
}

Eigen::Matrix<double, 6, 6> jacobian_body(
    const std::vector<ScrewAxis>& screw_axes_body,
    const JointConfiguration& joint_angles) {

    Eigen::Matrix<double, 6, 6> J = Eigen::Matrix<double, 6, 6>::Zero();

    // Last column is just B_n
    J.col(5) = screw_axes_body[5];

    // Preceding columns: J_i = Ad_{e^{-[B_n]θ_n}...e^{-[B_{i+1}]θ_{i+1}}} · B_i
    Matrix4d T = lie::exp_screw(screw_axes_body[5], -joint_angles(5));

    for (int i = 4; i >= 0; --i) {
        Matrix6d Ad_T = lie::adjoint(T);
        J.col(i) = Ad_T * screw_axes_body[i];
        T = T * lie::exp_screw(screw_axes_body[i], -joint_angles(i));
    }

    return J;
}

Eigen::Matrix<double, 6, 6> jacobian(
    const RobotParameters& params,
    const JointConfiguration& joint_angles,
    bool use_space_frame) {

    if (use_space_frame) {
        return jacobian_space(params.screw_axes_space, joint_angles);
    } else {
        return jacobian_body(params.screw_axes_body, joint_angles);
    }
}

Eigen::Matrix<double, 6, 6> jacobian_analytical(
    const RobotParameters& params,
    const JointConfiguration& joint_angles,
    const std::string& euler_convention) {

    // Get the geometric Jacobian in space frame
    auto J_geom = jacobian_space(params.screw_axes_space, joint_angles);

    // Get current rotation
    Matrix4d T = fk_space_frame(params.screw_axes_space, params.M_home, joint_angles);
    Matrix3d R = T.block<3, 3>(0, 0);

    // Compute the transformation matrix E that converts angular velocity to Euler rates
    // For ZYX (roll-pitch-yaw): ω = E(φ) · φ̇
    // We need E^{-1}

    Matrix3d E_inv = Matrix3d::Identity();

    if (euler_convention == "ZYX" || euler_convention == "RPY") {
        // Extract ZYX Euler angles from rotation matrix
        double pitch = std::asin(-R(2, 0));
        double roll, yaw;

        if (std::abs(std::cos(pitch)) > EPSILON) {
            roll = std::atan2(R(2, 1), R(2, 2));
            yaw = std::atan2(R(1, 0), R(0, 0));
        } else {
            // Gimbal lock
            roll = 0;
            yaw = std::atan2(-R(0, 1), R(1, 1));
        }

        double cr = std::cos(roll);
        double sr = std::sin(roll);
        double cp = std::cos(pitch);
        double sp = std::sin(pitch);

        // E matrix for ZYX: ω = E · [roll_dot, pitch_dot, yaw_dot]^T
        // E^{-1} converts ω to Euler rates
        if (std::abs(cp) > EPSILON) {
            E_inv << 1, sr * sp / cp, cr * sp / cp,
                     0, cr, -sr,
                     0, sr / cp, cr / cp;
        }
    } else if (euler_convention == "ZYZ") {
        // ZYZ Euler angles
        double theta = std::acos(R(2, 2));
        double phi, psi;

        if (std::abs(std::sin(theta)) > EPSILON) {
            phi = std::atan2(R(1, 2), R(0, 2));
            psi = std::atan2(R(2, 1), -R(2, 0));
        } else {
            phi = 0;
            psi = std::atan2(R(1, 0), R(0, 0));
        }

        double st = std::sin(theta);
        double ct = std::cos(theta);
        double cp = std::cos(phi);
        double sp = std::sin(phi);

        if (std::abs(st) > EPSILON) {
            E_inv << -sp / st, cp / st, 0,
                     cp, sp, 0,
                     sp * ct / st, -cp * ct / st, 1;
        }
    }

    // Build the full transformation matrix
    // J_analytical = [I  0 ] · J_geom
    //                [0 E^-1]
    Eigen::Matrix<double, 6, 6> J_analytical;
    J_analytical.block<3, 6>(0, 0) = J_geom.block<3, 6>(3, 0);  // Linear velocity
    J_analytical.block<3, 6>(3, 0) = E_inv * J_geom.block<3, 6>(0, 0);  // Angular

    return J_analytical;
}

double manipulability(const Eigen::Matrix<double, 6, 6>& J) {
    // w = sqrt(det(J · J^T))
    Eigen::Matrix<double, 6, 6> JJT = J * J.transpose();
    double det = JJT.determinant();
    return std::sqrt(std::max(0.0, det));
}

double condition_number(const Eigen::Matrix<double, 6, 6>& J) {
    Eigen::JacobiSVD<Eigen::Matrix<double, 6, 6>> svd(J);
    Eigen::VectorXd singular_values = svd.singularValues();

    double sigma_max = singular_values(0);
    double sigma_min = singular_values(5);

    if (std::abs(sigma_min) < EPSILON) {
        return std::numeric_limits<double>::infinity();
    }

    return sigma_max / sigma_min;
}

bool is_near_singularity(
    const Eigen::Matrix<double, 6, 6>& J,
    double threshold) {

    return manipulability(J) < threshold;
}

Eigen::Matrix<double, 6, 6> jacobian_pseudoinverse(
    const Eigen::Matrix<double, 6, 6>& J,
    double damping) {

    if (damping > EPSILON) {
        return jacobian_damped_inverse(J, damping);
    }

    // Moore-Penrose pseudoinverse using SVD
    Eigen::JacobiSVD<Eigen::Matrix<double, 6, 6>> svd(
        J, Eigen::ComputeFullU | Eigen::ComputeFullV);

    Eigen::VectorXd singular_values = svd.singularValues();
    Eigen::VectorXd singular_values_inv = Eigen::VectorXd::Zero(6);

    for (int i = 0; i < 6; ++i) {
        if (singular_values(i) > EPSILON) {
            singular_values_inv(i) = 1.0 / singular_values(i);
        }
    }

    return svd.matrixV() * singular_values_inv.asDiagonal() * svd.matrixU().transpose();
}

Eigen::Matrix<double, 6, 6> jacobian_damped_inverse(
    const Eigen::Matrix<double, 6, 6>& J,
    double lambda) {

    // J⁺_dls = J^T (J J^T + λ²I)^{-1}
    Eigen::Matrix<double, 6, 6> JJT = J * J.transpose();
    Eigen::Matrix<double, 6, 6> damped = JJT + lambda * lambda * Eigen::Matrix<double, 6, 6>::Identity();

    return J.transpose() * damped.inverse();
}

JointConfiguration twist_to_joint_velocities(
    const Eigen::Matrix<double, 6, 6>& J,
    const Twist& twist,
    double damping) {

    Eigen::Matrix<double, 6, 6> J_inv = jacobian_damped_inverse(J, damping);
    return J_inv * twist;
}

}  // namespace ur_kinematics
