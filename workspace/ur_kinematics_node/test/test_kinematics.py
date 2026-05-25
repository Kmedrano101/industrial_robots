#!/usr/bin/env python3
"""
Unit tests for UR Kinematics Python implementation
"""

import pytest
import numpy as np
from ur_kinematics_node.robot_parameters import (
    load_robot_parameters,
    create_ur5e_parameters,
    get_supported_models,
)
from ur_kinematics_node.screw_kinematics import URScrewKinematics, IKSolution


class TestRobotParameters:
    """Tests for robot parameter loading."""

    def test_load_ur5e(self):
        params = load_robot_parameters('ur5e')
        assert params.model_name == 'ur5e'
        assert params.num_joints == 6

    def test_supported_models(self):
        models = get_supported_models()
        assert 'ur5e' in models
        assert 'ur3e' in models
        assert 'ur10e' in models

    def test_dh_parameters_shape(self):
        params = create_ur5e_parameters()
        assert len(params.a) == 6
        assert len(params.d) == 6
        assert len(params.alpha) == 6

    def test_screw_axes_shape(self):
        params = create_ur5e_parameters()
        assert params.screw_axes_space.shape == (6, 6)
        assert params.screw_axes_body.shape == (6, 6)


class TestLieAlgebra:
    """Tests for Lie algebra operations."""

    def test_skew3(self):
        v = np.array([1, 2, 3])
        skew = URScrewKinematics.skew3(v)

        # Check antisymmetry
        assert np.allclose(skew + skew.T, np.zeros((3, 3)))

        # Check values
        assert skew[0, 1] == -3
        assert skew[0, 2] == 2
        assert skew[1, 2] == -1

    def test_rodrigues_identity(self):
        omega = np.array([0, 0, 1])
        R = URScrewKinematics.rodrigues(omega, 0)
        assert np.allclose(R, np.eye(3))

    def test_rodrigues_90_degrees(self):
        omega = np.array([0, 0, 1])
        R = URScrewKinematics.rodrigues(omega, np.pi / 2)

        # Should rotate x to y
        x = np.array([1, 0, 0])
        result = R @ x
        expected = np.array([0, 1, 0])
        assert np.allclose(result, expected, atol=1e-10)

    def test_exp_so3_log_so3_inverse(self):
        omega = np.array([0.5, -0.3, 0.8])
        R = URScrewKinematics.exp_so3(omega)
        omega_recovered = URScrewKinematics.log_so3(R)
        assert np.allclose(omega, omega_recovered, atol=1e-10)


class TestForwardKinematics:
    """Tests for forward kinematics."""

    @pytest.fixture
    def kinematics(self):
        params = create_ur5e_parameters()
        return URScrewKinematics(params)

    def test_home_configuration(self, kinematics):
        q = np.zeros(6)
        T = kinematics.fk(q)
        assert np.allclose(T, kinematics.M_home, atol=1e-10)

    def test_space_body_consistency(self, kinematics):
        q = np.array([0.1, -0.5, 0.3, 0.2, -0.4, 0.6])
        T_space = kinematics.fk_space_frame(q)
        T_body = kinematics.fk_body_frame(q)
        assert np.allclose(T_space, T_body, atol=1e-10)

    def test_fk_is_se3(self, kinematics):
        q = np.array([0.5, -1.0, 1.5, 0.0, 1.2, -0.3])
        T = kinematics.fk(q)

        # Check rotation part
        R = T[:3, :3]
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-10)
        assert np.abs(np.linalg.det(R) - 1.0) < 1e-10

        # Check bottom row
        assert np.allclose(T[3, :], [0, 0, 0, 1])


class TestJacobian:
    """Tests for Jacobian computation."""

    @pytest.fixture
    def kinematics(self):
        params = create_ur5e_parameters()
        return URScrewKinematics(params)

    def test_jacobian_shape(self, kinematics):
        q = np.zeros(6)
        J = kinematics.jacobian(q)
        assert J.shape == (6, 6)

    def test_manipulability(self, kinematics):
        q = np.zeros(6)
        J = kinematics.jacobian(q)
        w = kinematics.manipulability(J)
        assert w >= 0


class TestInverseKinematics:
    """Tests for inverse kinematics."""

    @pytest.fixture
    def kinematics(self):
        params = create_ur5e_parameters()
        return URScrewKinematics(params)

    def test_ik_newton_converges(self, kinematics):
        # Create reachable target
        q_target = np.array([0.3, -0.8, 1.2, 0.5, -0.5, 0.2])
        T_target = kinematics.fk(q_target)

        # Solve from nearby guess
        q_init = np.array([0.2, -0.7, 1.1, 0.4, -0.4, 0.1])
        solution = kinematics.ik_newton_raphson(T_target, q_init)

        assert solution.is_valid
        assert solution.error < 1e-4

    def test_ik_lm_converges(self, kinematics):
        q_target = np.array([0.5, -1.0, 1.5, 0.2, -0.3, 0.4])
        T_target = kinematics.fk(q_target)

        solution = kinematics.ik_levenberg_marquardt(T_target, np.zeros(6))

        assert solution.is_valid
        assert solution.error < 1e-4

    def test_ik_reproduces_pose(self, kinematics):
        q_target = np.array([0.4, -0.6, 0.9, -0.3, 0.7, -0.1])
        T_target = kinematics.fk(q_target)

        solution = kinematics.ik(T_target)

        if solution.is_valid:
            T_result = kinematics.fk(solution.joints)
            assert np.allclose(T_result, T_target, atol=1e-3)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
