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
Overhang Analyzer

Tier-1 module of the support-free multi-axis printing plan (see
docs/RESEARCH_SUPPORT_FREE_MULTIAXIS.md): flags which faces of a mesh
cannot be printed without support material in the current build direction.
This is the prerequisite for build-direction segmentation — you can't decide
where to split a model into sub-volumes without first knowing where the
overhangs are.

Angle convention (locked down here because overhang-angle conventions differ
across slicers — Cura measures from the horizontal build plate, the classic
maker "45-degree rule" measures from vertical — and mixing them up silently
inverts every threshold check):

    angle_deg ==  0   ->  face is a vertical wall (or better): no overhang,
                          each layer sits directly on the one below it.
    angle_deg == 90   ->  face points straight down: a horizontal ceiling
                          with nothing beneath it, the worst possible case.
    Upward-facing faces (normal has a positive component along the build
    direction — floors, not ceilings) are never flagged; the layer above
    them is supported BY them, they don't need support themselves.

No ROS dependencies — pure Python + NumPy, mirrors multiaxis_planner.py.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .multiaxis_planner import MeshTriangle, load_stl_mesh

# The classic FDM "45-degree rule": surfaces steeper than 45 degrees from
# vertical are the common threshold beyond which unsupported prints sag or
# fail. Reasonable default, not a hard physical constant — override per
# material/nozzle.
DEFAULT_MAX_PRINTABLE_OVERHANG_DEG = 45.0


@dataclass
class OverhangConfig:
    """Parameters for one overhang analysis pass."""

    build_direction: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 0.0, 1.0])
    )
    max_printable_overhang_deg: float = DEFAULT_MAX_PRINTABLE_OVERHANG_DEG


@dataclass
class FaceOverhang:
    """A single mesh face that needs support in the analyzed build direction."""

    face_index: int
    angle_deg: float
    area: float             # m^2 (load_stl_mesh converts mm -> m on load)
    centroid: np.ndarray    # (3,), metres


@dataclass
class OverhangReport:
    """Result of analyzing a mesh against one build direction."""

    build_direction: np.ndarray
    max_printable_overhang_deg: float
    total_area: float
    overhang_faces: List[FaceOverhang]

    @property
    def overhang_area(self) -> float:
        return sum(f.area for f in self.overhang_faces)

    @property
    def overhang_area_pct(self) -> float:
        if self.total_area <= 0.0:
            return 0.0
        return 100.0 * self.overhang_area / self.total_area

    @property
    def needs_support(self) -> bool:
        return len(self.overhang_faces) > 0

    @property
    def worst_angle_deg(self) -> float:
        if not self.overhang_faces:
            return 0.0
        return max(f.angle_deg for f in self.overhang_faces)

    def summary(self) -> str:
        if not self.needs_support:
            return (
                f"No overhangs beyond {self.max_printable_overhang_deg:.0f}° "
                f"in this build direction."
            )
        return (
            f"{len(self.overhang_faces)} face(s) need support "
            f"({self.overhang_area_pct:.1f}% of surface area, "
            f"worst angle {self.worst_angle_deg:.1f}°)."
        )


def _triangle_areas(triangles: List[MeshTriangle]) -> np.ndarray:
    """Vectorised triangle areas via the cross-product formula."""
    v = np.array([t.vertices for t in triangles])  # (N, 3, 3)
    e1 = v[:, 1] - v[:, 0]
    e2 = v[:, 2] - v[:, 0]
    return 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)


def normalize_direction(v: np.ndarray) -> np.ndarray:
    """Unit vector, raising on a (near-)zero input. Shared by every module
    that takes a build direction, so a zero-vector guard only lives once."""
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    if n < 1e-9:
        raise ValueError("direction vector must be non-zero")
    return v / n


def unit_face_normals(triangles: List[MeshTriangle]) -> np.ndarray:
    """(N,3) unit face normals, guarding against non-unit/zero normals in a
    hand-authored or edited STL."""
    normals = np.array([t.normal for t in triangles])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths[lengths < 1e-9] = 1.0
    return normals / lengths


def overhang_angles_deg(normals: np.ndarray, build_dir: np.ndarray) -> np.ndarray:
    """Per-face overhang angle in degrees for a given (already unit) build
    direction, using this module's angle convention: 0 = vertical wall
    (fine), 90 = straight-down ceiling (worst). Upward-facing faces (floors)
    get exactly 0.0 -- never flagged regardless of threshold, since they are
    the ones being built ON, not overhanging.

    `normals` must already be unit vectors (see unit_face_normals); this is
    the single place the down_component/arcsin formula lives so every
    caller (analyze_overhangs, build_segmentation) shares one convention.
    """
    down_component = -(normals @ build_dir)
    angles = np.zeros(len(normals))
    mask = down_component > 1e-9
    angles[mask] = np.degrees(np.arcsin(np.clip(down_component[mask], 0.0, 1.0)))
    return angles


def analyze_overhangs(
    triangles: List[MeshTriangle],
    config: Optional[OverhangConfig] = None,
) -> OverhangReport:
    """Flag faces that cannot print without support in `config.build_direction`.

    See the module docstring for the angle convention: 0 deg = vertical wall
    (fine), 90 deg = straight-down ceiling (worst). Upward-facing faces are
    excluded entirely, never flagged.
    """
    config = config or OverhangConfig()
    build_dir = normalize_direction(config.build_direction)

    if not triangles:
        return OverhangReport(
            build_direction=build_dir,
            max_printable_overhang_deg=config.max_printable_overhang_deg,
            total_area=0.0,
            overhang_faces=[],
        )

    normals = unit_face_normals(triangles)
    areas = _triangle_areas(triangles)
    total_area = float(areas.sum())
    angles = overhang_angles_deg(normals, build_dir)

    overhang_faces: List[FaceOverhang] = []
    for face_idx in np.nonzero(angles > config.max_printable_overhang_deg)[0]:
        face_idx = int(face_idx)
        overhang_faces.append(FaceOverhang(
            face_index=face_idx,
            angle_deg=float(angles[face_idx]),
            area=float(areas[face_idx]),
            centroid=np.mean(triangles[face_idx].vertices, axis=0),
        ))

    return OverhangReport(
        build_direction=build_dir,
        max_printable_overhang_deg=config.max_printable_overhang_deg,
        total_area=total_area,
        overhang_faces=overhang_faces,
    )


def analyze_stl_overhangs(
    stl_filepath: str,
    config: Optional[OverhangConfig] = None,
) -> OverhangReport:
    """Convenience wrapper: load an STL file and analyze it directly."""
    triangles = load_stl_mesh(stl_filepath)
    return analyze_overhangs(triangles, config)
