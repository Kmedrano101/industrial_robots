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
"""
Infill Pattern Generation.

Generates 2D fill polylines inside closed slice contours. The slicer
re-attaches z (and surface normals for multi-axis) when consuming the
output.

Supported patterns:

    NONE            -> no infill
    LINEAR          -> parallel rasters, alternating direction per row
    UNIDIRECTIONAL  -> parallel rasters, all rows oriented same way
    RECIPROCATING   -> single continuous zig-zag polyline
    OFFSET          -> concentric inward rings (contour-following)
    Z_SHAPED        -> zig-zag with diagonal Z-shaped connectors
    PLANAR_SPIRAL   -> single inward spiral derived from concentric offsets

Returns a list of polylines. Each polyline is a numpy array (M, 2) of
(x, y) points representing one continuous extrusion stroke. The slicer is
responsible for travel (non-extruding) moves between polylines.

This module requires shapely. If shapely is unavailable the module logs a
warning at import time and `generate_infill` returns an empty list.
"""

from __future__ import annotations

import logging
import math
from enum import Enum
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    from shapely.affinity import rotate as _shp_rotate
    from shapely.geometry import LineString, MultiPolygon, Point, Polygon
    SHAPELY_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency missing
    SHAPELY_AVAILABLE = False
    logger.warning(
        "shapely not installed; infill patterns disabled. "
        "Install with: pip install shapely"
    )


# ── Public API ───────────────────────────────────────────────────────────────


class Pattern(str, Enum):
    """Infill pattern identifiers (string-valued for easy JSON transport)."""

    NONE = "none"
    LINEAR = "linear"
    UNIDIRECTIONAL = "unidirectional"
    RECIPROCATING = "reciprocating"
    OFFSET = "offset"
    Z_SHAPED = "z_shaped"
    PLANAR_SPIRAL = "planar_spiral"

    @classmethod
    def from_string(cls, value) -> "Pattern":
        """Tolerant parser. Unknown values map to NONE."""
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.NONE
        try:
            return cls(str(value).lower())
        except ValueError:
            logger.warning("Unknown infill pattern %r; falling back to NONE", value)
            return cls.NONE


def line_spacing_from_density(density: float, nozzle_diameter: float) -> float:
    """Convert infill density (0..1) into center-to-center line spacing.

    100% density -> spacing == nozzle_diameter (solid fill).
    20% density  -> spacing == 5 * nozzle_diameter.
    Clamped to (0.01, 1.0] to avoid zero-division and pathological values.
    """
    d = max(min(float(density), 1.0), 0.01)
    return float(nozzle_diameter) / d


def generate_infill(
    closed_contours: List[np.ndarray],
    pattern: Pattern,
    line_spacing: float,
    angle_deg: float = 45.0,
    layer_index: int = 0,
    boundary_inset: float = 0.0,
) -> List[np.ndarray]:
    """Generate infill polylines inside the closed contours.

    Args:
        closed_contours: List of (N, 2) or (N, 3) numpy arrays. Only XY is
            consumed. Each input must be an explicitly closed loop
            (last point == first point).
        pattern: Which pattern to generate.
        line_spacing: Center-to-center distance between adjacent infill
            lines (same units as the contours, typically mm).
        angle_deg: Raster angle in degrees (line-based patterns only).
        layer_index: Layer index; reserved for callers that want to vary
            the raster angle per layer outside this module.
        boundary_inset: Shrink the polygon inward by this distance before
            generating infill (typically nozzle_diameter / 2 to leave room
            for the perimeter wall). 0 disables.

    Returns:
        List of (M, 2) polylines. Empty list if pattern is NONE, shapely
        is unavailable, or no fill geometry could be produced.
    """
    if pattern == Pattern.NONE or not closed_contours:
        return []
    if not SHAPELY_AVAILABLE:
        return []
    if line_spacing <= 0:
        return []

    mp = _classify_holes(closed_contours)
    if mp is None or mp.is_empty:
        return []

    polylines: List[np.ndarray] = []
    for poly in mp.geoms:
        if boundary_inset > 0:
            shrunk = poly.buffer(-boundary_inset, join_style=2)
            if shrunk.is_empty:
                continue
            for sub in _as_polygons(shrunk):
                polylines.extend(_dispatch(sub, pattern, line_spacing, angle_deg))
        else:
            polylines.extend(_dispatch(poly, pattern, line_spacing, angle_deg))
    return polylines


