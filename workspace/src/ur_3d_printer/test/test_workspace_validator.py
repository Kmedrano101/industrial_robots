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
"""Tests for workspace validator."""

import numpy as np
import pytest

from ur_3d_printer.toolpath import Waypoint, Layer, Toolpath
from ur_3d_printer.workspace_validator import ValidationResult


class TestValidationResult:
    def test_default_valid(self):
        result = ValidationResult()
        assert result.is_valid is True
        assert result.total_checked == 0

    def test_reachability_pct(self):
        result = ValidationResult(total_checked=10, total_reachable=8)
        assert result.reachability_pct == pytest.approx(80.0)

    def test_reachability_pct_zero(self):
        result = ValidationResult()
        assert result.reachability_pct == 0.0

    def test_unreachable_makes_invalid(self):
        result = ValidationResult(
            is_valid=False,
            unreachable_waypoints=[10, 20, 30],
            total_checked=100,
            total_reachable=97,
        )
        assert not result.is_valid
        assert len(result.unreachable_waypoints) == 3


class TestBoundsCheck:
    """Test workspace bounds validation logic (without ROS services)."""

    def test_within_bounds(self):
        """Toolpath within workspace bounds should pass."""
        tp = Toolpath()
        layer = Layer(index=0, z_height=0.5, waypoints=[
            Waypoint(position=[0.3, 0.0, 0.5]),
            Waypoint(position=[0.4, 0.1, 0.5]),
        ])
        tp.layers = [layer]

        bb_min, bb_max = tp.bounding_box
        ws_min = np.array([0.0, -0.5, 0.0])
        ws_max = np.array([1.0, 0.5, 1.0])

        # All axes should be within bounds
        assert np.all(bb_min >= ws_min)
        assert np.all(bb_max <= ws_max)

    def test_out_of_bounds(self):
        """Toolpath exceeding workspace should be detected."""
        tp = Toolpath()
        layer = Layer(index=0, z_height=0.5, waypoints=[
            Waypoint(position=[1.5, 0.0, 0.5]),  # X too large
        ])
        tp.layers = [layer]

        bb_min, bb_max = tp.bounding_box
        ws_max = np.array([1.0, 0.5, 1.0])

        assert bb_max[0] > ws_max[0]  # X exceeds bound

    def test_transformed_bounds(self):
        """Test bounds check with print frame transform."""
        tp = Toolpath()
        tp.print_frame = np.eye(4)
        tp.print_frame[0, 3] = 0.5  # Shift 0.5m in X

        layer = Layer(index=0, z_height=0.001, waypoints=[
            Waypoint(position=[0.0, 0.0, 0.001]),
            Waypoint(position=[0.1, 0.1, 0.001]),
        ])
        tp.layers = [layer]

        bb_min, bb_max = tp.bounding_box_robot_frame()
        assert bb_min[0] == pytest.approx(0.5)
        assert bb_max[0] == pytest.approx(0.6)
