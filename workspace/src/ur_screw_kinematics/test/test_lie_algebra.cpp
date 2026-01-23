/**
 * @file test_lie_algebra.cpp
 * @brief Unit tests for Lie algebra operations
 */

#include <gtest/gtest.h>
#include "ur_screw_kinematics/lie_algebra.hpp"
#include <cmath>

using namespace ur_kinematics;
using namespace ur_kinematics::lie;

class LieAlgebraTest : public ::testing::Test {
protected:
    void SetUp() override {}
    const double tolerance = 1e-10;
};

TEST_F(LieAlgebraTest, Skew3BasicOperation) {
    Vector3d v(1, 2, 3);
    Matrix3d skew = skew3(v);

    EXPECT_NEAR(skew(0, 1), -3, tolerance);
    EXPECT_NEAR(skew(0, 2), 2, tolerance);
    EXPECT_NEAR(skew(1, 0), 3, tolerance);
    EXPECT_NEAR(skew(1, 2), -1, tolerance);
    EXPECT_NEAR(skew(2, 0), -2, tolerance);
    EXPECT_NEAR(skew(2, 1), 1, tolerance);

    // Diagonal should be zero
    EXPECT_NEAR(skew(0, 0), 0, tolerance);
    EXPECT_NEAR(skew(1, 1), 0, tolerance);
    EXPECT_NEAR(skew(2, 2), 0, tolerance);
}

TEST_F(LieAlgebraTest, Skew3Antisymmetric) {
    Vector3d v(1, 2, 3);
    Matrix3d skew = skew3(v);

    // Check antisymmetry: skew^T = -skew
    Matrix3d sum = skew + skew.transpose();
    EXPECT_NEAR(sum.norm(), 0, tolerance);
}

TEST_F(LieAlgebraTest, Unskew3Inverse) {
    Vector3d v(1.5, -2.3, 0.7);
    Matrix3d skew = skew3(v);
    Vector3d v_recovered = unskew3(skew);

    EXPECT_NEAR((v - v_recovered).norm(), 0, tolerance);
}

TEST_F(LieAlgebraTest, RodriguesIdentityAtZero) {
    Vector3d omega_hat(1, 0, 0);
    Matrix3d R = rodrigues(omega_hat, 0);

    EXPECT_TRUE(R.isApprox(Matrix3d::Identity(), tolerance));
}

TEST_F(LieAlgebraTest, RodriguesRotationAboutZ) {
    Vector3d omega_hat(0, 0, 1);
    double theta = PI / 2;
    Matrix3d R = rodrigues(omega_hat, theta);

    // 90 degree rotation about Z should map x to y
    Vector3d x(1, 0, 0);
    Vector3d result = R * x;

    EXPECT_NEAR(result(0), 0, tolerance);
    EXPECT_NEAR(result(1), 1, tolerance);
    EXPECT_NEAR(result(2), 0, tolerance);
}

TEST_F(LieAlgebraTest, RodriguesIsRotationMatrix) {
    Vector3d omega_hat = Vector3d(1, 2, 3).normalized();
    double theta = 1.2;
    Matrix3d R = rodrigues(omega_hat, theta);

    EXPECT_TRUE(is_rotation_matrix(R, tolerance));
}

TEST_F(LieAlgebraTest, ExpSo3LogSo3Inverse) {
    Vector3d omega(0.5, -0.3, 0.8);
    Matrix3d R = exp_so3(omega);
    Vector3d omega_recovered = log_so3(R);

    EXPECT_NEAR((omega - omega_recovered).norm(), 0, tolerance);
}

TEST_F(LieAlgebraTest, ExpScrewIdentityAtZero) {
    ScrewAxis S;
    S << 0, 0, 1, 0, 0, 0;
    Matrix4d T = exp_screw(S, 0);

    EXPECT_TRUE(T.isApprox(Matrix4d::Identity(), tolerance));
}

TEST_F(LieAlgebraTest, ExpScrewPureRotation) {
    ScrewAxis S;
    S << 0, 0, 1, 0, 0, 0;  // Rotation about Z
    double theta = PI / 4;
    Matrix4d T = exp_screw(S, theta);

    // Check rotation part
    EXPECT_TRUE(is_rotation_matrix(T.block<3, 3>(0, 0), tolerance));

    // Translation should be zero
    Vector3d translation = T.block<3, 1>(0, 3);
    EXPECT_NEAR(translation.norm(), 0, tolerance);
}

TEST_F(LieAlgebraTest, ExpScrewPureTranslation) {
    ScrewAxis S;
    S << 0, 0, 0, 1, 0, 0;  // Translation along X
    double theta = 2.5;
    Matrix4d T = exp_screw(S, theta);

    // Rotation should be identity
    Matrix3d rotation = T.block<3, 3>(0, 0);
    EXPECT_TRUE(rotation.isApprox(Matrix3d::Identity(), tolerance));

    // Translation should be [2.5, 0, 0]
    EXPECT_NEAR(T(0, 3), 2.5, tolerance);
    EXPECT_NEAR(T(1, 3), 0, tolerance);
    EXPECT_NEAR(T(2, 3), 0, tolerance);
}

TEST_F(LieAlgebraTest, AdjointTransformation) {
    Matrix4d T = Matrix4d::Identity();
    T.block<3, 3>(0, 0) = rotz(PI / 4);
    T(0, 3) = 1.0;
    T(1, 3) = 2.0;
    T(2, 3) = 3.0;

    Matrix6d Ad = adjoint(T);

    // Adjoint should be 6x6
    EXPECT_EQ(Ad.rows(), 6);
    EXPECT_EQ(Ad.cols(), 6);
}

TEST_F(LieAlgebraTest, RotationMatrixFunctions) {
    double theta = PI / 6;

    Matrix3d Rx = rotx(theta);
    Matrix3d Ry = roty(theta);
    Matrix3d Rz = rotz(theta);

    EXPECT_TRUE(is_rotation_matrix(Rx, tolerance));
    EXPECT_TRUE(is_rotation_matrix(Ry, tolerance));
    EXPECT_TRUE(is_rotation_matrix(Rz, tolerance));
}

int main(int argc, char **argv) {
    testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
