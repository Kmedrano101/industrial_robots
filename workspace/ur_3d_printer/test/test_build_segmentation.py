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
"""Tests for the build-direction segmentation module.

Fixture design note: a face whose normal is aligned with a single axis
(e.g. a flat floor or ceiling, normal = (0,0,+-1)) is trivially "printable"
(angle 0) under BOTH the opposite direction AND every direction merely
PERPENDICULAR to its axis -- a ceiling becomes a floor if you flip the
build upside down, but it *also* becomes an ordinary side wall if you print
sideways instead. So with the full 6-axis candidate pool, "which direction
fixes a pure ceiling face" is genuinely ambiguous (4 of the 6 candidates
tie), and the outcome is a deterministic but somewhat arbitrary
list-order tie-break, not a specific direction worth hardcoding into an
assertion. Tests that need an unambiguous, hand-verifiable outcome
restrict `candidate_directions` to just [+Z, -Z] so the only real choice
left is "print it, or flip it" -- verified directly against
overhang_angles_deg() rather than derived by hand trigonometry, which is
easy to get backwards (see the overhang_analyzer tests for two examples of
exactly that mistake).
"""

import os
import struct
import tempfile

import numpy as np
import pytest

from ur_3d_printer.multiaxis_planner import MeshTriangle
from ur_3d_printer.build_segmentation import (
    AXIS_ALIGNED_DIRECTIONS,
    SegmentationConfig,
    segment_by_build_direction,
    segment_stl_by_build_direction,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _triangle(normal, base=(0.0, 0.0, 0.0), size=1.0) -> MeshTriangle:
    v0 = np.array(base, dtype=float)
    v1 = v0 + np.array([size, 0.0, 0.0])
    v2 = v0 + np.array([0.0, size, 0.0])
    return MeshTriangle(
        vertices=np.array([v0, v1, v2]),
        normal=np.array(normal, dtype=float),
    )


def _all_face_indices(result) -> list:
    return sorted(i for seg in result.segments for i in seg.face_indices)


def _write_cube_stl(filepath, size=20.0):
    """Binary STL cube, all faces printable in the default +Z direction
    (mirrors the helper used by test_multiaxis_planner.py /
    test_overhang_analyzer.py -- the bottom face is the only overhang)."""
    s = size
    faces = [
        ([0, 0, 0], [s, 0, 0], [s, s, 0], [0, 0, -1]),
        ([0, 0, 0], [s, s, 0], [0, s, 0], [0, 0, -1]),
        ([0, 0, s], [s, s, s], [s, 0, s], [0, 0, 1]),
        ([0, 0, s], [0, s, s], [s, s, s], [0, 0, 1]),
        ([0, 0, 0], [s, 0, 0], [s, 0, s], [0, -1, 0]),
        ([0, 0, 0], [s, 0, s], [0, 0, s], [0, -1, 0]),
        ([0, s, 0], [s, s, s], [s, s, 0], [0, 1, 0]),
        ([0, s, 0], [0, s, s], [s, s, s], [0, 1, 0]),
        ([0, 0, 0], [0, s, s], [0, s, 0], [-1, 0, 0]),
        ([0, 0, 0], [0, 0, s], [0, s, s], [-1, 0, 0]),
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


# ── Everything already printable in the default direction ──────────────────

class TestNoReorientationNeeded:

    def test_cube_needs_two_segments_and_covers_every_face(self):
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            path = f.name
        try:
            _write_cube_stl(path, size=20.0)
            result = segment_stl_by_build_direction(path)
            # The bottom face is a straight-down overhang (angle 90 > 45),
            # so it's NOT covered by the default direction alone -- the
            # algorithm still needs a 2nd segment to clear it (which one of
            # the 5 non-default axes it picks is an arbitrary tie-break,
            # see module docstring; only the count + completeness matter).
            assert result.num_segments == 2
            assert _all_face_indices(result) == list(range(12))
            assert result.overall_overhang_area_pct == pytest.approx(0.0, abs=1e-6)
        finally:
            os.unlink(path)

    def test_single_upward_face_needs_no_reorientation(self):
        triangles = [_triangle([0, 0, 1]) for _ in range(4)]
        result = segment_by_build_direction(triangles)
        assert result.num_segments == 1
        assert result.segments[0].build_direction == pytest.approx([0, 0, 1])
        assert result.overall_overhang_area_pct == pytest.approx(0.0)


# ── The "print it, then flip it over" scenario ──────────────────────────────
#
# Candidate pool restricted to [+Z, -Z] in this whole class: with the full
# 6-axis pool a pure ceiling/floor face is a 4-way tie (see module
# docstring), so pinning the pool down to just "print, or flip" is what
# makes the outcome unambiguous enough to assert on directly.

class TestFlipScenario:

    _POOL = [np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, -1.0])]

    def _floor_and_ceiling_mesh(self, n_floor=5, n_ceiling=5):
        floor = [_triangle([0, 0, 1], base=(i, 0, 0)) for i in range(n_floor)]
        ceiling = [_triangle([0, 0, -1], base=(i, 5, 0)) for i in range(n_ceiling)]
        return floor + ceiling, n_floor, n_ceiling

    def _config(self, **overrides):
        return SegmentationConfig(candidate_directions=self._POOL, **overrides)

    def test_needs_exactly_two_segments(self):
        triangles, n_floor, n_ceiling = self._floor_and_ceiling_mesh()
        result = segment_by_build_direction(triangles, self._config())
        assert result.num_segments == 2

    def test_partition_is_complete_and_disjoint(self):
        triangles, n_floor, n_ceiling = self._floor_and_ceiling_mesh()
        result = segment_by_build_direction(triangles, self._config())
        all_indices = _all_face_indices(result)
        assert all_indices == list(range(len(triangles)))  # no dupes, none missing

    def test_default_direction_segment_comes_first(self):
        triangles, *_ = self._floor_and_ceiling_mesh()
        config = self._config(default_build_direction=np.array([0.0, 0.0, 1.0]))
        result = segment_by_build_direction(triangles, config)
        assert result.segments[0].build_direction == pytest.approx([0, 0, 1])

    def test_each_segment_has_near_zero_residual_overhang(self):
        triangles, *_ = self._floor_and_ceiling_mesh()
        result = segment_by_build_direction(triangles, self._config())
        for seg in result.segments:
            assert seg.overhang_area_pct == pytest.approx(0.0, abs=1e-6)
        assert result.overall_overhang_area_pct == pytest.approx(0.0, abs=1e-6)

    def test_ceiling_faces_land_in_the_flipped_segment(self):
        triangles, n_floor, n_ceiling = self._floor_and_ceiling_mesh()
        result = segment_by_build_direction(triangles, self._config())
        ceiling_indices = set(range(n_floor, n_floor + n_ceiling))
        flipped = [s for s in result.segments if s.build_direction[2] < 0]
        assert len(flipped) == 1
        assert set(flipped[0].face_indices) == ceiling_indices


