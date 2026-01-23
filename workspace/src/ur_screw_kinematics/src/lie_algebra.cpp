/**
 * @file lie_algebra.cpp
 * @brief Implementation of Lie algebra operations
 */

#include "ur_screw_kinematics/lie_algebra.hpp"
#include <cmath>
#include <Eigen/SVD>

namespace ur_kinematics {
namespace lie {

Matrix3d skew3(const Vector3d& v) {
    Matrix3d m;
    m <<     0, -v(2),  v(1),
          v(2),     0, -v(0),
         -v(1),  v(0),     0;
    return m;
}

Vector3d unskew3(const Matrix3d& m) {
    return Vector3d(m(2, 1), m(0, 2), m(1, 0));
}

Matrix4d twist_to_se3(const Twist& twist) {
    Matrix4d se3 = Matrix4d::Zero();
    se3.block<3, 3>(0, 0) = skew3(twist.head<3>());
    se3.block<3, 1>(0, 3) = twist.tail<3>();
    return se3;
}

Twist se3_to_twist(const Matrix4d& se3_matrix) {
    Twist twist;
    twist.head<3>() = unskew3(se3_matrix.block<3, 3>(0, 0));
    twist.tail<3>() = se3_matrix.block<3, 1>(0, 3);
    return twist;
}

Matrix3d rodrigues(const Vector3d& omega_hat, double theta) {
    if (std::abs(theta) < EPSILON) {
        return Matrix3d::Identity();
    }

    Matrix3d omega_skew = skew3(omega_hat);
    double s = std::sin(theta);
    double c = std::cos(theta);

    // Rodrigues' formula: R = I + sin(θ)[ω̂]× + (1-cos(θ))[ω̂]×²
    return Matrix3d::Identity() + s * omega_skew + (1.0 - c) * omega_skew * omega_skew;
}

Matrix3d exp_so3(const Vector3d& omega) {
    double theta = omega.norm();
    if (theta < EPSILON) {
        return Matrix3d::Identity();
    }
    Vector3d omega_hat = omega / theta;
    return rodrigues(omega_hat, theta);
}

Vector3d log_so3(const Matrix3d& R) {
    double cos_theta = (R.trace() - 1.0) / 2.0;

    // Clamp to handle numerical errors
    cos_theta = std::max(-1.0, std::min(1.0, cos_theta));

    double theta = std::acos(cos_theta);

    if (std::abs(theta) < EPSILON) {
        // Near identity: use small angle approximation
        return Vector3d(R(2, 1) - R(1, 2),
                        R(0, 2) - R(2, 0),
                        R(1, 0) - R(0, 1)) / 2.0;
    }

    if (std::abs(theta - PI) < EPSILON) {
        // Near π rotation: special handling
        // Find the column of R + I with largest norm
        Matrix3d RpI = R + Matrix3d::Identity();
        int max_col = 0;
        double max_norm = RpI.col(0).norm();
        for (int i = 1; i < 3; ++i) {
            double norm = RpI.col(i).norm();
            if (norm > max_norm) {
                max_norm = norm;
                max_col = i;
            }
        }
        Vector3d omega_hat = RpI.col(max_col).normalized();
        return omega_hat * theta;
    }

    // General case
    Vector3d omega_hat = unskew3(R - R.transpose()) / (2.0 * std::sin(theta));
    return omega_hat * theta;
}

Matrix4d exp_screw(const ScrewAxis& screw_axis, double theta) {
    Vector3d omega = screw_axis.head<3>();
    Vector3d v = screw_axis.tail<3>();

    Matrix4d T = Matrix4d::Identity();

    double omega_norm = omega.norm();

    if (omega_norm < EPSILON) {
        // Pure translation (prismatic joint)
        T.block<3, 1>(0, 3) = v * theta;
    } else {
        // Rotation (revolute joint)
        Vector3d omega_hat = omega / omega_norm;
        double theta_scaled = theta * omega_norm;

        // Rotation part
        T.block<3, 3>(0, 0) = rodrigues(omega_hat, theta_scaled);

        // Translation part: G(θ)v where
        // G(θ) = Iθ + (1-cos(θ))[ω̂]× + (θ-sin(θ))[ω̂]×²
        Matrix3d omega_skew = skew3(omega_hat);
        double s = std::sin(theta_scaled);
        double c = std::cos(theta_scaled);

        Matrix3d G = Matrix3d::Identity() * theta_scaled +
                     (1.0 - c) * omega_skew +
                     (theta_scaled - s) * omega_skew * omega_skew;

        T.block<3, 1>(0, 3) = G * (v / omega_norm);
    }

    return T;
}

Twist log_se3(const Matrix4d& T) {
    Matrix3d R = T.block<3, 3>(0, 0);
    Vector3d p = T.block<3, 1>(0, 3);

    Vector3d omega = log_so3(R);
    double theta = omega.norm();

    Twist twist;

    if (theta < EPSILON) {
        // Near identity rotation
        twist.head<3>() = Vector3d::Zero();
        twist.tail<3>() = p;
    } else {
        Vector3d omega_hat = omega / theta;
        Matrix3d omega_skew = skew3(omega_hat);

        // G^{-1} = I/θ - [ω̂]×/2 + (1/θ - cot(θ/2)/2)[ω̂]×²
        double half_theta = theta / 2.0;
        double cot_half = std::cos(half_theta) / std::sin(half_theta);

        Matrix3d G_inv = Matrix3d::Identity() / theta -
                         omega_skew / 2.0 +
                         (1.0 / theta - cot_half / 2.0) * omega_skew * omega_skew;

        twist.head<3>() = omega_hat;
        twist.tail<3>() = G_inv * p;
    }

    return twist;
}

Matrix6d adjoint(const Matrix4d& T) {
    Matrix3d R = T.block<3, 3>(0, 0);
    Vector3d p = T.block<3, 1>(0, 3);
    return adjoint(R, p);
}

Matrix6d adjoint(const Matrix3d& R, const Vector3d& p) {
    Matrix6d Ad = Matrix6d::Zero();

    // Ad_T = | R     0   |
    //        | [p]×R  R  |
    Ad.block<3, 3>(0, 0) = R;
    Ad.block<3, 3>(3, 0) = skew3(p) * R;
    Ad.block<3, 3>(3, 3) = R;

    return Ad;
}

Matrix6d adjoint_inverse(const Matrix4d& T) {
    Matrix3d R = T.block<3, 3>(0, 0);
    Vector3d p = T.block<3, 1>(0, 3);

    Matrix6d Ad_inv = Matrix6d::Zero();

    // Ad_{T^{-1}} = | R^T       0    |
    //               | -R^T[p]×  R^T  |
    Matrix3d R_t = R.transpose();
    Ad_inv.block<3, 3>(0, 0) = R_t;
    Ad_inv.block<3, 3>(3, 0) = -R_t * skew3(p);
    Ad_inv.block<3, 3>(3, 3) = R_t;

    return Ad_inv;
}

Matrix6d ad_twist(const Twist& twist) {
    Vector3d omega = twist.head<3>();
    Vector3d v = twist.tail<3>();

    Matrix6d ad = Matrix6d::Zero();

    // ad_V = | [ω]×   0   |
    //        | [v]×  [ω]× |
    ad.block<3, 3>(0, 0) = skew3(omega);
    ad.block<3, 3>(3, 0) = skew3(v);
    ad.block<3, 3>(3, 3) = skew3(omega);

    return ad;
}

bool is_rotation_matrix(const Matrix3d& R, double tolerance) {
    // Check R^T R = I
    Matrix3d should_be_identity = R.transpose() * R;
    double identity_error = (should_be_identity - Matrix3d::Identity()).norm();

    // Check det(R) = 1
    double det_error = std::abs(R.determinant() - 1.0);

    return (identity_error < tolerance) && (det_error < tolerance);
}

bool is_transformation_matrix(const Matrix4d& T, double tolerance) {
    // Check rotation part
    if (!is_rotation_matrix(T.block<3, 3>(0, 0), tolerance)) {
        return false;
    }

    // Check bottom row is [0 0 0 1]
    Eigen::Vector4d bottom_row = T.row(3).transpose();
    Eigen::Vector4d expected;
    expected << 0, 0, 0, 1;

    return (bottom_row - expected).norm() < tolerance;
}

Matrix3d normalize_rotation(const Matrix3d& R) {
    Eigen::JacobiSVD<Matrix3d> svd(R, Eigen::ComputeFullU | Eigen::ComputeFullV);
    Matrix3d U = svd.matrixU();
    Matrix3d V = svd.matrixV();

    // Ensure proper rotation (det = +1, not reflection)
    Matrix3d R_normalized = U * V.transpose();
    if (R_normalized.determinant() < 0) {
        U.col(2) *= -1;
        R_normalized = U * V.transpose();
    }

    return R_normalized;
}

Matrix3d rotx(double theta) {
    double c = std::cos(theta);
    double s = std::sin(theta);
    Matrix3d R;
    R << 1,  0,  0,
         0,  c, -s,
         0,  s,  c;
    return R;
}

Matrix3d roty(double theta) {
    double c = std::cos(theta);
    double s = std::sin(theta);
    Matrix3d R;
    R <<  c, 0, s,
          0, 1, 0,
         -s, 0, c;
    return R;
}

Matrix3d rotz(double theta) {
    double c = std::cos(theta);
    double s = std::sin(theta);
    Matrix3d R;
    R << c, -s, 0,
         s,  c, 0,
         0,  0, 1;
    return R;
}

}  // namespace lie
}  // namespace ur_kinematics
