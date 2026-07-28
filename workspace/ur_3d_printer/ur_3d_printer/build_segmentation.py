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
Build-Direction Segmentation

Tier-1 module of the support-free multi-axis printing plan (see
docs/RESEARCH_SUPPORT_FREE_MULTIAXIS.md, section "Plan de implementacion
por tiers", step 2): groups a mesh's faces into a small number of
sub-regions, each assigned the build direction that best avoids overhang
for THAT region, using overhang_analyzer.py as the scoring function.

Deliberately NOT the continuous scalar-field volume decomposition of Dai et
al. (SIGGRAPH 2018) -- that is genuinely open research (Tier 3) and has no
reusable open-source implementation. This is the "simple and verifiable"
alternative explicitly called out in the plan: a small, fixed set of
candidate build directions, greedily assigned by area coverage.

Candidate directions default to the 6 axis-aligned unit vectors. This is a
deliberate simplification, not corner-cutting: Tier 1's physical execution
model is a human pausing the print and re-seating the workpiece in an
indexed fixture (see docs/RESEARCH_SUPPORT_FREE_MULTIAXIS.md section 0) --
without an actuated positioner (Tier 2), arbitrary continuous reorientation
isn't realizable anyway, so optimizing over an arbitrary continuous
direction space would be solving a harder problem than the hardware can act
on.

The suggested print order is a documented HEURISTIC (default direction
first, then largest remaining segment), not a solved dependency/support
ordering problem -- a human should sanity-check it before physically
executing a multi-orientation print. Real inter-segment dependency analysis
(does segment B rest on already-printed segment A?) is Tier 2/3 territory.

No ROS dependencies — pure Python + NumPy, mirrors overhang_analyzer.py.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .multiaxis_planner import MeshTriangle, load_stl_mesh
from .overhang_analyzer import (
    DEFAULT_MAX_PRINTABLE_OVERHANG_DEG,
    OverhangConfig,
    _triangle_areas,
    analyze_overhangs,
    normalize_direction,
    overhang_angles_deg,
    unit_face_normals,
)

# The 6 axis-aligned directions: the discrete orientations an indexed
# manual fixture can realistically hit without a rotary positioner.
AXIS_ALIGNED_DIRECTIONS: List[np.ndarray] = [
    np.array([1.0, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0]),
    np.array([0.0, 1.0, 0.0]), np.array([0.0, -1.0, 0.0]),
    np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, -1.0]),
]


@dataclass
class SegmentationConfig:
    """Parameters for one build-direction segmentation pass."""

    default_build_direction: np.ndarray = field(
        default_factory=lambda: np.array([0.0, 0.0, 1.0])
    )
    max_segments: int = 4
    max_printable_overhang_deg: float = DEFAULT_MAX_PRINTABLE_OVERHANG_DEG
    # None -> AXIS_ALIGNED_DIRECTIONS. Callers can pass their own candidate
    # pool (e.g. once a Tier-2 positioner allows arbitrary directions).
    candidate_directions: Optional[List[np.ndarray]] = None


@dataclass
class BuildSegment:
    """One sub-region of the mesh, printed in its own build direction."""

    build_direction: np.ndarray
    face_indices: List[int]
    area: float
    overhang_area_pct: float   # residual overhang WITHIN this segment,
    worst_angle_deg: float     # judged under this segment's OWN direction


@dataclass
class SegmentationResult:
    """A full partition of the mesh's faces, in suggested print order."""

    segments: List[BuildSegment]
    total_area: float

    @property
    def num_segments(self) -> int:
        return len(self.segments)

    @property
    def overall_overhang_area_pct(self) -> float:
        """Residual overhang area across the whole mesh, each face judged
        under its OWN segment's chosen direction (not the single default
        direction analyze_overhangs() would use alone)."""
        if self.total_area <= 0.0:
            return 0.0
        residual = sum(
            seg.overhang_area_pct / 100.0 * seg.area for seg in self.segments
        )
        return 100.0 * residual / self.total_area

    def summary(self) -> str:
        if self.num_segments <= 1:
            return (
                "1 segment (no reorientation needed) covers the whole "
                f"part; residual overhang {self.overall_overhang_area_pct:.1f}%."
            )
        return (
            f"{self.num_segments} segments (reorient between each); "
            f"residual overhang {self.overall_overhang_area_pct:.1f}% "
            "(faces no candidate direction could fix)."
        )


def _candidate_pool(config: SegmentationConfig) -> List[np.ndarray]:
    """Default direction first (try to avoid reorientation entirely if it's
    already good enough), then the rest of the candidate pool, deduplicated."""
    default_dir = normalize_direction(config.default_build_direction)
    pool = config.candidate_directions or AXIS_ALIGNED_DIRECTIONS
    ordered = [default_dir]
    for d in pool:
        d = normalize_direction(d)
        if not any(np.allclose(d, existing, atol=1e-6) for existing in ordered):
            ordered.append(d)
    return ordered