# ── max_segments forces a single, honestly-imperfect segment ───────────────

class TestMaxSegmentsCap:

    _POOL = [np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, -1.0])]

    def test_max_segments_one_keeps_everything_together(self):
        floor = [_triangle([0, 0, 1]) for _ in range(5)]
        ceiling = [_triangle([0, 0, -1], base=(0, 5, 0)) for _ in range(5)]
        triangles = floor + ceiling
        result = segment_by_build_direction(
            triangles,
            SegmentationConfig(max_segments=1, candidate_directions=self._POOL),
        )
        assert result.num_segments == 1
        # The ceiling half is force-attached to the only segment, imperfectly:
        # residual overhang should reflect roughly half the total area, NOT
        # be silently reported as zero.
        assert result.overall_overhang_area_pct == pytest.approx(50.0, abs=1.0)

    def test_max_segments_below_one_raises(self):
        with pytest.raises(ValueError):
            segment_by_build_direction(
                [_triangle([0, 0, -1])], SegmentationConfig(max_segments=0),
            )


# ── Config / report basics ──────────────────────────────────────────────────

class TestReportBasics:

    def test_empty_mesh(self):
        result = segment_by_build_direction([])
        assert result.num_segments == 0
        assert result.total_area == 0.0

    def test_default_candidate_pool_is_six_axes(self):
        assert len(AXIS_ALIGNED_DIRECTIONS) == 6
        for d in AXIS_ALIGNED_DIRECTIONS:
            assert np.linalg.norm(d) == pytest.approx(1.0)

    def test_summary_mentions_no_reorientation_for_single_segment(self):
        result = segment_by_build_direction([_triangle([0, 0, 1])])
        assert 'no reorientation' in result.summary()

    def test_summary_mentions_segment_count_when_multiple(self):
        # Pool restricted to [+Z, -Z]: with the full 6-axis pool this
        # particular pure floor/ceiling mesh collapses to 1 segment, since
        # any horizontal axis fixes both at once (see module docstring) --
        # restricting the pool to an opposite pair forces the 2-segment
        # "print, then flip" outcome instead.
        triangles = (
            [_triangle([0, 0, 1]) for _ in range(3)]
            + [_triangle([0, 0, -1], base=(0, 5, 0)) for _ in range(3)]
        )
        config = SegmentationConfig(candidate_directions=[
            np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, -1.0]),
        ])
        result = segment_by_build_direction(triangles, config)
        assert '2 segments' in result.summary()

    def test_custom_candidate_pool_is_respected(self):
        # No alternative to the default offered (candidate_directions ==
        # just +Z again) -- a straight-down ceiling face needs some OTHER
        # direction to fix it (any of the 5 non-Z axes would do), so
        # restricting the pool down to only +Z must leave it unfixed.
        # This demonstrates the pool restriction actually excludes the
        # axes the default AXIS_ALIGNED_DIRECTIONS pool would otherwise try.
        config = SegmentationConfig(
            candidate_directions=[np.array([0.0, 0.0, 1.0])],
        )
        result = segment_by_build_direction([_triangle([0, 0, -1])], config)
        assert result.num_segments == 1  # only the default direction is used
        assert result.overall_overhang_area_pct > 0.0
