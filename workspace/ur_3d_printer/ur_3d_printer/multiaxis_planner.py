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
Multi-Axis Toolpath Planner

Generates non-planar toolpaths where the robot nozzle orientation varies
to follow surface normals, enabling:

  - Overhang printing without support material
  - Curved-layer deposition for smoother surfaces
  - Complex geometry impossible with conventional 3-axis printers

Integrates self-collision checking to ensure all configurations are safe.

No ROS dependencies — pure Python + NumPy.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import struct

import numpy as np

from .toolpath import Waypoint, Layer, Toolpath
from .collision_checker import SelfCollisionChecker

try:
    from .infill import (
        Pattern as _InfillPattern,
        generate_infill as _generate_infill,
        line_spacing_from_density as _line_spacing_from_density,
    )
    _INFILL_AVAILABLE = True
except ImportError:  # pragma: no cover - shapely missing
    _InfillPattern = None
    _generate_infill = None
    _line_spacing_from_density = None
    _INFILL_AVAILABLE = False


# ── Configuration ────────────────────────────────────────────────────────────

@dataclass
class MultiAxisConfig:
    """Configuration for multi-axis toolpath generation."""

    layer_height: float = 0.001             # 1 mm (metres)
    nozzle_diameter: float = 0.0004         # 0.4 mm
    max_tilt_angle: float = np.radians(45)  # max nozzle tilt from vertical
    tilt_smoothing_window: int = 5          # smooth orientations over N wps
    enable_collision_check: bool = True
    collision_safety_margin: float = 0.02   # 2 cm
    robot_model: str = 'ur5e'
    waypoint_spacing: float = 0.002         # 2 mm between waypoints
    print_speed: float = 0.05              # 50 mm/s
    travel_speed: float = 0.15             # 150 mm/s

    # Infill (none = perimeter-only, same as before)
    infill_pattern: str = 'none'
    infill_density: float = 0.2             # 0..1 (1.0 = solid fill)
    infill_angle_base: float = 45.0         # degrees
    infill_angle_increment: float = 90.0    # degrees per layer


# ── Mesh Data ────────────────────────────────────────────────────────────────

@dataclass
class MeshTriangle:
    """A triangle from an STL mesh with vertex positions in metres."""

    vertices: np.ndarray   # (3, 3)
    normal: np.ndarray     # (3,)


# ── STL I/O ──────────────────────────────────────────────────────────────────

def load_stl_mesh(filepath: str) -> List[MeshTriangle]:
    """Load an STL file (binary or ASCII), converting mm to metres.

    Returns list of MeshTriangle objects.
    """
    with open(filepath, 'rb') as f:
        header = f.read(80)

    try:
        header_str = header.decode('ascii', errors='ignore')
        is_ascii = header_str.strip().lower().startswith('solid')
    except Exception:
        is_ascii = False

    # Binary heuristic: if "solid" appears but the file size matches
    # binary format, prefer binary.
    if is_ascii:
        try:
            return _load_stl_ascii(filepath)
        except Exception:
            return _load_stl_binary(filepath)
    return _load_stl_binary(filepath)


def _load_stl_binary(filepath: str) -> List[MeshTriangle]:
    triangles: List[MeshTriangle] = []
    with open(filepath, 'rb') as f:
        f.read(80)  # header
        num_tris = struct.unpack('<I', f.read(4))[0]

        for _ in range(num_tris):
            normal = np.array(struct.unpack('<3f', f.read(12)), dtype=np.float64)
            v0 = np.array(struct.unpack('<3f', f.read(12)), dtype=np.float64)
            v1 = np.array(struct.unpack('<3f', f.read(12)), dtype=np.float64)
            v2 = np.array(struct.unpack('<3f', f.read(12)), dtype=np.float64)
            f.read(2)  # attribute byte count

            vertices = np.array([v0, v1, v2]) * 0.001  # mm → m
            norm_len = np.linalg.norm(normal)
            if norm_len > 1e-10:
                normal = normal / norm_len

            triangles.append(MeshTriangle(vertices=vertices, normal=normal))

    return triangles


