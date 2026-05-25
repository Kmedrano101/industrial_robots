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
"""Tests for the multi-axis toolpath planning module."""

import os
import struct
import tempfile

import numpy as np
import pytest

from ur_3d_printer.multiaxis_planner import (
    MeshTriangle,
    MultiAxisConfig,
    MultiAxisToolpathGenerator,
    _densify_points,
    _order_segments,
    _rotate_vector,
    compute_surface_normal_at_point,
    interpolate_orientations,
    load_stl_mesh,
    nozzle_down_orientation,
    orientation_from_normal,
    smooth_orientations,
)
from ur_3d_printer.toolpath import Waypoint


# ── Helpers ──────────────────────────────────────────────────────────────────

def _write_cube_stl(filepath, size=20.0):
    """Write a minimal binary STL cube (12 triangles)."""
    s = size
    faces = [
        # Bottom (z=0)
        ([0, 0, 0], [s, 0, 0], [s, s, 0], [0, 0, -1]),
        ([0, 0, 0], [s, s, 0], [0, s, 0], [0, 0, -1]),
        # Top
        ([0, 0, s], [s, s, s], [s, 0, s], [0, 0, 1]),
        ([0, 0, s], [0, s, s], [s, s, s], [0, 0, 1]),
        # Front (y=0)
        ([0, 0, 0], [s, 0, 0], [s, 0, s], [0, -1, 0]),
        ([0, 0, 0], [s, 0, s], [0, 0, s], [0, -1, 0]),
        # Back
        ([0, s, 0], [s, s, s], [s, s, 0], [0, 1, 0]),
        ([0, s, 0], [0, s, s], [s, s, s], [0, 1, 0]),
        # Left (x=0)
        ([0, 0, 0], [0, s, s], [0, s, 0], [-1, 0, 0]),
        ([0, 0, 0], [0, 0, s], [0, s, s], [-1, 0, 0]),
        # Right
        ([s, 0, 0], [s, s, 0], [s, s, s], [1, 0, 0]),
        ([s, 0, 0], [s, s, s], [s, 0, s], [1, 0, 0]),
    ]

    with open(filepath, 'wb') as f:
        f.write(b'Binary STL test cube' + b'\0' * 60)
        f.write(struct.pack('<I', len(faces)))
        for v0, v1, v2, n in faces:
            f.write(struct.pack('<3f', *n))
            f.write(struct.pack('<3f', *v0))
            f.write(struct.pack('<3f', *v1))
            f.write(struct.pack('<3f', *v2))
            f.write(struct.pack('<H', 0))


# ── Orientation From Normal ─────────────────────────────────────────────────

class TestOrientationFromNormal:

    def test_vertical_normal(self):
        R = orientation_from_normal(np.array([0, 0, 1.0]), max_tilt=np.radians(45))
        assert R[2, 2] < -0.9  # Z-axis points down

    def test_tilted_normal(self):
        angle = np.radians(30)
        normal = np.array([np.sin(angle), 0, np.cos(angle)])
        R = orientation_from_normal(normal, max_tilt=np.radians(45))
        assert abs(R[0, 2]) > 0.01  # X-component of Z-axis

    def test_max_tilt_clamp(self):
        angle = np.radians(80)
        normal = np.array([np.sin(angle), 0, np.cos(angle)])
        R = orientation_from_normal(normal, max_tilt=np.radians(45))

        approach = R[:, 2]
        vertical = np.array([0, 0, -1.0])
        actual_tilt = np.arccos(np.clip(np.dot(approach, vertical), -1, 1))
        assert actual_tilt <= np.radians(45) + 0.01

    def test_valid_rotation(self):
        normal = np.array([0.3, 0.4, 0.866])
        normal /= np.linalg.norm(normal)
        R = orientation_from_normal(normal)

        np.testing.assert_array_almost_equal(R.T @ R, np.eye(3), decimal=6)
        assert abs(np.linalg.det(R) - 1.0) < 1e-6

    def test_downward_normal(self):
        R = orientation_from_normal(np.array([0, 0, -1.0]))
        assert R.shape == (3, 3)
        assert abs(np.linalg.det(R) - 1.0) < 1e-6


# ── Smooth Orientations ─────────────────────────────────────────────────────