# ── Dispatch ─────────────────────────────────────────────────────────────────


def _dispatch(poly: "Polygon", pattern: Pattern, spacing: float, angle: float) -> List[np.ndarray]:
    if pattern == Pattern.LINEAR:
        return _pattern_linear(poly, spacing, angle)
    if pattern == Pattern.UNIDIRECTIONAL:
        return _pattern_unidirectional(poly, spacing, angle)
    if pattern == Pattern.RECIPROCATING:
        return _pattern_reciprocating(poly, spacing, angle)
    if pattern == Pattern.OFFSET:
        return _pattern_offset(poly, spacing)
    if pattern == Pattern.Z_SHAPED:
        return _pattern_z_shaped(poly, spacing, angle)
    if pattern == Pattern.PLANAR_SPIRAL:
        return _pattern_planar_spiral(poly, spacing)
    return []


# ── Hole classification ──────────────────────────────────────────────────────


def _classify_holes(closed_polys: List[np.ndarray]):
    """Turn unordered closed 2D contours into a `MultiPolygon` with holes.

    Each input is a (N, k>=2) numpy array forming a closed loop. Nesting is
    decided by signed-area parity inside the largest enclosing exterior.
    """
    valids: List["Polygon"] = []
    for poly in closed_polys:
        arr = np.asarray(poly)
        if arr.ndim != 2 or arr.shape[0] < 4 or arr.shape[1] < 2:
            continue
        coords = [(float(p[0]), float(p[1])) for p in arr]
        try:
            p = Polygon(coords)
            if not p.is_valid:
                p = p.buffer(0)
                if p.is_empty or not p.is_valid:
                    continue
            if isinstance(p, MultiPolygon):
                valids.extend(g for g in p.geoms if g.area > 1e-9)
            elif p.area > 1e-9:
                valids.append(p)
        except Exception:
            continue
    if not valids:
        return None

    valids.sort(key=lambda g: -g.area)

    exteriors: List[Tuple["Polygon", List["Polygon"]]] = []
    for p in valids:
        nested = False
        for ex, holes in exteriors:
            if ex.contains(p.representative_point()):
                # Inside this exterior; check if any already-recorded hole
                # contains it (then it's an island inside a hole -> treat as
                # its own exterior).
                in_hole = any(h.contains(p.representative_point()) for h in holes)
                if in_hole:
                    continue
                holes.append(p)
                nested = True
                break
        if not nested:
            exteriors.append((p, []))

    out: List["Polygon"] = []
    for ex, holes in exteriors:
        try:
            built = Polygon(
                list(ex.exterior.coords),
                [list(h.exterior.coords) for h in holes],
            )
            if built.is_valid and built.area > 1e-9:
                out.append(built)
            else:
                fixed = built.buffer(0)
                if not fixed.is_empty and fixed.is_valid:
                    out.extend(_as_polygons(fixed))
        except Exception:
            continue
    return MultiPolygon(out) if out else None


def _as_polygons(geom) -> List["Polygon"]:
    if isinstance(geom, Polygon):
        return [geom] if not geom.is_empty else []
    if isinstance(geom, MultiPolygon):
        return [g for g in geom.geoms if not g.is_empty]
    return []


# ── Raster helper ────────────────────────────────────────────────────────────


