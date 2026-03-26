#!/usr/bin/env python3
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
"""Simple planar STL slicer that generates G-code for ur_3d_printer testing."""

import argparse
import math
import struct
import sys
from collections import defaultdict

import numpy as np


# ── STL loading ──────────────────────────────────────────────────────────────

def load_stl(path):
    """Load binary or ASCII STL, return (N,3,3) array of triangle vertices."""
    with open(path, 'rb') as f:
        header = f.read(80)
        raw = f.read()

    # Try binary first
    try:
        count = struct.unpack('<I', raw[:4])[0]
        expected_size = 4 + count * 50
        if len(raw) >= expected_size:
            dt = np.dtype([
                ('normal', '<f4', 3),
                ('v0', '<f4', 3),
                ('v1', '<f4', 3),
                ('v2', '<f4', 3),
                ('attr', '<u2'),
            ])
            data = np.frombuffer(raw[:expected_size], dtype=dt, offset=4)
            return np.stack([data['v0'], data['v1'], data['v2']], axis=1)
    except Exception:
        pass

    # ASCII STL fallback
    text = header.decode('ascii', errors='replace') + raw.decode('ascii', errors='replace')
    tris = []
    tri = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('vertex '):
            parts = line.split()
            tri.append([float(parts[1]), float(parts[2]), float(parts[3])])
            if len(tri) == 3:
                tris.append(tri)
                tri = []
    return np.array(tris, dtype=np.float32)


# ── Slicing ───────────────────────────────────────────────────────────────────

def slice_at_z(triangles, z):
    """
    Intersect all triangles with horizontal plane at given z.

    Returns list of (p0, p1) segment pairs as 2D numpy arrays.
    """
    segments = []
    v = triangles  # shape (N, 3, 3): [tri, vertex, xyz]
    zv = v[:, :, 2]  # z coordinates per vertex, shape (N, 3)

    # Triangles that straddle the plane
    above = zv > z
    below = ~above
    crossing = ~(above.all(axis=1) | below.all(axis=1))
    cross_tris = v[crossing]
    cross_zv = zv[crossing]
    cross_above = above[crossing]

    for tri, zs, ab in zip(cross_tris, cross_zv, cross_above):
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            if ab[i] != ab[j]:
                dz = zs[j] - zs[i]
                if abs(dz) < 1e-12:
                    continue
                t = (z - zs[i]) / dz
                p = tri[i] + t * (tri[j] - tri[i])
                pts.append(p[:2])
        if len(pts) == 2:
            segments.append((pts[0], pts[1]))

    return segments


def connect_segments(segments, tol=1e-3):
    """
    Stitch unordered line segments into closed polygon chains.

    Returns list of polylines (each a list of 2D points).
    Each polygon is guaranteed to be closed (last point == first point
    within tolerance).
    """
    if not segments:
        return []

    # Build a spatial lookup: grid cell -> list of (seg_idx, which_end)
    grid = defaultdict(list)

    def key(pt):
        return (round(pt[0] / tol), round(pt[1] / tol))

    segs = list(segments)  # [(p0, p1), ...]
    used = [False] * len(segs)

    for i, (p0, p1) in enumerate(segs):
        grid[key(p0)].append((i, 0))
        grid[key(p1)].append((i, 1))

    def find_next(pt, exclude_idx):
        """Find an unused segment that starts or ends near pt."""
        k = key(pt)
        # Search the grid cell and its 8 neighbors for robustness
        for dk0 in (-1, 0, 1):
            for dk1 in (-1, 0, 1):
                neighbor_key = (k[0] + dk0, k[1] + dk1)
                for idx, end in grid.get(neighbor_key, []):
                    if not used[idx] and idx != exclude_idx:
                        # Verify actual distance within tolerance
                        match_pt = segs[idx][end]
                        if (abs(match_pt[0] - pt[0]) < tol and
                                abs(match_pt[1] - pt[1]) < tol):
                            return idx, end
        return None, None

    polygons = []

    for start in range(len(segs)):
        if used[start]:
            continue
        used[start] = True
        p0, p1 = segs[start]
        chain = [p0, p1]

        while True:
            # Find next segment connecting to the end of the chain
            next_idx, next_end = find_next(chain[-1], start if len(chain) == 2 else -1)
            if next_idx is None:
                break
            used[next_idx] = True
            np0, np1 = segs[next_idx]
            # Append the far end of the matched segment
            if next_end == 0:
                chain.append(np1)
            else:
                chain.append(np0)
            # Check if we've closed the loop back to the start
            if np.linalg.norm(np.array(chain[-1]) - np.array(chain[0])) < tol * 2:
                break

        if len(chain) >= 3:
            # Ensure polygon is explicitly closed
            if np.linalg.norm(np.array(chain[-1]) - np.array(chain[0])) > tol * 2:
                chain.append(chain[0])
            polygons.append(chain)

    return polygons


# ── G-code generation ─────────────────────────────────────────────────────────