class TestSmoothOrientations:

    def test_identical_preserved(self):
        R = np.eye(3)
        wps = [
            Waypoint(
                position=np.array([i * 0.01, 0, 0.0]),
                orientation=R.copy(),
                feed_rate=0.05,
                layer_index=0,
                line_number=i,
            )
            for i in range(10)
        ]
        smoothed = smooth_orientations(wps, window_size=3)
        for wp in smoothed:
            np.testing.assert_array_almost_equal(wp.orientation, R, decimal=4)

    def test_discontinuity_reduced(self):
        wps = []
        for i in range(10):
            if i == 5:
                R = orientation_from_normal(np.array([0.5, 0, 0.866]))
            else:
                R = nozzle_down_orientation()
            wps.append(Waypoint(
                position=np.array([i * 0.01, 0, 0.0]),
                orientation=R.copy(),
                feed_rate=0.05,
                layer_index=0,
                line_number=i,
            ))

        orig_diff = np.linalg.norm(wps[4].orientation - wps[5].orientation)
        smoothed = smooth_orientations(wps, window_size=5)
        sm_diff = np.linalg.norm(smoothed[4].orientation - smoothed[5].orientation)
        assert sm_diff <= orig_diff + 0.01

    def test_short_list(self):
        wp = Waypoint(
            position=np.zeros(3),
            orientation=np.eye(3),
            feed_rate=0.05,
            layer_index=0,
            line_number=0,
        )
        result = smooth_orientations([wp], window_size=5)
        assert len(result) == 1


# ── Interpolate Orientations ────────────────────────────────────────────────

class TestInterpolateOrientations:

    def test_alpha_zero(self):
        R1 = np.eye(3)
        R2 = nozzle_down_orientation()
        np.testing.assert_array_almost_equal(
            interpolate_orientations(R1, R2, 0.0), R1, decimal=5,
        )

    def test_alpha_one(self):
        R1 = np.eye(3)
        R2 = nozzle_down_orientation()
        np.testing.assert_array_almost_equal(
            interpolate_orientations(R1, R2, 1.0), R2, decimal=5,
        )

    def test_result_is_rotation(self):
        R1 = np.eye(3)
        R2 = nozzle_down_orientation()
        R = interpolate_orientations(R1, R2, 0.5)
        np.testing.assert_array_almost_equal(R.T @ R, np.eye(3), decimal=5)
        assert abs(np.linalg.det(R) - 1.0) < 1e-5


# ── Rotate Vector ───────────────────────────────────────────────────────────

class TestRotateVector:

    def test_90_around_z(self):
        result = _rotate_vector(
            np.array([1, 0, 0.0]),
            np.array([0, 0, 1.0]),
            np.pi / 2,
        )
        np.testing.assert_array_almost_equal(result, [0, 1, 0], decimal=10)

    def test_full_rotation(self):
        v = np.array([1, 2, 3.0])
        result = _rotate_vector(v, np.array([0, 0, 1.0]), 2 * np.pi)
        np.testing.assert_array_almost_equal(result, v, decimal=10)

    def test_zero_rotation(self):
        v = np.array([1, 2, 3.0])
        result = _rotate_vector(v, np.array([0, 0, 1.0]), 0.0)
        np.testing.assert_array_almost_equal(result, v, decimal=10)


# ── Nozzle Down Orientation ─────────────────────────────────────────────────

class TestNozzleDown:

    def test_z_axis_points_down(self):
        R = nozzle_down_orientation()
        np.testing.assert_array_almost_equal(R[:, 2], [0, 0, -1])

    def test_valid_rotation(self):
        R = nozzle_down_orientation()
        np.testing.assert_array_almost_equal(R.T @ R, np.eye(3))
        assert abs(np.linalg.det(R) - 1.0) < 1e-10


# ── Surface Normal ──────────────────────────────────────────────────────────

