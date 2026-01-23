/**
 * @file forward_kinematics.cpp
 * @brief Implementation of forward kinematics using Product of Exponentials
 */

#include "ur_screw_kinematics/forward_kinematics.hpp"

namespace ur_kinematics {

Matrix4d fk_space_frame(
    const std::vector<ScrewAxis>& screw_axes,
    const Matrix4d& M_home,
    const JointConfiguration& joint_angles) {

    // T(θ) = e^{[S₁]θ₁} · e^{[S₂]θ₂} · ... · e^{[Sₙ]θₙ} · M
    Matrix4d T = Matrix4d::Identity();

    for (size_t i = 0; i < screw_axes.size(); ++i) {
        T = T * lie::exp_screw(screw_axes[i], joint_angles(i));
    }

    return T * M_home;
}

Matrix4d fk_body_frame(
    const std::vector<ScrewAxis>& screw_axes,
    const Matrix4d& M_home,
    const JointConfiguration& joint_angles) {

    // T(θ) = M · e^{[B₁]θ₁} · e^{[B₂]θ₂} · ... · e^{[Bₙ]θₙ}
    Matrix4d T = M_home;

    for (size_t i = 0; i < screw_axes.size(); ++i) {
        T = T * lie::exp_screw(screw_axes[i], joint_angles(i));
    }

    return T;
}

FKResult fk_with_joint_transforms(
    const std::vector<ScrewAxis>& screw_axes,
    const Matrix4d& M_home,
    const JointConfiguration& joint_angles) {

    FKResult result;
    result.joint_transforms.resize(screw_axes.size());

    Matrix4d T = Matrix4d::Identity();

    for (size_t i = 0; i < screw_axes.size(); ++i) {
        T = T * lie::exp_screw(screw_axes[i], joint_angles(i));
        result.joint_transforms[i] = Transform(T);
    }

    result.end_effector_pose = Transform(T * M_home);
    result.is_valid = true;

    return result;
}

Matrix4d fk(
    const RobotParameters& params,
    const JointConfiguration& joint_angles,
    bool use_space_frame) {

    if (use_space_frame) {
        return fk_space_frame(
            params.screw_axes_space,
            params.M_home,
            joint_angles);
    } else {
        return fk_body_frame(
            params.screw_axes_body,
            params.M_home,
            joint_angles);
    }
}

Vector3d fk_position(
    const RobotParameters& params,
    const JointConfiguration& joint_angles) {

    Matrix4d T = fk(params, joint_angles, true);
    return T.block<3, 1>(0, 3);
}

Matrix3d fk_orientation(
    const RobotParameters& params,
    const JointConfiguration& joint_angles) {

    Matrix4d T = fk(params, joint_angles, true);
    return T.block<3, 3>(0, 0);
}

std::vector<ScrewAxis> space_to_body_screws(
    const std::vector<ScrewAxis>& screw_axes_space,
    const Matrix4d& M_home) {

    // B_i = Ad_{M^{-1}} · S_i
    Matrix4d M_inv = Matrix4d::Identity();
    Matrix3d R = M_home.block<3, 3>(0, 0);
    Vector3d p = M_home.block<3, 1>(0, 3);

    M_inv.block<3, 3>(0, 0) = R.transpose();
    M_inv.block<3, 1>(0, 3) = -R.transpose() * p;

    Matrix6d Ad_M_inv = lie::adjoint(M_inv);

    std::vector<ScrewAxis> screw_axes_body(screw_axes_space.size());
    for (size_t i = 0; i < screw_axes_space.size(); ++i) {
        screw_axes_body[i] = Ad_M_inv * screw_axes_space[i];
    }

    return screw_axes_body;
}

std::vector<ScrewAxis> body_to_space_screws(
    const std::vector<ScrewAxis>& screw_axes_body,
    const Matrix4d& M_home) {

    // S_i = Ad_M · B_i
    Matrix6d Ad_M = lie::adjoint(M_home);

    std::vector<ScrewAxis> screw_axes_space(screw_axes_body.size());
    for (size_t i = 0; i < screw_axes_body.size(); ++i) {
        screw_axes_space[i] = Ad_M * screw_axes_body[i];
    }

    return screw_axes_space;
}

}  // namespace ur_kinematics