def to_gcode(
    triangles,
    layer_height=1.0,
    nozzle_d=0.4,
    filament_d=1.75,
    print_speed=3000,  # mm/min
    travel_speed=9000,
    center_xy=True,
    scale=1.0,
):
    """Slice the STL and return G-code as a string."""
    if scale != 1.0:
        triangles = triangles * scale

    verts = triangles.reshape(-1, 3)
    z_min = verts[:, 2].min()
    z_max = verts[:, 2].max()
    x_c = (verts[:, 0].min() + verts[:, 0].max()) / 2
    y_c = (verts[:, 1].min() + verts[:, 1].max()) / 2

    if center_xy:
        triangles[:, :, 0] -= x_c
        triangles[:, :, 1] -= y_c
        # Recompute verts after centering
        verts = triangles.reshape(-1, 3)

    # Shift so z_min == 0
    triangles[:, :, 2] -= z_min
    z_max -= z_min
    z_min = 0.0

    # Layer heights (slice at mid-layer)
    z_levels = np.arange(layer_height / 2, z_max, layer_height)
    total_layers = len(z_levels)

    filament_area = math.pi * (filament_d / 2) ** 2
    extrude_per_mm = (nozzle_d * layer_height) / filament_area

    lines = [
        "; G-code generated by ur_3d_printer/resource/stl_slicer.py",
        f"; Source: chair.stl  ({len(triangles)} triangles)",
        f"; Layers: {total_layers}  Layer height: {layer_height:.2f}mm",
        f"; Print area: {verts[:, 0].ptp():.1f} x {verts[:, 1].ptp():.1f} x {z_max:.1f} mm",
        "G90 ; absolute positioning",
        "G21 ; millimetre units",
        "M82 ; absolute extrusion",
        "G92 E0 ; reset extruder",
        f"G0 Z{layer_height:.3f} F600 ; lift to first layer",
        "",
    ]

    e = 0.0

    for layer_idx, z in enumerate(z_levels):
        segs = slice_at_z(triangles, z)
        polys = connect_segments(segs, tol=0.01)

        # Sort polygons largest-first so the outer perimeter is first
        polys.sort(key=lambda p: -len(p))

        if not polys:
            continue

        lines.append(f"; LAYER:{layer_idx}")
        lines.append(f"; Z:{z:.3f}")
        lines.append(f"G0 Z{z:.3f} F600")

        for poly in polys:
            if len(poly) < 3:
                continue

            start = np.array(poly[0])
            # Travel move to start of contour
            lines.append(
                f"G0 X{start[0]:.3f} Y{start[1]:.3f} F{travel_speed}"
            )

            prev = start.copy()
            for pt in poly[1:]:
                curr = np.array(pt)
                d = np.linalg.norm(curr - prev)
                if d < 1e-4:
                    continue
                e += d * extrude_per_mm
                lines.append(
                    f"G1 X{curr[0]:.3f} Y{curr[1]:.3f} E{e:.5f} F{print_speed}"
                )
                prev = curr

            # Close contour: always extrude back to start point
            # This ensures each layer perimeter is fully closed
            d = np.linalg.norm(start - prev)
            if d > nozzle_d * 0.5:
                e += d * extrude_per_mm
                lines.append(
                    f"G1 X{start[0]:.3f} Y{start[1]:.3f} E{e:.5f} F{print_speed}"
                )

        if layer_idx % 10 == 0:
            print(f"  Sliced layer {layer_idx+1}/{total_layers} z={z:.2f}mm "
                  f"({len(polys)} contours)", file=sys.stderr)

    lines.append("; END OF PRINT")
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Slice STL to G-code")
    parser.add_argument("stl", help="Input STL file")
    parser.add_argument(
        "-o", "--output", default=None, help="Output G-code file (default: stdout)"
    )
    parser.add_argument("--layer-height", type=float, default=1.0, help="Layer height mm")
    parser.add_argument("--nozzle", type=float, default=0.4, help="Nozzle diameter mm")
    parser.add_argument("--scale", type=float, default=1.0, help="Scale factor")
    parser.add_argument("--print-speed", type=int, default=3000, help="Print speed mm/min")
    args = parser.parse_args()

    print(f"Loading {args.stl}...", file=sys.stderr)
    tris = load_stl(args.stl)
    print(f"  {len(tris)} triangles loaded", file=sys.stderr)

    verts = tris.reshape(-1, 3)
    print(f"  Bounding box: "
          f"X[{verts[:, 0].min():.1f}, {verts[:, 0].max():.1f}] "
          f"Y[{verts[:, 1].min():.1f}, {verts[:, 1].max():.1f}] "
          f"Z[{verts[:, 2].min():.1f}, {verts[:, 2].max():.1f}] mm",
          file=sys.stderr)

    print(f"Slicing at {args.layer_height}mm layers...", file=sys.stderr)
    gcode = to_gcode(
        tris,
        layer_height=args.layer_height,
        nozzle_d=args.nozzle,
        scale=args.scale,
        print_speed=args.print_speed,
    )

    if args.output:
        with open(args.output, 'w') as f:
            f.write(gcode)
        print(f"Wrote {args.output} ({len(gcode)//1024} KB, "
              f"{gcode.count(chr(10))} lines)", file=sys.stderr)
    else:
        print(gcode)


if __name__ == "__main__":
    main()