class TestSurfaceNormal:

    def test_flat_triangle(self):
        tri = MeshTriangle(
            vertices=np.array([[0, 0, 0], [0.01, 0, 0], [0, 0.01, 0.0]]),
            normal=np.array([0, 0, 1.0]),
        )
        n = compute_surface_normal_at_point(
            np.array([0.003, 0.003, 0.0]),
            [tri],
            search_radius=0.1,
        )
        assert n[2] > 0.9

    def test_no_nearby_triangles(self):
        tri = MeshTriangle(
            vertices=np.array([[10, 10, 10.0], [11, 10, 10], [10, 11, 10]]),
            normal=np.array([0, 0, 1.0]),
        )
        n = compute_surface_normal_at_point(
            np.zeros(3), [tri], search_radius=0.01,
        )
        assert n.shape == (3,)
        assert abs(np.linalg.norm(n) - 1.0) < 1e-6


# ── STL Loading ─────────────────────────────────────────────────────────────

class TestLoadSTL:

    def test_load_binary_cube(self):
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            path = f.name
        try:
            _write_cube_stl(path)
            tris = load_stl_mesh(path)
            assert len(tris) == 12
            for tri in tris:
                assert tri.vertices.shape == (3, 3)
                assert tri.normal.shape == (3,)
        finally:
            os.unlink(path)

    def test_mm_to_metres(self):
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            path = f.name
        try:
            _write_cube_stl(path, size=20.0)  # 20 mm cube
            tris = load_stl_mesh(path)
            verts = np.vstack([t.vertices for t in tris])
            assert verts.max() < 0.021  # should be ~0.020 m
            assert verts.max() > 0.019
        finally:
            os.unlink(path)


# ── Densify Points ──────────────────────────────────────────────────────────

class TestDensify:

    def test_no_densification_needed(self):
        pts = np.array([[0, 0, 0.0], [0.001, 0, 0]])
        result = _densify_points(pts, max_spacing=0.01)
        assert len(result) == 2

    def test_inserts_points(self):
        pts = np.array([[0, 0, 0.0], [0.1, 0, 0]])
        result = _densify_points(pts, max_spacing=0.01)
        assert len(result) >= 10

    def test_single_point(self):
        pts = np.array([[0, 0, 0.0]])
        result = _densify_points(pts, max_spacing=0.01)
        assert len(result) == 1


# ── Order Segments ──────────────────────────────────────────────────────────

class TestOrderSegments:

    def test_empty(self):
        assert _order_segments([]) == []

    def test_single_segment(self):
        segs = [(np.array([0, 0, 0.0]), np.array([1, 0, 0.0]))]
        contours = _order_segments(segs)
        assert len(contours) == 1
        assert len(contours[0]) == 2

    def test_connected_chain(self):
        segs = [
            (np.array([0, 0, 0.0]), np.array([1, 0, 0.0])),
            (np.array([1, 0, 0.0]), np.array([1, 1, 0.0])),
            (np.array([1, 1, 0.0]), np.array([0, 1, 0.0])),
        ]
        contours = _order_segments(segs)
        assert len(contours) == 1
        assert len(contours[0]) == 4


# ── Toolpath Generator ──────────────────────────────────────────────────────

class TestMultiAxisToolpathGenerator:

    def test_generate_from_cube(self):
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            path = f.name
        try:
            _write_cube_stl(path, size=20.0)  # 20 mm = 0.020 m

            config = MultiAxisConfig(
                layer_height=0.005,
                enable_collision_check=False,
            )
            gen = MultiAxisToolpathGenerator(config)
            tp = gen.generate_from_stl(path)

            assert tp.num_layers > 0
            assert tp.metadata['type'] == 'multi_axis'

            for layer in tp.layers:
                for wp in layer.waypoints:
                    assert wp.orientation.shape == (3, 3)
                    assert abs(np.linalg.det(wp.orientation) - 1.0) < 1e-4
        finally:
            os.unlink(path)

    def test_config_defaults(self):
        c = MultiAxisConfig()
        assert c.layer_height > 0
        assert 0 < c.max_tilt_angle <= np.pi / 2
        assert c.collision_safety_margin > 0

    def test_collision_checker_created(self):
        gen = MultiAxisToolpathGenerator(
            MultiAxisConfig(enable_collision_check=True),
        )
        assert gen.collision_checker is not None

    def test_collision_checker_disabled(self):
        gen = MultiAxisToolpathGenerator(
            MultiAxisConfig(enable_collision_check=False),
        )
        assert gen.collision_checker is None
