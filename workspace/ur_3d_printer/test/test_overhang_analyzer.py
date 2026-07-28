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
"""Tests for the overhang analyzer module.

The angle convention (0 deg = vertical wall/fine, 90 deg = straight-down
ceiling/worst) is the single easiest thing to get backwards in this kind of
code, so the tests lock down the three canonical cases (floor, wall,
ceiling) explicitly before testing anything else.
"""

import os
import struct
import tempfile

import numpy as np
import pytest

from ur_3d_printer.multiaxis_planner import MeshTriangle
from ur_3d_printer.overhang_analyzer import (
    OverhangConfig,
    analyze_overhangs,
    analyze_stl_overhangs,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _triangle(normal, base=(0.0, 0.0, 0.0), size=1.0) -> MeshTriangle:
    """A single triangle with an explicit (possibly non-physical) normal.

    analyze_overhangs() only reads t.normal, never recomputes it from the
    vertices, so a right-angle triangle with a hand-set normal is enough to
    exercise a single, precise overhang angle in isolation.
    """
    v0 = np.array(base, dtype=float)
    v1 = v0 + np.array([size, 0.0, 0.0])
    v2 = v0 + np.array([0.0, size, 0.0])
    return MeshTriangle(
        vertices=np.array([v0, v1, v2]),
        normal=np.array(normal, dtype=float),
    )


def _write_cube_stl(filepath, size=20.0):
    """Write a minimal binary STL cube (12 triangles), mirrors the helper
    in test_multiaxis_planner.py."""
    s = size
    faces = [
        # Bottom (z=0) -- points straight down, the worst-case ceiling.
        ([0, 0, 0], [s, 0, 0], [s, s, 0], [0, 0, -1]),
        ([0, 0, 0], [s, s, 0], [0, s, 0], [0, 0, -1]),
        # Top (z=s) -- points straight up, a floor, never flagged.
        ([0, 0, s], [s, s, s], [s, 0, s], [0, 0, 1]),
        ([0, 0, s], [0, s, s], [s, s, s], [0, 0, 1]),
        # Front (y=0) -- vertical wall.
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


# ── Angle convention: the three canonical cases ─────────────────────────────

class TestAngleConvention:

    def test_straight_down_is_worst_case_90deg(self):
        report = analyze_overhangs([_triangle([0, 0, -1])])
        assert report.needs_support
        assert report.overhang_faces[0].angle_deg == pytest.approx(90.0, abs=0.5)

    def test_vertical_wall_is_zero_and_not_flagged(self):
        report = analyze_overhangs([_triangle([1, 0, 0])])
        assert not report.needs_support
        assert report.worst_angle_deg == 0.0

    def test_straight_up_floor_never_flagged(self):
        report = analyze_overhangs([_triangle([0, 0, 1])])
        assert not report.needs_support
        assert report.overhang_area == 0.0

    @staticmethod
    def _tilted_normal(alpha_deg):
        """normal = (sin(alpha), 0, -cos(alpha)): alpha=0 -> straight down
        (angle_deg=90), alpha=90 -> vertical wall (angle_deg=0). I.e. this
        helper's alpha and the module's angle_deg are complementary:
        angle_deg == 90 - alpha_deg."""
        a = np.radians(alpha_deg)
        return [np.sin(a), 0.0, -np.cos(a)]

    def test_tilt_angle_computation_is_the_complement_of_alpha(self):
        # alpha=45 -> angle_deg=45 (the one point where they coincide) --
        # purely a numeric-conversion check, not a threshold/flagging test.
        report = analyze_overhangs(
            [_triangle(self._tilted_normal(45))],
            OverhangConfig(max_printable_overhang_deg=0.0),  # force-flag it
        )
        assert report.overhang_faces[0].angle_deg == pytest.approx(45.0, abs=0.5)

    def test_below_threshold_not_flagged(self):
        # alpha=50 -> angle_deg=40, clearly under the 45 deg default.
        report = analyze_overhangs([_triangle(self._tilted_normal(50))])
        assert not report.needs_support

    def test_above_threshold_flagged(self):
        # alpha=40 -> angle_deg=50, clearly over the 45 deg default.
        report = analyze_overhangs([_triangle(self._tilted_normal(40))])
        assert report.needs_support
        assert report.overhang_faces[0].angle_deg == pytest.approx(50.0, abs=0.5)


# ── Aggregate report over a real solid mesh ─────────────────────────────────

class TestCubeAggregate:

    def test_only_bottom_face_flagged(self):
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            path = f.name
        try:
            _write_cube_stl(path, size=20.0)  # 20 mm cube
            report = analyze_stl_overhangs(path)

            assert report.needs_support
            # Exactly the 2 bottom triangles, none of the 4 side or 2 top.
            assert len(report.overhang_faces) == 2
            for face in report.overhang_faces:
                assert face.angle_deg == pytest.approx(90.0, abs=0.5)

            # Bottom face area = 20mm x 20mm = 0.02m x 0.02m = 4e-4 m^2.
            assert report.overhang_area == pytest.approx(4e-4, rel=1e-3)
            assert report.overhang_area_pct == pytest.approx(100.0 / 6.0, abs=0.5)
        finally:
            os.unlink(path)

    def test_upside_down_build_direction_flags_the_opposite_face(self):
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            path = f.name
        try:
            _write_cube_stl(path, size=20.0)
            # Printing "upside down" (build direction -Z) makes the former
            # top face the new ceiling.
            report = analyze_stl_overhangs(
                path, OverhangConfig(build_direction=np.array([0.0, 0.0, -1.0]))
            )
            assert len(report.overhang_faces) == 2
            for face in report.overhang_faces:
                assert face.centroid[2] == pytest.approx(0.020, abs=1e-6)  # old top, z=20mm=0.02m
        finally:
            os.unlink(path)


# ── Config / report basics ──────────────────────────────────────────────────

class TestReportProperties:

    def test_empty_mesh(self):
        report = analyze_overhangs([])
        assert not report.needs_support
        assert report.total_area == 0.0
        assert report.overhang_area_pct == 0.0
        assert report.worst_angle_deg == 0.0

    def test_zero_build_direction_raises(self):
        with pytest.raises(ValueError):
            analyze_overhangs([_triangle([0, 0, -1])], OverhangConfig(
                build_direction=np.array([0.0, 0.0, 0.0]),
            ))

    def test_summary_mentions_no_overhangs_when_clean(self):
        report = analyze_overhangs([_triangle([1, 0, 0])])
        assert 'No overhangs' in report.summary()

    def test_summary_mentions_area_pct_when_flagged(self):
        report = analyze_overhangs([_triangle([0, 0, -1])])
        assert '%' in report.summary()

    def test_non_unit_normal_is_normalized(self):
        # A hand-edited STL can carry a non-unit or zero normal; make sure
        # we don't silently produce nonsense (e.g. angle > 90) for it.
        report = analyze_overhangs([_triangle([0, 0, -5.0])])
        assert report.overhang_faces[0].angle_deg == pytest.approx(90.0, abs=0.5)
