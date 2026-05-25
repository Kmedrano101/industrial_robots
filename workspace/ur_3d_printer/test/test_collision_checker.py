# Copyright 2024 Kevin Medrano
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the self-collision detection module."""

import numpy as np
import pytest

from ur_3d_printer.collision_checker import (
    Capsule,
    CollisionResult,
    SelfCollisionChecker,
    capsule_distance,
    forward_kinematics_all_links,
    segment_segment_distance,
    _dh_transform,
    UR_DH_PARAMS,
)


# ── Segment Distance ────────────────────────────────────────────────────────

class TestSegmentDistance:
    """Minimum distance between two line segments."""

    def test_parallel_horizontal(self):
        d, _, _ = segment_segment_distance(
            np.array([0, 0, 0.0]), np.array([1, 0, 0.0]),
            np.array([0, 1, 0.0]), np.array([1, 1, 0.0]),
        )
        assert abs(d - 1.0) < 1e-10

    def test_same_segment(self):
        d, _, _ = segment_segment_distance(
            np.array([0, 0, 0.0]), np.array([1, 0, 0.0]),
            np.array([0, 0, 0.0]), np.array([1, 0, 0.0]),
        )
        assert d < 1e-10

    def test_point_to_point(self):
        d, _, _ = segment_segment_distance(
            np.array([0, 0, 0.0]), np.array([0, 0, 0.0]),
            np.array([3, 4, 0.0]), np.array([3, 4, 0.0]),
        )
        assert abs(d - 5.0) < 1e-10

    def test_perpendicular(self):
        d, _, _ = segment_segment_distance(
            np.array([0, 0, 0.0]), np.array([1, 0, 0.0]),
            np.array([0.5, 0.5, 0.0]), np.array([0.5, 1.5, 0.0]),
        )
        assert abs(d - 0.5) < 1e-10

    def test_crossing_different_z(self):
        d, _, _ = segment_segment_distance(
            np.array([0, 0, 0.0]), np.array([1, 1, 0.0]),
            np.array([0, 1, 1.0]), np.array([1, 0, 1.0]),
        )
        assert d > 0.0

    def test_endpoint_to_midpoint(self):
        d, s, t = segment_segment_distance(
            np.array([0, 0, 0.0]), np.array([2, 0, 0.0]),
            np.array([1, 3, 0.0]), np.array([1, 3, 0.0]),  # point
        )
        assert abs(d - 3.0) < 1e-10
        assert abs(s - 0.5) < 1e-10


# ── Capsule Distance ────────────────────────────────────────────────────────

class TestCapsuleDistance:
    """Distance between two capsules."""

    def test_non_overlapping(self):
        a = Capsule(np.array([0, 0, 0.0]), np.array([1, 0, 0.0]), 0.1)
        b = Capsule(np.array([0, 2, 0.0]), np.array([1, 2, 0.0]), 0.1)
        assert abs(capsule_distance(a, b) - 1.8) < 1e-10

    def test_overlapping(self):
        a = Capsule(np.array([0, 0, 0.0]), np.array([1, 0, 0.0]), 0.5)
        b = Capsule(np.array([0, 0.5, 0.0]), np.array([1, 0.5, 0.0]), 0.5)
        assert capsule_distance(a, b) < 0.0

    def test_touching(self):
        a = Capsule(np.array([0, 0, 0.0]), np.array([1, 0, 0.0]), 0.5)
        b = Capsule(np.array([0, 1, 0.0]), np.array([1, 1, 0.0]), 0.5)
        assert abs(capsule_distance(a, b)) < 1e-10

    def test_capsule_length(self):
        c = Capsule(np.array([0, 0, 0.0]), np.array([3, 4, 0.0]), 0.1)
        assert abs(c.length - 5.0) < 1e-10


# ── DH Transform ────────────────────────────────────────────────────────────

class TestDHTransform:
    """Standard DH transformation matrix."""

    def test_identity_params(self):
        T = _dh_transform(0, 0, 0, 0)
        np.testing.assert_array_almost_equal(T, np.eye(4))

    def test_pure_translation_d(self):
        T = _dh_transform(0, 0.5, 0, 0)
        assert abs(T[2, 3] - 0.5) < 1e-10

    def test_pure_translation_a(self):
        T = _dh_transform(0, 0, 0.3, 0)
        assert abs(T[0, 3] - 0.3) < 1e-10

    def test_pure_rotation(self):
        T = _dh_transform(np.pi / 2, 0, 0, 0)
        assert abs(T[0, 0]) < 1e-10
        assert abs(T[1, 0] - 1.0) < 1e-10

    def test_rotation_matrix_valid(self):
        T = _dh_transform(0.5, 0.1, 0.2, 0.3)
        R = T[:3, :3]
        np.testing.assert_array_almost_equal(R.T @ R, np.eye(3), decimal=10)
        assert abs(np.linalg.det(R) - 1.0) < 1e-10


# ── Forward Kinematics ──────────────────────────────────────────────────────

class TestForwardKinematics:
    """FK computation for all link frames."""

    def test_zero_config_num_transforms(self):
        transforms = forward_kinematics_all_links(np.zeros(6))
        assert len(transforms) == 7

    def test_base_is_identity(self):
        transforms = forward_kinematics_all_links(np.zeros(6))
        np.testing.assert_array_almost_equal(transforms[0], np.eye(4))

    def test_valid_rotation_matrices(self):
        transforms = forward_kinematics_all_links(
            np.array([0.3, -0.5, 1.2, -0.8, 0.4, -0.1]),
        )
        for T in transforms:
            assert T.shape == (4, 4)
            R = T[:3, :3]
            assert abs(np.linalg.det(R) - 1.0) < 1e-6

    def test_different_configs_differ(self):
        T0 = forward_kinematics_all_links(np.zeros(6))
        T1 = forward_kinematics_all_links(
            np.array([0.5, -0.3, 0.7, 0.1, -0.2, 0.4]),
        )
        assert not np.allclose(T0[6], T1[6])

    def test_joint1_rotation(self):
        T0 = forward_kinematics_all_links(np.zeros(6))
        T1 = forward_kinematics_all_links(
            np.array([np.pi / 2, 0, 0, 0, 0, 0]),
        )
        # End-effector positions should differ after rotating joint 1.
        assert not np.allclose(T0[6][:3, 3], T1[6][:3, 3], atol=1e-4)

    def test_ur3e_params(self):
        transforms = forward_kinematics_all_links(
            np.zeros(6), UR_DH_PARAMS['ur3e'],
        )
        assert len(transforms) == 7

    def test_ur10e_params(self):
        transforms = forward_kinematics_all_links(
            np.zeros(6), UR_DH_PARAMS['ur10e'],
        )
        assert len(transforms) == 7


# ── Self-Collision Checker ──────────────────────────────────────────────────

class TestSelfCollisionChecker:
    """Self-collision detection for UR robots."""

    def test_home_no_collision(self):
        checker = SelfCollisionChecker(safety_margin=0.01)
        result = checker.check_config(np.zeros(6))
        assert not result.has_collision
        assert result.min_clearance > 0.0

    def test_typical_print_pose_no_collision(self):
        q = np.array([0.0, -np.pi / 4, np.pi / 3, -np.pi / 2, -np.pi / 2, 0.0])
        checker = SelfCollisionChecker(safety_margin=0.01)
        result = checker.check_config(q)
        assert not result.has_collision

    def test_folded_arm_collision(self):
        q = np.array([0.0, 0.0, np.pi * 0.95, 0.0, 0.0, 0.0])
        checker = SelfCollisionChecker(safety_margin=0.01)
        result = checker.check_config(q)
        # Extreme fold — expect collision or very tight clearance.
        assert result.has_collision or result.min_clearance < 0.03

    def test_capsule_count(self):
        checker = SelfCollisionChecker()
        capsules = checker._build_capsules(np.zeros(6))
        assert len(capsules) == 7  # 6 links + extruder

    def test_trajectory_check(self):
        checker = SelfCollisionChecker(safety_margin=0.01)
        traj = np.array([
            [0, 0, 0, 0, 0, 0.0],
            [0.1, -0.2, 0.3, -0.1, 0.2, -0.1],
        ])
        collisions = checker.check_trajectory(traj)
        assert isinstance(collisions, list)

    def test_min_clearance_trajectory(self):
        checker = SelfCollisionChecker(safety_margin=0.01)
        traj = np.array([
            [0, 0, 0, 0, 0, 0.0],
            [0.0, -np.pi / 4, np.pi / 3, -np.pi / 2, -np.pi / 2, 0.0],
        ])
        clearance, idx, pair = checker.min_clearance_trajectory(traj)
        assert isinstance(clearance, float)
        assert idx >= 0

    def test_safety_margin_effect(self):
        q = np.array([0.0, -np.pi / 4, np.pi / 3, -np.pi / 2, -np.pi / 2, 0.0])
        r_small = SelfCollisionChecker(safety_margin=0.001).check_config(q)
        r_large = SelfCollisionChecker(safety_margin=0.05).check_config(q)
        assert r_small.min_clearance > r_large.min_clearance

    def test_collision_pairs_reported(self):
        q = np.array([0.0, 0.0, np.pi * 0.95, 0.0, 0.0, 0.0])
        result = SelfCollisionChecker(safety_margin=0.01).check_config(q)
        if result.has_collision:
            assert len(result.collision_pairs) > 0
            for pair in result.collision_pairs:
                assert len(pair) == 2

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match='Unknown robot model'):
            SelfCollisionChecker(robot_model='ur99e')

    def test_ur3e_model(self):
        checker = SelfCollisionChecker(robot_model='ur3e')
        result = checker.check_config(np.zeros(6))
        assert isinstance(result, CollisionResult)

    def test_ur10e_model(self):
        checker = SelfCollisionChecker(robot_model='ur10e')
        result = checker.check_config(np.zeros(6))
        assert isinstance(result, CollisionResult)