def segment_by_build_direction(
    triangles: List[MeshTriangle],
    config: Optional[SegmentationConfig] = None,
) -> SegmentationResult:
    """Partition `triangles` into up to `config.max_segments` build-direction
    groups via greedy area-coverage assignment.

    Algorithm (deliberately simple -- see module docstring for why):
      1. Score every candidate direction against every still-unassigned face.
      2. Repeatedly pick the direction that newly covers the most unassigned
         area (classic greedy set cover), until `max_segments` is reached or
         no candidate improves coverage further.
      3. Any faces left over (no candidate direction prints them cleanly)
         are attached to whichever chosen segment minimizes THEIR angle --
         every face ends up in exactly one segment, even if imperfectly.
      4. Segments are ordered: the default build direction first (if
         chosen), then by descending area -- a documented heuristic, not a
         solved build-order/dependency problem.
    """
    config = config or SegmentationConfig()
    if config.max_segments < 1:
        raise ValueError("max_segments must be >= 1")

    if not triangles:
        return SegmentationResult(segments=[], total_area=0.0)

    normals = unit_face_normals(triangles)
    n_faces = len(triangles)
    candidates = _candidate_pool(config)

    # angles_by_candidate[k] = per-face overhang angle under candidates[k].
    angles_by_candidate = np.array(
        [overhang_angles_deg(normals, d) for d in candidates]
    )  # (K, N)
    printable_by_candidate = angles_by_candidate <= config.max_printable_overhang_deg
    areas = _triangle_areas(triangles)
    total_area = float(areas.sum())

    unassigned = np.ones(n_faces, dtype=bool)
    chosen: List[int] = []          # indices into `candidates`
    assignment: List[List[int]] = []  # face indices per chosen segment

    while len(chosen) < config.max_segments and np.any(unassigned):
        best_k, best_new_area = None, 0.0
        for k in range(len(candidates)):
            if k in chosen:
                continue
            newly_covered = printable_by_candidate[k] & unassigned
            covered_area = float(areas[newly_covered].sum())
            if covered_area > best_new_area:
                best_k, best_new_area = k, covered_area

        if best_k is None or best_new_area <= 1e-12:
            break  # no remaining candidate improves coverage -- stop early

        newly_covered = printable_by_candidate[best_k] & unassigned
        chosen.append(best_k)
        assignment.append(list(np.nonzero(newly_covered)[0]))
        unassigned &= ~newly_covered

    if not chosen:
        # Degenerate mesh (e.g. every normal is zero-length) -- fall back to
        # a single segment in the default direction so callers always get a
        # complete, non-empty partition.
        chosen.append(0)
        assignment.append([])

    # Attach any leftover faces to whichever CHOSEN segment minimizes their
    # angle -- best effort, not silently dropped.
    leftover = np.nonzero(unassigned)[0]
    if len(leftover) > 0:
        chosen_angles = angles_by_candidate[chosen][:, leftover]  # (C, len(leftover))
        best_segment_per_face = np.argmin(chosen_angles, axis=0)
        for local_i, face_idx in enumerate(leftover):
            assignment[int(best_segment_per_face[local_i])].append(int(face_idx))

    # Build the segment objects (metrics via analyze_overhangs -- reuse
    # rather than re-derive overhang_area_pct/worst_angle_deg by hand).
    segments: List[BuildSegment] = []
    for k, face_indices in zip(chosen, assignment):
        direction = candidates[k]
        face_indices = sorted(face_indices)
        seg_area = float(areas[face_indices].sum()) if face_indices else 0.0
        if face_indices:
            seg_triangles = [triangles[i] for i in face_indices]
            report = analyze_overhangs(seg_triangles, OverhangConfig(
                build_direction=direction,
                max_printable_overhang_deg=config.max_printable_overhang_deg,
            ))
            overhang_pct = report.overhang_area_pct
            worst_angle = report.worst_angle_deg
        else:
            overhang_pct, worst_angle = 0.0, 0.0
        segments.append(BuildSegment(
            build_direction=direction,
            face_indices=face_indices,
            area=seg_area,
            overhang_area_pct=overhang_pct,
            worst_angle_deg=worst_angle,
        ))

    # Suggested print order: default direction first (if it was chosen),
    # then descending area. See module docstring -- this is a heuristic.
    default_dir = normalize_direction(config.default_build_direction)

    def _sort_key(seg: BuildSegment):
        is_default = np.allclose(seg.build_direction, default_dir, atol=1e-6)
        return (0 if is_default else 1, -seg.area)

    segments.sort(key=_sort_key)

    return SegmentationResult(segments=segments, total_area=total_area)


def segment_stl_by_build_direction(
    stl_filepath: str,
    config: Optional[SegmentationConfig] = None,
) -> SegmentationResult:
    """Convenience wrapper: load an STL file and segment it directly."""
    triangles = load_stl_mesh(stl_filepath)
    return segment_by_build_direction(triangles, config)
