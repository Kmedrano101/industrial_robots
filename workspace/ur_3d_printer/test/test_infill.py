# Copyright 2024 Kevin Medrano
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Tests for the infill pattern generation module.

These tests check structural invariants per pattern rather than exact
coordinates. The exact path geometry depends on raster phase and floating
point details; what matters is:

  * the function returns the documented shape (count of polylines, point
    counts within reason),
  * all generated points stay inside the input polygon, and
  * patterns that promise a single continuous polyline keep that promise.
"""

import os
import sys

import numpy as np
import pytest

# Make the package importable when running pytest directly from the repo.
_TEST_DIR = os.path.dirname(__file__)
_PKG_ROOT = os.path.abspath(os.path.join(_TEST_DIR, ".."))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

shapely = pytest.importorskip("shapely", reason="shapely required for infill tests")
from shapely.geometry import Polygon as _ShpPolygon  # noqa: E402

from ur_3d_printer.infill import (  # noqa: E402
    Pattern,
    generate_infill,
    line_spacing_from_density,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _square(size: float = 50.0) -> np.ndarray:
    """Closed CCW square of side `size`, anchored at origin."""
    return np.array(
        [[0, 0], [size, 0], [size, size], [0, size], [0, 0]],
        dtype=float,
    )


def _annulus(outer: float = 50.0, inner: float = 15.0) -> list:
    """Square ring: outer square + hole."""
    half_out = outer / 2.0
    half_in = inner / 2.0
    outer_poly = np.array([
        [-half_out, -half_out],
        [ half_out, -half_out],
        [ half_out,  half_out],
        [-half_out,  half_out],
        [-half_out, -half_out],
    ], dtype=float)
    hole = np.array([
        [-half_in, -half_in],
        [ half_in, -half_in],
        [ half_in,  half_in],
        [-half_in,  half_in],
        [-half_in, -half_in],
    ], dtype=float)
    return [outer_poly, hole]


# ── Generic invariants ───────────────────────────────────────────────────────


def test_none_returns_empty():
    polys = generate_infill([_square()], Pattern.NONE, 1.0, 45.0)
    assert polys == []


def test_empty_input_returns_empty():
    assert generate_infill([], Pattern.LINEAR, 1.0, 45.0) == []


def test_nonpositive_spacing_returns_empty():
    assert generate_infill([_square()], Pattern.LINEAR, 0.0, 45.0) == []
    assert generate_infill([_square()], Pattern.LINEAR, -1.0, 45.0) == []


def test_from_string_tolerant():
    assert Pattern.from_string("linear") == Pattern.LINEAR
    assert Pattern.from_string("LINEAR") == Pattern.LINEAR
    assert Pattern.from_string(None) == Pattern.NONE
    assert Pattern.from_string("bogus") == Pattern.NONE


def test_density_to_spacing_inverse():
    # 100% density -> spacing == nozzle (solid fill)
    assert line_spacing_from_density(1.0, 0.4) == pytest.approx(0.4)
    # 20% density -> 5 * nozzle
    assert line_spacing_from_density(0.2, 0.4) == pytest.approx(2.0)
    # Density clamped above 1% to avoid runaway loops
    assert line_spacing_from_density(0.0, 0.4) == pytest.approx(40.0)
    assert line_spacing_from_density(2.0, 0.4) == pytest.approx(0.4)


# ── Per-pattern invariants ───────────────────────────────────────────────────


@pytest.mark.parametrize("pattern", [
    Pattern.LINEAR,
    Pattern.UNIDIRECTIONAL,
    Pattern.RECIPROCATING,
    Pattern.OFFSET,
    Pattern.Z_SHAPED,
    Pattern.PLANAR_SPIRAL,
])
def test_pattern_returns_polylines_inside_polygon(pattern):
    """Every generated point must lie inside (or near the boundary of) the
    input polygon, within a small numerical tolerance."""
    sq = _square(50.0)
    spacing = line_spacing_from_density(0.4, 0.4)
    polys = generate_infill([sq], pattern, spacing, 45.0, boundary_inset=0.0)
    assert len(polys) > 0, f"{pattern} produced no polylines"

    shp = _ShpPolygon([(p[0], p[1]) for p in sq])
    buffered = shp.buffer(1e-3)  # Allow tiny numeric drift
    for poly in polys:
        assert poly.shape[1] == 2
        for x, y in poly:
            assert buffered.contains(_ShpPolygon([
                (x, y), (x + 1e-6, y), (x, y + 1e-6),
            ]).representative_point()) or buffered.intersects(_ShpPolygon([
                (x, y), (x + 1e-6, y), (x, y + 1e-6),
            ]))


def test_linear_alternates_direction():
    """LINEAR returns segments where consecutive rows reverse direction."""
    sq = _square(50.0)
    polys = generate_infill([sq], Pattern.LINEAR, 5.0, 0.0)  # horizontal
    assert len(polys) >= 3
    # Each polyline is a 2-point segment.
    for p in polys:
        assert p.shape == (2, 2)
    # Direction of segments alternates row-by-row.
    dx0 = polys[0][1, 0] - polys[0][0, 0]
    dx1 = polys[1][1, 0] - polys[1][0, 0]
    assert np.sign(dx0) != np.sign(dx1)


def test_unidirectional_same_direction():
    """UNIDIRECTIONAL returns segments all oriented the same way."""
    sq = _square(50.0)
    polys = generate_infill([sq], Pattern.UNIDIRECTIONAL, 5.0, 0.0)
    assert len(polys) >= 3
    signs = [np.sign(p[1, 0] - p[0, 0]) for p in polys]
    assert len(set(signs)) == 1  # all same sign


def test_reciprocating_single_polyline():
    """RECIPROCATING returns exactly one continuous polyline."""
    sq = _square(50.0)
    polys = generate_infill([sq], Pattern.RECIPROCATING, 5.0, 45.0)
    assert len(polys) == 1
    assert polys[0].shape[0] >= 4  # at least two rows worth of points


def test_z_shaped_single_polyline_with_more_points_than_reciprocating():
    """Z_SHAPED adds extra connector midpoints over RECIPROCATING."""
    sq = _square(50.0)
    recip = generate_infill([sq], Pattern.RECIPROCATING, 5.0, 45.0)
    zsh = generate_infill([sq], Pattern.Z_SHAPED, 5.0, 45.0)
    assert len(zsh) == 1
    assert zsh[0].shape[0] > recip[0].shape[0]


def test_offset_rings_shrink_monotonically():
    """OFFSET produces concentric rings; each subsequent ring has smaller
    bounding-box diagonal than the previous one."""
    sq = _square(50.0)
    polys = generate_infill([sq], Pattern.OFFSET, 5.0, 0.0)
    assert len(polys) >= 2
    prev_diag = float("inf")
    for ring in polys:
        diag = np.linalg.norm(ring.max(axis=0) - ring.min(axis=0))
        assert diag < prev_diag + 1e-6
        prev_diag = diag


def test_planar_spiral_is_single_continuous_polyline():
    """PLANAR_SPIRAL returns exactly one polyline."""
    sq = _square(50.0)
    polys = generate_infill([sq], Pattern.PLANAR_SPIRAL, 5.0, 0.0)
    assert len(polys) == 1
    assert polys[0].shape[0] >= 8


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_polygon_smaller_than_spacing_returns_empty():
    tiny = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], dtype=float)
    polys = generate_infill([tiny], Pattern.LINEAR, 10.0, 45.0)
    assert polys == []


def test_degenerate_polygon_skipped():
    line = np.array([[0, 0], [10, 0], [0, 0]], dtype=float)  # zero area
    polys = generate_infill([line], Pattern.LINEAR, 1.0, 45.0)
    assert polys == []


def test_annulus_respects_hole():
    """Infill inside an annulus should produce points only in the ring, never
    inside the hole."""
    closed = _annulus(50.0, 20.0)
    polys = generate_infill(closed, Pattern.LINEAR, 3.0, 0.0)
    assert len(polys) > 0
    # No point should lie strictly inside the hole.
    half_in = 10.0 - 1e-3
    for poly in polys:
        for x, y in poly:
            inside_hole = (-half_in < x < half_in) and (-half_in < y < half_in)
            assert not inside_hole, f"point {(x, y)} fell inside the hole"


def test_boundary_inset_keeps_lines_away_from_edge():
    sq = _square(50.0)
    inset = 2.0
    polys = generate_infill([sq], Pattern.LINEAR, 3.0, 0.0, boundary_inset=inset)
    assert len(polys) > 0
    for poly in polys:
        xs = poly[:, 0]
        ys = poly[:, 1]
        # Y stays inside [inset, 50 - inset] (horizontal rasters).
        assert ys.min() >= inset - 1e-6
        assert ys.max() <= 50.0 - inset + 1e-6
