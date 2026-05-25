/**
 * @file test_forward_kinematics.cpp
 * @brief Unit tests for forward kinematics
 */

#include <gtest/gtest.h>
#include "ur_screw_kinematics/ur_screw_kinematics.hpp"
#include <cmath>

using namespace ur_kinematics;

class ForwardKinematicsTest : public ::testing::Test {
protected:
    void SetUp() override {
        params = createUR5eParameters();
    }

    RobotParameters params;
    const double tolerance = 1e-6;
};

TEST_F(ForwardKinematicsTest, HomeConfiguration) {
    JointConfiguration q = JointConfiguration::Zero();
    Matrix4d T = fk(params, q);

    // At home configuration, FK should return M_home
    EXPECT_TRUE(T.isApprox(params.M_home, tolerance));
}

TEST_F(ForwardKinematicsTest, SpaceAndBodyFrameConsistent) {
    JointConfiguration q;
    q << 0.1, -0.5, 0.3, 0.2, -0.4, 0.6;

    Matrix4d T_space = fk_space_frame(
        params.screw_axes_space, params.M_home, q);
    Matrix4d T_body = fk_body_frame(
        params.screw_axes_body, params.M_home, q);

    EXPECT_TRUE(T_space.isApprox(T_body, tolerance));
}

TEST_F(ForwardKinematicsTest, IsValidTransformation) {
    JointConfiguration q;
    q << 0.5, -1.0, 1.5, 0.0, 1.2, -0.3;

    Matrix4d T = fk(params, q);

    EXPECT_TRUE(lie::is_transformation_matrix(T, tolerance));
}

TEST_F(ForwardKinematicsTest, FKWithJointTransforms) {
    JointConfiguration q;
    q << 0.1, -0.2, 0.3, 0.1, -0.1, 0.2;

    FKResult result = fk_with_joint_transforms(
        params.screw_axes_space, params.M_home, q);

    EXPECT_TRUE(result.is_valid);
    EXPECT_EQ(result.joint_transforms.size(), 6u);

    // End-effector should match standard FK
    Matrix4d T_expected = fk(params, q);
    EXPECT_TRUE(result.end_effector_pose.matrix.isApprox(T_expected, tolerance));
}

TEST_F(ForwardKinematicsTest, PositionAndOrientation) {
    JointConfiguration q;
    q << 0.5, -1.0, 1.5, 0.0, 1.2, -0.3;

    Matrix4d T = fk(params, q);
    Vector3d pos = fk_position(params, q);
    Matrix3d ori = fk_orientation(params, q);

    EXPECT_TRUE(pos.isApprox(T.block<3, 1>(0, 3), tolerance));
    EXPECT_TRUE(ori.isApprox(T.block<3, 3>(0, 0), tolerance));
}

TEST_F(ForwardKinematicsTest, ScrewConversion) {
    // Convert space to body and back
    auto body_screws = space_to_body_screws(
        params.screw_axes_space, params.M_home);
    auto space_screws_recovered = body_to_space_screws(
        body_screws, params.M_home);

    for (size_t i = 0; i < 6; ++i) {
        EXPECT_TRUE(params.screw_axes_space[i].isApprox(
            space_screws_recovered[i], tolerance));
    }
}

int main(int argc, char **argv) {
    testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