def _load_stl_ascii(filepath: str) -> List[MeshTriangle]:
    triangles: List[MeshTriangle] = []
    with open(filepath, 'r') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('facet normal'):
            parts = line.split()
            normal = np.array(
                [float(parts[2]), float(parts[3]), float(parts[4])],
                dtype=np.float64,
            )
            norm_len = np.linalg.norm(normal)
            if norm_len > 1e-10:
                normal /= norm_len

            i += 2  # skip 'outer loop'
            verts = []
            for _ in range(3):
                vline = lines[i].strip().split()
                verts.append([float(vline[1]), float(vline[2]), float(vline[3])])
                i += 1

            vertices = np.array(verts, dtype=np.float64) * 0.001
            triangles.append(MeshTriangle(vertices=vertices, normal=normal))
            i += 2  # skip 'endloop', 'endfacet'
        else:
            i += 1

    return triangles


# ── Orientation Helpers ──────────────────────────────────────────────────────

def _rotate_vector(v: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    """Rodrigues' rotation: rotate *v* around *axis* by *angle* radians."""
    ca, sa = np.cos(angle), np.sin(angle)
    return v * ca + np.cross(axis, v) * sa + axis * np.dot(axis, v) * (1 - ca)


def nozzle_down_orientation() -> np.ndarray:
    """Standard nozzle-down orientation (Z-axis points -Z world)."""
    return np.array([
        [1.0,  0.0,  0.0],
        [0.0, -1.0,  0.0],
        [0.0,  0.0, -1.0],
    ])


def orientation_from_normal(
    surface_normal: np.ndarray,
    max_tilt: float = np.radians(45),
) -> np.ndarray:
    """Build a nozzle rotation matrix from a surface outward normal.

    The nozzle Z-axis is set opposite to the surface normal (pointing
    into the surface).  The tilt is clamped to *max_tilt* from vertical.

    Returns 3x3 rotation matrix.
    """
    # Desired nozzle approach: opposite to outward normal.
    approach = -surface_normal.copy()

    # Clamp tilt relative to straight down.
    vertical = np.array([0.0, 0.0, -1.0])
    cos_angle = np.clip(np.dot(approach, vertical), -1.0, 1.0)
    angle = np.arccos(cos_angle)

    if angle > max_tilt:
        axis = np.cross(vertical, approach)
        axis_len = np.linalg.norm(axis)
        if axis_len < 1e-10:
            approach = vertical.copy()
        else:
            axis /= axis_len
            approach = _rotate_vector(vertical, axis, max_tilt)

    # Build rotation matrix with Z = approach.
    z_axis = approach / (np.linalg.norm(approach) + 1e-15)

    x_candidate = np.array([1.0, 0.0, 0.0]) if abs(z_axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    y_axis = np.cross(z_axis, x_candidate)
    y_axis /= (np.linalg.norm(y_axis) + 1e-15)
    x_axis = np.cross(y_axis, z_axis)
    x_axis /= (np.linalg.norm(x_axis) + 1e-15)

    return np.column_stack([x_axis, y_axis, z_axis])


def interpolate_orientations(R1: np.ndarray, R2: np.ndarray, alpha: float) -> np.ndarray:
    """Linear blend of two rotation matrices with SVD re-orthogonalisation."""
    R_blend = (1.0 - alpha) * R1 + alpha * R2
    U, _, Vt = np.linalg.svd(R_blend)
    if np.linalg.det(U @ Vt) < 0:
        U[:, -1] *= -1
    return U @ Vt


def _precompute_mesh_arrays(
    triangles: List[MeshTriangle],
) -> Tuple[np.ndarray, np.ndarray]:
    """Precompute centroids and normals as (N,3) arrays for vectorized lookup."""
    centroids = np.array([np.mean(t.vertices, axis=0) for t in triangles])
    normals = np.array([t.normal for t in triangles])
    return centroids, normals


def compute_surface_normal_at_point(
    point: np.ndarray,
    triangles: List[MeshTriangle],
    search_radius: float = 0.01,
    _centroids: Optional[np.ndarray] = None,
    _normals: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Inverse-distance-weighted surface normal from nearby triangles.

    Pass _centroids and _normals from _precompute_mesh_arrays() to avoid
    recomputing them for every call.
    """
    if _centroids is None or _normals is None:
        _centroids, _normals = _precompute_mesh_arrays(triangles)

    diffs = _centroids - point
    dists = np.linalg.norm(diffs, axis=1)
    mask = dists < search_radius

    if not np.any(mask):
        return np.array([0.0, 0.0, 1.0])  # default: surface up

    nearby_normals = _normals[mask]
    nearby_dists = dists[mask]
    w = 1.0 / (nearby_dists + 1e-6)
    w /= w.sum()
    avg = np.sum(nearby_normals * w[:, np.newaxis], axis=0)
    norm_len = np.linalg.norm(avg)
    return avg / norm_len if norm_len > 1e-10 else np.array([0.0, 0.0, 1.0])


def smooth_orientations(
    waypoints: List[Waypoint],
    window_size: int = 5,
) -> List[Waypoint]:
    """Moving-average smoothing of nozzle approach directions.

    Prevents sudden orientation jumps that stress robot joints.
    """
    if len(waypoints) < window_size:
        return waypoints

    n = len(waypoints)
    half_w = window_size // 2

    z_axes = np.array([wp.orientation[:, 2] for wp in waypoints])
    smoothed_z = np.empty_like(z_axes)

    for i in range(n):
        lo = max(0, i - half_w)
        hi = min(n, i + half_w + 1)
        avg = z_axes[lo:hi].mean(axis=0)
        norm = np.linalg.norm(avg)
        smoothed_z[i] = avg / norm if norm > 1e-10 else z_axes[i]

    for i, wp in enumerate(waypoints):
        z = smoothed_z[i]
        x_cand = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        y = np.cross(z, x_cand)
        y /= (np.linalg.norm(y) + 1e-15)
        x = np.cross(y, z)
        x /= (np.linalg.norm(x) + 1e-15)
        wp.orientation = np.column_stack([x, y, z])

    return waypoints


# ── Multi-Axis Toolpath Generator ────────────────────────────────────────────

class MultiAxisToolpathGenerator:
    """Generate multi-axis toolpaths from STL meshes.

    Unlike conventional 3-axis printing (nozzle always vertical), this
    generator computes variable nozzle orientations based on the local
    surface geometry.  A self-collision checker validates that every
    proposed orientation is achievable without the robot hitting itself.
    """

    def __init__(self, config: Optional[MultiAxisConfig] = None):
        self.config = config or MultiAxisConfig()
        self.collision_checker: Optional[SelfCollisionChecker] = None
        if self.config.enable_collision_check:
            self.collision_checker = SelfCollisionChecker(
                robot_model=self.config.robot_model,
                safety_margin=self.config.collision_safety_margin,
            )

    def generate_from_stl(
        self,
        stl_filepath: str,
        print_frame: Optional[np.ndarray] = None,
    ) -> Toolpath:
        """Slice an STL mesh into a multi-axis Toolpath.

        Args:
            stl_filepath: Path to an STL file (units: mm).
            print_frame: 4x4 print-origin → robot-base transform.

        Returns:
            Toolpath with per-waypoint variable nozzle orientations.
        """
        triangles = load_stl_mesh(stl_filepath)

        if print_frame is None:
            print_frame = np.eye(4)

        # Precompute centroids + normals for vectorized lookup
        mesh_centroids, mesh_normals = _precompute_mesh_arrays(triangles)

        all_verts = np.vstack([t.vertices for t in triangles])
        z_min = float(all_verts[:, 2].min())
        z_max = float(all_verts[:, 2].max())

        layers: List[Layer] = []
        layer_idx = 0
        z = z_min + self.config.layer_height / 2.0

        while z <= z_max:
            wps = self._slice_layer(
                triangles, z, layer_idx,
                mesh_centroids=mesh_centroids,
                mesh_normals=mesh_normals,
            )
            if wps:
                layers.append(Layer(
                    index=layer_idx,
                    z_height=z,
                    layer_height=self.config.layer_height,
                    waypoints=wps,
                ))
                layer_idx += 1
            z += self.config.layer_height

        toolpath = Toolpath(
            layers=layers,
            print_frame=print_frame,
            metadata={
                'type': 'multi_axis',
                'source': stl_filepath,
                'layer_height_m': self.config.layer_height,
                'max_tilt_deg': float(np.degrees(self.config.max_tilt_angle)),
                'total_layers': len(layers),
            },
        )
        return toolpath

    # ── Collision-Aware Validation ───────────────────────────────────────

    def validate_toolpath_collisions(
        self,
        toolpath: Toolpath,
        ik_solver,
        seed: Optional[np.ndarray] = None,
    ) -> Tuple[Toolpath, Dict]:
        """Validate a multi-axis toolpath for self-collisions.

        For each waypoint the method:
          1. Solves IK with the given *ik_solver*.
          2. Checks the resulting configuration for self-collision.
          3. If a collision is detected, progressively reduces the nozzle
             tilt toward vertical until a collision-free solution is found.

        Args:
            toolpath: Toolpath to validate (modified in-place).
            ik_solver: Object with ``ik_levenberg_marquardt(T, seed, tol, n)``
                returning a result with ``.is_valid`` and ``.joints``.
            seed: Starting joint configuration (6,).

        Returns:
            (toolpath, report_dict) — the toolpath has orientations
            adjusted where collisions were detected.
        """
        if self.collision_checker is None:
            return toolpath, {'status': 'skipped', 'reason': 'disabled'}

        report: Dict = {
            'total_waypoints': 0,
            'collisions_detected': 0,
            'orientations_adjusted': 0,
            'unreachable': 0,
            'collision_free': True,
        }

        if seed is None:
            seed = np.zeros(6)
        current_seed = seed.copy()

        for layer in toolpath.layers:
            for wp in layer.waypoints:
                report['total_waypoints'] += 1

                T_target = wp.to_homogeneous()
                sol = ik_solver.ik_levenberg_marquardt(
                    T_target, current_seed, 1e-6, 100,
                )
                if not sol.is_valid:
                    report['unreachable'] += 1
                    continue

                q = sol.joints.copy()
                result = self.collision_checker.check_config(q)

                if result.has_collision:
                    report['collisions_detected'] += 1
                    resolved = self._try_reduce_tilt(
                        wp, ik_solver, current_seed,
                    )
                    if resolved is not None:
                        q = resolved
                        report['orientations_adjusted'] += 1
                    else:
                        report['collision_free'] = False

                current_seed = q

        return toolpath, report

    # ── Private Helpers ──────────────────────────────────────────────────

    def _try_reduce_tilt(self, wp, ik_solver, seed):
        """Progressively reduce tilt toward vertical until collision-free."""
        vertical = nozzle_down_orientation()
        for alpha in (0.25, 0.5, 0.75, 1.0):
            blended = interpolate_orientations(wp.orientation, vertical, alpha)
            T = np.eye(4)
            T[:3, :3] = blended
            T[:3, 3] = wp.position

            sol = ik_solver.ik_levenberg_marquardt(T, seed, 1e-6, 100)
            if not sol.is_valid:
                continue

            q = sol.joints.copy()
            check = self.collision_checker.check_config(q)
            if not check.has_collision:
                wp.orientation = blended
                return q
        return None

    def _slice_layer(
        self,
        triangles: List[MeshTriangle],
        z_height: float,
        layer_idx: int,
        mesh_centroids: Optional[np.ndarray] = None,
        mesh_normals: Optional[np.ndarray] = None,
    ) -> List[Waypoint]:
        """Intersect mesh at *z_height* and build oriented waypoints."""
        segments = self._intersect_plane(triangles, z_height)
        if not segments:
            return []

        contours = _order_segments(segments)
        waypoints: List[Waypoint] = []

        for contour in contours:
            dense = _densify_points(contour, self.config.waypoint_spacing)
            waypoints.extend(self._oriented_waypoints_from_points(
                dense, layer_idx, triangles, mesh_centroids, mesh_normals,
                line_number_start=0, is_infill=False,
            ))

        # ── Infill ──────────────────────────────────────────────────────
        if (
            _INFILL_AVAILABLE
            and self.config.infill_pattern
            and self.config.infill_pattern.lower() != 'none'
            and contours
        ):
            pattern = _InfillPattern.from_string(self.config.infill_pattern)
            if pattern != _InfillPattern.NONE:
                spacing = _line_spacing_from_density(
                    self.config.infill_density, self.config.nozzle_diameter,
                )
                angle = (
                    self.config.infill_angle_base
                    + self.config.infill_angle_increment * layer_idx
                )
                polylines = _generate_infill(
                    closed_contours=contours,
                    pattern=pattern,
                    line_spacing=spacing,
                    angle_deg=angle,
                    layer_index=layer_idx,
                    boundary_inset=self.config.nozzle_diameter / 2.0,
                )
                start_idx = len(waypoints)
                for poly in polylines:
                    if len(poly) < 2:
                        continue
                    # Re-attach z to make 3D points the surface-normal lookup
                    # expects.
                    pts3d = np.column_stack([poly, np.full(len(poly), z_height)])
                    # Densify within each polyline to honour waypoint_spacing.
                    dense = _densify_points(pts3d, self.config.waypoint_spacing)
                    waypoints.extend(self._oriented_waypoints_from_points(
                        dense, layer_idx, triangles, mesh_centroids, mesh_normals,
                        line_number_start=start_idx, is_infill=True,
                    ))
                    start_idx += len(dense)

        if waypoints:
            waypoints = smooth_orientations(
                waypoints, self.config.tilt_smoothing_window,
            )
        return waypoints

    def _oriented_waypoints_from_points(
        self,
        points: np.ndarray,
        layer_idx: int,
        triangles: List[MeshTriangle],
        mesh_centroids: Optional[np.ndarray],
        mesh_normals: Optional[np.ndarray],
        line_number_start: int = 0,
        is_infill: bool = False,
    ) -> List[Waypoint]:
        """Build oriented waypoints for a sequence of 3D points on the surface.

        The first point of the sequence is flagged as a travel move
        (non-extruding entry into the polyline). All subsequent points are
        extrusion moves with feed rate scaled by tilt.
        """
        out: List[Waypoint] = []
        for i, point in enumerate(points):
            normal = compute_surface_normal_at_point(
                point, triangles,
                search_radius=self.config.layer_height * 3,
                _centroids=mesh_centroids,
                _normals=mesh_normals,
            )
            orient = orientation_from_normal(
                normal, max_tilt=self.config.max_tilt_angle,
            )

            tilt = np.arccos(np.clip(abs(orient[2, 2]), 0.0, 1.0))
            tilt_factor = 1.0 - 0.3 * (tilt / (self.config.max_tilt_angle + 1e-9))
            feed = self.config.print_speed * tilt_factor

            extrusion_rate = (
                self.config.nozzle_diameter
                * self.config.layer_height
                * feed
            )

            out.append(Waypoint(
                position=point.copy(),
                orientation=orient,
                feed_rate=feed,
                extrusion_rate=extrusion_rate,
                is_travel=(i == 0),
                is_infill=is_infill,
                layer_index=layer_idx,
                line_number=line_number_start + i,
            ))
        return out

    @staticmethod
    def _intersect_plane(
        triangles: List[MeshTriangle],
        z: float,
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Intersect all triangles with a horizontal plane at *z*."""
        segments: List[Tuple[np.ndarray, np.ndarray]] = []
        for tri in triangles:
            verts = tri.vertices
            z_vals = verts[:, 2]
            if z_vals.min() > z or z_vals.max() < z:
                continue

            pts: List[np.ndarray] = []
            for i in range(3):
                j = (i + 1) % 3
                z0, z1 = verts[i, 2], verts[j, 2]
                if (z0 <= z <= z1) or (z1 <= z <= z0):
                    dz = z1 - z0
                    if abs(dz) < 1e-12:
                        continue
                    t = np.clip((z - z0) / dz, 0.0, 1.0)
                    pts.append(verts[i] + t * (verts[j] - verts[i]))

            if len(pts) >= 2:
                segments.append((pts[0], pts[1]))

        return segments


# ── Free-standing Geometry Utilities ─────────────────────────────────────────

def _order_segments(
    segments: List[Tuple[np.ndarray, np.ndarray]],
    tol: float = 1e-5,
) -> List[np.ndarray]:
    """Chain unordered line segments into connected contours.

    Returns list of contour arrays, each shape (M, 3).
    """
    if not segments:
        return []

    remaining = list(segments)
    contours: List[np.ndarray] = []

    while remaining:
        seg = remaining.pop(0)
        chain = [seg[0], seg[1]]

        changed = True
        while changed:
            changed = False
            for i, s in enumerate(remaining):
                p0, p1 = s
                if np.linalg.norm(chain[-1] - p0) < tol:
                    chain.append(p1)
                elif np.linalg.norm(chain[-1] - p1) < tol:
                    chain.append(p0)
                elif np.linalg.norm(chain[0] - p1) < tol:
                    chain.insert(0, p0)
                elif np.linalg.norm(chain[0] - p0) < tol:
                    chain.insert(0, p1)
                else:
                    continue
                remaining.pop(i)
                changed = True
                break

        contours.append(np.array(chain))

    return contours


def _densify_points(points: np.ndarray, max_spacing: float) -> np.ndarray:
    """Insert intermediate points so that no gap exceeds *max_spacing*."""
    if len(points) < 2:
        return points

    dense = [points[0]]
    for i in range(1, len(points)):
        dist = float(np.linalg.norm(points[i] - points[i - 1]))
        if dist > max_spacing:
            n_seg = int(np.ceil(dist / max_spacing))
            for j in range(1, n_seg):
                t = j / n_seg
                dense.append(points[i - 1] + t * (points[i] - points[i - 1]))
        dense.append(points[i])

    return np.array(dense)