def _raster_segments(
    poly: "Polygon",
    line_spacing: float,
    angle_deg: float,
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Compute parallel-line clipping against the polygon.

    Returns an ordered list of (p0, p1) endpoints in walking order with
    alternating direction per row so consecutive endpoints sit on adjacent
    rows. Multiple segments per row (concave / holed polygons) are sorted
    left-to-right within the row.
    """
    centroid = poly.centroid
    rotated = _shp_rotate(poly, -angle_deg, origin=centroid)
    minx, miny, maxx, maxy = rotated.bounds
    height = maxy - miny
    if height <= 0:
        return []
    n_lines = int(math.floor(height / line_spacing))
    if n_lines < 1:
        return []
    # Center the line band inside the bounding box.
    y0 = miny + (height - (n_lines - 1) * line_spacing) / 2.0

    segs_rot: List[Tuple[np.ndarray, np.ndarray]] = []
    for i in range(n_lines):
        y = y0 + i * line_spacing
        scan = LineString([(minx - 1.0, y), (maxx + 1.0, y)])
        clipped = scan.intersection(rotated)
        if clipped.is_empty:
            continue
        row_segs: List[Tuple[np.ndarray, np.ndarray]] = []
        if clipped.geom_type == "LineString":
            cs = list(clipped.coords)
            if len(cs) >= 2:
                row_segs.append((np.array(cs[0]), np.array(cs[-1])))
        elif clipped.geom_type == "MultiLineString":
            for line in clipped.geoms:
                cs = list(line.coords)
                if len(cs) >= 2:
                    row_segs.append((np.array(cs[0]), np.array(cs[-1])))
        else:
            continue
        row_segs.sort(key=lambda s: s[0][0])
        if i % 2 == 1:
            row_segs = [(b, a) for (a, b) in reversed(row_segs)]
        segs_rot.extend(row_segs)

    cos_a = math.cos(math.radians(angle_deg))
    sin_a = math.sin(math.radians(angle_deg))
    cx, cy = centroid.x, centroid.y
    out: List[Tuple[np.ndarray, np.ndarray]] = []
    for a, b in segs_rot:
        out.append((_rotate_xy(a, cos_a, sin_a, cx, cy),
                    _rotate_xy(b, cos_a, sin_a, cx, cy)))
    return out


def _rotate_xy(p: np.ndarray, cos_a: float, sin_a: float, cx: float, cy: float) -> np.ndarray:
    x, y = float(p[0]) - cx, float(p[1]) - cy
    return np.array([cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a])


# ── Patterns ─────────────────────────────────────────────────────────────────


def _pattern_linear(poly: "Polygon", spacing: float, angle: float) -> List[np.ndarray]:
    """Parallel rasters as independent polylines; direction alternates per row.

    The slicer must travel (non-extruding) between consecutive polylines.
    """
    segs = _raster_segments(poly, spacing, angle)
    return [np.array([a, b]) for a, b in segs]


def _pattern_unidirectional(poly: "Polygon", spacing: float, angle: float) -> List[np.ndarray]:
    """Parallel rasters all oriented in the same direction."""
    segs = _raster_segments(poly, spacing, angle)
    if not segs:
        return []
    # Normalize: each segment goes in the direction of `angle`. Project the
    # endpoints onto the raster axis and order so the lower-projection point
    # is first.
    ux = math.cos(math.radians(angle))
    uy = math.sin(math.radians(angle))
    out: List[np.ndarray] = []
    for a, b in segs:
        if (a[0] * ux + a[1] * uy) > (b[0] * ux + b[1] * uy):
            a, b = b, a
        out.append(np.array([a, b]))
    return out


def _pattern_reciprocating(poly: "Polygon", spacing: float, angle: float) -> List[np.ndarray]:
    """Single continuous zig-zag polyline."""
    segs = _raster_segments(poly, spacing, angle)
    if not segs:
        return []
    pts: List[np.ndarray] = [segs[0][0].copy()]
    for a, b in segs:
        if np.linalg.norm(pts[-1] - a) > 1e-9:
            pts.append(a.copy())
        pts.append(b.copy())
    return [np.array(pts)]


def _pattern_offset(poly: "Polygon", spacing: float) -> List[np.ndarray]:
    """Concentric inward offsets until the polygon collapses.

    Returns each ring (exterior + any inner holes) as its own polyline. The
    outermost ring is offset by `spacing` inward from the polygon boundary
    so it never overlaps the perimeter wall.
    """
    rings: List[np.ndarray] = []
    distance = spacing
    # Safety cap: a polygon of diameter D can be offset at most ~D/(2*spacing)
    # times before disappearing. Cap at 200 to avoid pathological loops.
    for _ in range(200):
        shrunk = poly.buffer(-distance, join_style=2)
        if shrunk.is_empty:
            break
        for g in _as_polygons(shrunk):
            ext = np.array(g.exterior.coords)
            if len(ext) >= 4:
                rings.append(ext)
            for interior in g.interiors:
                arr = np.array(interior.coords)
                if len(arr) >= 4:
                    rings.append(arr)
        distance += spacing
    return rings


def _pattern_z_shaped(poly: "Polygon", spacing: float, angle: float) -> List[np.ndarray]:
    """Continuous zig-zag with diagonal Z-shaped connectors between rows.

    Compared to RECIPROCATING (which turns flush against the polygon edge),
    this pattern inserts an extra waypoint offset along the raster axis so
    the bend takes a diagonal "Z" shape — easier to print at high speed and
    reduces stress concentration at boundary contact points.

    Connector midpoints that would fall outside the polygon are pulled back
    toward the segment midpoint until they sit inside.
    """
    segs = _raster_segments(poly, spacing, angle)
    if not segs:
        return []
    ux = math.cos(math.radians(angle))
    uy = math.sin(math.radians(angle))
    pts: List[np.ndarray] = [segs[0][0].copy()]
    for idx, (a, b) in enumerate(segs):
        if idx > 0:
            prev_end = pts[-1]
            base_mid = 0.5 * (prev_end + a)
            # Step half-spacing back along the raster axis (sign alternates).
            sign = 1.0 if idx % 2 == 1 else -1.0
            offset_vec = sign * 0.5 * spacing * np.array([ux, uy])
            mid = base_mid + offset_vec
            # If the offset midpoint would leave the polygon, shrink it.
            # Try a few smaller offsets, then fall back to the plain midpoint.
            if not poly.contains(Point(mid[0], mid[1])):
                for shrink in (0.5, 0.25, 0.0):
                    candidate = base_mid + offset_vec * shrink
                    if poly.contains(Point(candidate[0], candidate[1])):
                        mid = candidate
                        break
                else:
                    mid = base_mid
            pts.append(mid)
            pts.append(a.copy())
        pts.append(b.copy())
    return [np.array(pts)]


def _pattern_planar_spiral(poly: "Polygon", spacing: float) -> List[np.ndarray]:
    """Single inward planar spiral approximated by chained concentric rings.

    For each pair of consecutive rings, the next ring is rotated so it
    starts at the vertex closest to the previous ring's last point. This
    keeps inter-ring transitions short and continuous, approximating a
    smooth spiral curve.
    """
    rings = _pattern_offset(poly, spacing)
    if not rings:
        return []
    pts: List[np.ndarray] = [np.array(p) for p in rings[0]]
    for ring in rings[1:]:
        diffs = ring - pts[-1]
        dists = np.einsum("ij,ij->i", diffs, diffs)
        start = int(np.argmin(dists))
        # Roll the ring so it starts at the nearest vertex; drop the duplicate
        # closing point before re-appending the rotated start so the polyline
        # stays linearized.
        ring_open = ring[:-1] if np.linalg.norm(ring[0] - ring[-1]) < 1e-9 else ring
        rolled = np.concatenate([ring_open[start:], ring_open[:start + 1]])
        for p in rolled:
            pts.append(np.array(p))
    return [np.array(pts)]
