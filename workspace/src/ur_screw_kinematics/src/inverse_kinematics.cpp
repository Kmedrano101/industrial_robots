/**
 * @file inverse_kinematics.cpp
 * @brief Implementation of inverse kinematics solvers
 */

#include "ur_screw_kinematics/inverse_kinematics.hpp"
#include "ur_screw_kinematics/forward_kinematics.hpp"
#include "ur_screw_kinematics/jacobian.hpp"
#include "ur_screw_kinematics/lie_algebra.hpp"
#include <cmath>
#include <algorithm>

namespace ur_kinematics {

// ============================================================================
// Paden-Kahan Subproblems
// ============================================================================

double subproblem1(
    const Vector3d& omega_hat,
    const Vector3d& p,
    const Vector3d& q,
    const Vector3d& r) {

    // Project p and q onto plane perpendicular to omega
    Vector3d u = p - r;
    Vector3d v = q - r;

    // Remove component along omega
    Vector3d u_prime = u - omega_hat.dot(u) * omega_hat;
    Vector3d v_prime = v - omega_hat.dot(v) * omega_hat;

    double u_prime_norm = u_prime.norm();
    double v_prime_norm = v_prime.norm();

    if (u_prime_norm < EPSILON || v_prime_norm < EPSILON) {
        // Point on axis
        return 0.0;
    }

    // Normalize
    u_prime /= u_prime_norm;
    v_prime /= v_prime_norm;

    // Compute angle using atan2 for correct quadrant
    double cos_theta = u_prime.dot(v_prime);
    double sin_theta = omega_hat.dot(u_prime.cross(v_prime));

    return std::atan2(sin_theta, cos_theta);
}

int subproblem2(
    const Vector3d& omega1_hat,
    const Vector3d& omega2_hat,
    const Vector3d& p,
    const Vector3d& q,
    const Vector3d& r,
    std::vector<double>& theta1,
    std::vector<double>& theta2) {

    theta1.clear();
    theta2.clear();

    Vector3d u = p - r;
    Vector3d v = q - r;

    // Check if axes are parallel
    double omega1_dot_omega2 = omega1_hat.dot(omega2_hat);
    if (std::abs(std::abs(omega1_dot_omega2) - 1.0) < EPSILON) {
        // Parallel axes - degenerate case
        return 0;
    }

    // Solve for intersection point c on the circle
    // c = α·ω1 + β·ω2 + γ·(ω1 × ω2)
    double denom = 1.0 - omega1_dot_omega2 * omega1_dot_omega2;

    double alpha = (omega1_hat.dot(u) - omega1_dot_omega2 * omega2_hat.dot(v)) / denom;
    double beta = (omega2_hat.dot(v) - omega1_dot_omega2 * omega1_hat.dot(u)) / denom;

    Vector3d omega_cross = omega1_hat.cross(omega2_hat);

    // Compute discriminant for gamma
    double gamma_sq = (u.squaredNorm() - alpha * alpha - beta * beta -
                       2 * alpha * beta * omega1_dot_omega2) /
                      omega_cross.squaredNorm();

    if (gamma_sq < -EPSILON) {
        // No solution
        return 0;
    }

    if (gamma_sq < EPSILON) {
        // One solution
        Vector3d c = alpha * omega1_hat + beta * omega2_hat + r;

        theta2.push_back(subproblem1(omega2_hat, p, c, r));
        theta1.push_back(subproblem1(omega1_hat, c, q, r));
        return 1;
    }

    // Two solutions
    double gamma = std::sqrt(gamma_sq);

    Vector3d c1 = alpha * omega1_hat + beta * omega2_hat + gamma * omega_cross + r;
    Vector3d c2 = alpha * omega1_hat + beta * omega2_hat - gamma * omega_cross + r;

    theta2.push_back(subproblem1(omega2_hat, p, c1, r));
    theta1.push_back(subproblem1(omega1_hat, c1, q, r));

    theta2.push_back(subproblem1(omega2_hat, p, c2, r));
    theta1.push_back(subproblem1(omega1_hat, c2, q, r));

    return 2;
}

int subproblem3(
    const Vector3d& omega_hat,
    const Vector3d& p,
    const Vector3d& q,
    const Vector3d& r,
    double d,
    std::vector<double>& theta) {

    theta.clear();

    Vector3d u = p - r;
    Vector3d v = q - r;

    // Project onto plane perpendicular to omega
    Vector3d u_prime = u - omega_hat.dot(u) * omega_hat;
    Vector3d v_prime = v - omega_hat.dot(v) * omega_hat;

    double u_prime_norm = u_prime.norm();
    double v_prime_norm = v_prime.norm();

    if (u_prime_norm < EPSILON) {
        // p is on axis
        return 0;
    }

    // Height difference along omega
    double delta = omega_hat.dot(p - q);

    // Radius of circle traced by p
    double d_prime_sq = d * d - delta * delta;

    if (d_prime_sq < -EPSILON) {
        // No solution (target too far in omega direction)
        return 0;
    }

    double d_prime = std::sqrt(std::max(0.0, d_prime_sq));

    // Solve using law of cosines
    // ||u' - Rθ·v'|| = d' where Rθ is rotation about omega
    double cos_phi = (u_prime_norm * u_prime_norm + v_prime_norm * v_prime_norm -
                      d_prime * d_prime) /
                     (2.0 * u_prime_norm * v_prime_norm);

    if (std::abs(cos_phi) > 1.0 + EPSILON) {
        return 0;
    }

    cos_phi = std::max(-1.0, std::min(1.0, cos_phi));
    double phi = std::acos(cos_phi);

    // Base angle from u' to v'
    double theta0 = subproblem1(omega_hat, u, v, r);

    if (std::abs(phi) < EPSILON) {
        theta.push_back(theta0);
        return 1;
    }

    theta.push_back(theta0 + phi);
    theta.push_back(theta0 - phi);
    return 2;
}

int subproblem4(
    const Vector3d& omega_hat,
    const Vector3d& omega1_hat,
    const Vector3d& p,
    const Vector3d& r,
    double d,
    std::vector<double>& theta) {

    theta.clear();

    Vector3d u = p - r;

    // Project u onto plane perpendicular to omega1
    Vector3d u_prime = u - omega1_hat.dot(u) * omega1_hat;

    double u_prime_norm = u_prime.norm();
    if (u_prime_norm < EPSILON) {
        return 0;
    }

    // The projection value after rotation is:
    // omega^T · (r + R_theta · u) = d
    // omega^T · r + omega^T · R_theta · u = d

    double c0 = omega_hat.dot(r);
    double c1 = omega_hat.dot(u) - omega_hat.dot(omega1_hat) * omega1_hat.dot(u);

    // After rotation by theta: projection = c0 + c1*cos(theta) + c2*sin(theta) = d
    Vector3d v = omega1_hat.cross(u);
    double c2 = omega_hat.dot(v);

    // Solve: c1*cos(theta) + c2*sin(theta) = d - c0
    double rhs = d - c0;
    double A = std::sqrt(c1 * c1 + c2 * c2);

    if (A < EPSILON) {
        return 0;
    }

    double ratio = rhs / A;

    if (std::abs(ratio) > 1.0 + EPSILON) {
        return 0;
    }

    ratio = std::max(-1.0, std::min(1.0, ratio));

    double phi = std::atan2(c2, c1);
    double alpha = std::acos(ratio);

    if (std::abs(alpha) < EPSILON) {
        theta.push_back(phi);
        return 1;
    }

    theta.push_back(phi + alpha);
    theta.push_back(phi - alpha);
    return 2;
}

// ============================================================================
// Inverse Kinematics Solvers
// ============================================================================

Vector6d pose_error(const Matrix4d& T_current, const Matrix4d& T_target) {
    // Compute error in body frame: V_b = log(T_current^{-1} · T_target)
    Matrix4d T_error = Matrix4d::Identity();
    Matrix3d R_c = T_current.block<3, 3>(0, 0);
    Vector3d p_c = T_current.block<3, 1>(0, 3);

    Matrix3d R_t = T_target.block<3, 3>(0, 0);
    Vector3d p_t = T_target.block<3, 1>(0, 3);

    // T_current^{-1} · T_target
    T_error.block<3, 3>(0, 0) = R_c.transpose() * R_t;
    T_error.block<3, 1>(0, 3) = R_c.transpose() * (p_t - p_c);

    return lie::log_se3(T_error);
}

IKSolution ik_newton_raphson(
    const RobotParameters& params,
    const Matrix4d& T_target,
    const JointConfiguration& theta_init,
    double tolerance,
    int max_iterations) {

    IKSolution result;
    result.method = "newton_raphson";
    result.joints = theta_init;

    JointConfiguration theta = theta_init;

    for (int iter = 0; iter < max_iterations; ++iter) {
        // Compute current pose
        Matrix4d T_current = fk_space_frame(
            params.screw_axes_space, params.M_home, theta);

        // Compute error
        Vector6d error = pose_error(T_current, T_target);
        double error_norm = error.norm();

        if (error_norm < tolerance) {
            result.joints = normalize_angles(theta);
            result.is_valid = true;
            result.error = error_norm;
            result.iterations = iter + 1;
            return result;
        }

        // Compute body Jacobian
        auto J_b = jacobian_body(params.screw_axes_body, theta);

        // Update: Δθ = J_b^{-1} · V_b
        JointConfiguration delta_theta = jacobian_damped_inverse(J_b, 0.01) * error;

        theta += delta_theta;
    }

    result.joints = normalize_angles(theta);
    result.is_valid = false;
    result.error = pose_error(fk(params, theta), T_target).norm();
    result.iterations = max_iterations;

    return result;
}

IKSolution ik_levenberg_marquardt(
    const RobotParameters& params,
    const Matrix4d& T_target,
    const JointConfiguration& theta_init,
    double tolerance,
    int max_iterations) {

    IKSolution result;
    result.method = "levenberg_marquardt";
    result.joints = theta_init;

    JointConfiguration theta = theta_init;
    double lambda = 0.01;  // Damping parameter
    double lambda_factor = 10.0;

    double prev_error = std::numeric_limits<double>::max();

    for (int iter = 0; iter < max_iterations; ++iter) {
        Matrix4d T_current = fk_space_frame(
            params.screw_axes_space, params.M_home, theta);

        Vector6d error = pose_error(T_current, T_target);
        double error_norm = error.norm();

        if (error_norm < tolerance) {
            result.joints = normalize_angles(theta);
            result.is_valid = true;
            result.error = error_norm;
            result.iterations = iter + 1;
            return result;
        }

        // Compute Jacobian
        auto J_b = jacobian_body(params.screw_axes_body, theta);

        // Levenberg-Marquardt update
        Eigen::Matrix<double, 6, 6> JtJ = J_b.transpose() * J_b;
        Eigen::Matrix<double, 6, 6> damped = JtJ +
            lambda * Eigen::Matrix<double, 6, 6>::Identity();

        JointConfiguration delta_theta = damped.ldlt().solve(J_b.transpose() * error);

        // Try the update
        JointConfiguration theta_new = theta + delta_theta;
        Matrix4d T_new = fk(params, theta_new);
        double new_error = pose_error(T_new, T_target).norm();

        if (new_error < prev_error) {
            // Accept update, decrease damping
            theta = theta_new;
            lambda /= lambda_factor;
            prev_error = new_error;
        } else {
            // Reject update, increase damping
            lambda *= lambda_factor;
        }
    }

    result.joints = normalize_angles(theta);
    result.is_valid = false;
    result.error = pose_error(fk(params, theta), T_target).norm();
    result.iterations = max_iterations;

    return result;
}

IKSolutions ik_analytical(
    const RobotParameters& params,
    const Matrix4d& T_target) {

    IKSolutions results;

    // UR robots have a specific structure that allows analytical solution
    // The approach uses geometric decomposition and Paden-Kahan subproblems

    // For a 6R robot with the UR structure (3 parallel axes for wrist):
    // 1. Solve for wrist center position (joints 1-3)
    // 2. Solve for wrist orientation (joints 4-6)

    // Extract target position and orientation
    Vector3d p_target = T_target.block<3, 1>(0, 3);
    Matrix3d R_target = T_target.block<3, 3>(0, 0);

    // UR robot dimensions from params
    double d1 = params.d[0];  // Base height
    double a2 = std::abs(params.a[1]);  // Upper arm length
    double a3 = std::abs(params.a[2]);  // Forearm length
    double d4 = params.d[3];  // Wrist 1 offset
    double d5 = params.d[4];  // Wrist 2 offset
    double d6 = params.d[5];  // Tool offset

    // Wrist center position (accounting for tool offset)
    Vector3d z_target = R_target.col(2);
    Vector3d p_wc = p_target - d6 * z_target;

    // Solve for theta1 (base rotation)
    // Two solutions: shoulder left and shoulder right
    std::vector<double> theta1_solutions;

    double r = std::sqrt(p_wc(0) * p_wc(0) + p_wc(1) * p_wc(1));

    if (r < EPSILON) {
        theta1_solutions.push_back(0.0);  // Singular configuration
    } else {
        double alpha = std::atan2(p_wc(1), p_wc(0));
        double d4_ratio = d4 / r;

        if (std::abs(d4_ratio) <= 1.0) {
            double beta = std::acos(std::max(-1.0, std::min(1.0, d4_ratio)));
            theta1_solutions.push_back(alpha + beta + PI / 2);
            theta1_solutions.push_back(alpha - beta + PI / 2);
        } else {
            // No solution
            return results;
        }
    }

    // For each theta1 solution
    for (double theta1 : theta1_solutions) {
        // Solve for theta5 (wrist 2)
        // theta5 determines elbow up/down configuration

        Vector3d p1;  // Wrist center in frame 1
        double c1 = std::cos(theta1);
        double s1 = std::sin(theta1);

        p1(0) = c1 * p_wc(0) + s1 * p_wc(1);
        p1(1) = -s1 * p_wc(0) + c1 * p_wc(1);
        p1(2) = p_wc(2);

        // Solve for theta5
        double arg5 = (p1(0) - d4) / d6;
        arg5 = std::max(-1.0, std::min(1.0, arg5));

        std::vector<double> theta5_solutions;
        double theta5_base = std::acos(arg5);
        theta5_solutions.push_back(theta5_base);
        theta5_solutions.push_back(-theta5_base);

        for (double theta5 : theta5_solutions) {
            if (std::abs(std::sin(theta5)) < EPSILON) {
                // Wrist singularity - theta4 and theta6 are coupled
                continue;
            }

            // Solve for theta6
            Vector3d x_target = R_target.col(0);
            Vector3d y_target = R_target.col(1);

            double s5 = std::sin(theta5);
            double theta6 = std::atan2(
                (-s1 * x_target(0) + c1 * x_target(1)) / s5,
                (s1 * y_target(0) - c1 * y_target(1)) / s5);

            // Solve for theta2 and theta3 using subproblem 3 (elbow)
            // This is the 2R planar arm problem

            double px = p1(0) - d5 * std::sin(theta5);
            double py = p1(2) - d1;

            double c = std::sqrt(px * px + py * py);

            double cos_theta3 = (c * c - a2 * a2 - a3 * a3) / (2 * a2 * a3);

            if (std::abs(cos_theta3) > 1.0 + EPSILON) {
                continue;  // Target out of reach
            }

            cos_theta3 = std::max(-1.0, std::min(1.0, cos_theta3));

            // Two solutions: elbow up and elbow down
            std::vector<double> theta3_solutions;
            theta3_solutions.push_back(std::acos(cos_theta3));
            theta3_solutions.push_back(-std::acos(cos_theta3));

            for (double theta3 : theta3_solutions) {
                double s3 = std::sin(theta3);
                double c3 = std::cos(theta3);

                double k1 = a2 + a3 * c3;
                double k2 = a3 * s3;

                double theta2 = std::atan2(py, px) - std::atan2(k2, k1);

                // Solve for theta4
                double c23 = std::cos(theta2 + theta3);
                double s23 = std::sin(theta2 + theta3);

                double theta4 = std::atan2(
                    -z_target(0) * s1 + z_target(1) * c1,
                    z_target(0) * c1 * c23 + z_target(1) * s1 * c23 - z_target(2) * s23);

                // Create solution
                IKSolution sol;
                sol.joints << theta1, theta2, theta3, theta4, theta5, theta6;
                sol.joints = normalize_angles(sol.joints);

                // Verify solution
                Matrix4d T_check = fk(params, sol.joints);
                Vector6d err = pose_error(T_check, T_target);
                sol.error = err.norm();
                sol.is_valid = (sol.error < 1e-3);
                sol.method = "analytical";
                sol.iterations = 0;

                if (sol.is_valid) {
                    results.solutions.push_back(sol);
                }
            }
        }
    }

    return results;
}

IKSolutions ik_with_limits(
    const RobotParameters& params,
    const Matrix4d& T_target,
    const std::string& method,
    const JointConfiguration& theta_init) {

    IKSolutions all_solutions;

    if (method == "analytical") {
        all_solutions = ik_analytical(params, T_target);
    } else {
        IKSolution sol;
        if (method == "newton") {
            sol = ik_newton_raphson(params, T_target, theta_init);
        } else {
            sol = ik_levenberg_marquardt(params, T_target, theta_init);
        }
        all_solutions.solutions.push_back(sol);
    }

    // Filter by joint limits
    IKSolutions filtered;
    for (const auto& sol : all_solutions.solutions) {
        if (sol.is_valid && check_joint_limits(sol.joints, params.joint_limits)) {
            filtered.solutions.push_back(sol);
        }
    }

    return filtered;
}

IKSolution ik_position_only(
    const RobotParameters& params,
    const Vector3d& target_position,
    const JointConfiguration& theta_init) {

    IKSolution result;
    result.method = "position_only";

    JointConfiguration theta = theta_init;
    double tolerance = 1e-6;

    for (int iter = 0; iter < MAX_IK_ITERATIONS; ++iter) {
        Vector3d current_pos = fk_position(params, theta);
        Vector3d error = target_position - current_pos;

        if (error.norm() < tolerance) {
            result.joints = normalize_angles(theta);
            result.is_valid = true;
            result.error = error.norm();
            result.iterations = iter + 1;
            return result;
        }

        // Use only position part of Jacobian (rows 4-6)
        auto J = jacobian_space(params.screw_axes_space, theta);
        Eigen::Matrix<double, 3, 6> J_pos = J.block<3, 6>(3, 0);

        // Damped pseudoinverse
        Eigen::Matrix<double, 3, 3> JJT = J_pos * J_pos.transpose() +
            0.01 * Eigen::Matrix3d::Identity();
        JointConfiguration delta_theta = J_pos.transpose() * JJT.ldlt().solve(error);

        theta += delta_theta;
    }

    result.joints = normalize_angles(theta);
    result.is_valid = false;
    result.error = (target_position - fk_position(params, theta)).norm();
    result.iterations = MAX_IK_ITERATIONS;

    return result;
}

JointConfiguration normalize_angles(const JointConfiguration& theta) {
    JointConfiguration result;
    for (int i = 0; i < 6; ++i) {
        double angle = std::fmod(theta(i) + PI, 2 * PI);
        if (angle < 0) angle += 2 * PI;
        result(i) = angle - PI;
    }
    return result;
}

JointConfiguration normalize_angles_positive(const JointConfiguration& theta) {
    JointConfiguration result;
    for (int i = 0; i < 6; ++i) {
        double angle = std::fmod(theta(i), 2 * PI);
        if (angle < 0) angle += 2 * PI;
        result(i) = angle;
    }
    return result;
}

bool check_joint_limits(
    const JointConfiguration& theta,
    const std::vector<std::pair<double, double>>& limits) {

    if (limits.size() != 6) return true;  // No limits defined

    for (int i = 0; i < 6; ++i) {
        if (theta(i) < limits[i].first || theta(i) > limits[i].second) {
            return false;
        }
    }
    return true;
}

JointConfiguration clamp_to_limits(
    const JointConfiguration& theta,
    const std::vector<std::pair<double, double>>& limits) {

    JointConfiguration result = theta;

    if (limits.size() != 6) return result;

    for (int i = 0; i < 6; ++i) {
        result(i) = std::max(limits[i].first, std::min(limits[i].second, theta(i)));
    }

    return result;
}

IKSolution IKSolutions::nearestTo(const JointConfiguration& ref) const {
    if (solutions.empty()) {
        return IKSolution();
    }

    const IKSolution* nearest = nullptr;
    double min_dist = std::numeric_limits<double>::max();

    for (const auto& sol : solutions) {
        if (!sol.is_valid) continue;

        double dist = (sol.joints - ref).norm();
        if (dist < min_dist) {
            min_dist = dist;
            nearest = &sol;
        }
    }

    return nearest ? *nearest : IKSolution();
}

}  // namespace ur_kinematics
