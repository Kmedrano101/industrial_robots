/**
 * @file test_inverse_kinematics.cpp
 * @brief Unit tests for inverse kinematics
 */

#include <gtest/gtest.h>
#include "ur_screw_kinematics/ur_screw_kinematics.hpp"
#include <cmath>

using namespace ur_kinematics;

class InverseKinematicsTest : public ::testing::Test {
protected:
    void SetUp() override {
        params = createUR5eParameters();
    }

    RobotParameters params;
    const double tolerance = 1e-4;
};

TEST_F(InverseKinematicsTest, NewtonRaphsonConverges) {
    // Create a reachable target from a known configuration
    JointConfiguration q_target;
    q_target << 0.3, -0.8, 1.2, 0.5, -0.5, 0.2;

    Matrix4d T_target = fk(params, q_target);

    // Solve IK from nearby initial guess
    JointConfiguration q_init;
    q_init << 0.2, -0.7, 1.1, 0.4, -0.4, 0.1;

    IKSolution solution = ik_newton_raphson(params, T_target, q_init);

    EXPECT_TRUE(solution.is_valid);
    EXPECT_LT(solution.error, tolerance);
}

TEST_F(InverseKinematicsTest, LevenbergMarquardtConverges) {
    JointConfiguration q_target;
    q_target << 0.5, -1.0, 1.5, 0.2, -0.3, 0.4;

    Matrix4d T_target = fk(params, q_target);

    JointConfiguration q_init = JointConfiguration::Zero();

    IKSolution solution = ik_levenberg_marquardt(params, T_target, q_init);

    EXPECT_TRUE(solution.is_valid);
    EXPECT_LT(solution.error, tolerance);
}

TEST_F(InverseKinematicsTest, IKSolutionReproducesPose) {
    JointConfiguration q_target;
    q_target << 0.4, -0.6, 0.9, -0.3, 0.7, -0.1;

    Matrix4d T_target = fk(params, q_target);

    IKSolution solution = ik_newton_raphson(params, T_target,
                                             JointConfiguration::Zero());

    if (solution.is_valid) {
        Matrix4d T_result = fk(params, solution.joints);
        double pose_error = (T_result - T_target).norm();
        EXPECT_LT(pose_error, tolerance);
    }
}

TEST_F(InverseKinematicsTest, PoseErrorComputation) {
    Matrix4d T1 = Matrix4d::Identity();
    Matrix4d T2 = Matrix4d::Identity();
    T2(0, 3) = 0.1;  // Small translation

    Vector6d error = pose_error(T1, T2);

    // Error should be small and mostly in translation
    EXPECT_GT(error.norm(), 0);
}

TEST_F(InverseKinematicsTest, AngleNormalization) {
    JointConfiguration q;
    q << 3.5, -4.0, 7.0, -8.0, 2.5, -3.0;

    JointConfiguration q_norm = normalize_angles(q);

    for (int i = 0; i < 6; ++i) {
        EXPECT_GE(q_norm(i), -PI);
        EXPECT_LE(q_norm(i), PI);
    }
}

TEST_F(InverseKinematicsTest, JointLimitChecking) {
    JointConfiguration q_valid;
    q_valid << 0, 0, 0, 0, 0, 0;

    JointConfiguration q_invalid;
    q_invalid << 10, 0, 0, 0, 0, 0;  // Way out of limits

    EXPECT_TRUE(check_joint_limits(q_valid, params.joint_limits));
    EXPECT_FALSE(check_joint_limits(q_invalid, params.joint_limits));
}

TEST_F(InverseKinematicsTest, ClampToLimits) {
    JointConfiguration q;
    q << 10, -10, 5, -5, 3, -3;

    JointConfiguration q_clamped = clamp_to_limits(q, params.joint_limits);

    EXPECT_TRUE(check_joint_limits(q_clamped, params.joint_limits));
}

int main(int argc, char **argv) {
    testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
