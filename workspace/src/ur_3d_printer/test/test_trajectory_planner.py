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
"""Tests for trajectory planner and velocity profiler."""

import math
import numpy as np
import pytest

from ur_3d_printer.toolpath import Waypoint
from ur_3d_printer.velocity_profiler import VelocityProfiler


class TestVelocityProfiler:
    def test_single_waypoint(self):
        profiler = VelocityProfiler()
        wp = Waypoint(position=[0, 0, 0], feed_rate=0.05)
        timestamps = profiler.compute_timestamps([wp])
        assert timestamps == [0.0]

    def test_two_waypoints(self):
        profiler = VelocityProfiler(max_print_velocity=0.05)
        wps = [
            Waypoint(position=[0, 0, 0], feed_rate=0.05),
            Waypoint(position=[0.01, 0, 0], feed_rate=0.05),
        ]
        timestamps = profiler.compute_timestamps(wps)
        assert len(timestamps) == 2
        assert timestamps[0] == 0.0
        assert timestamps[1] > 0.0

    def test_timestamps_monotonically_increasing(self):
        profiler = VelocityProfiler()
        wps = [
            Waypoint(position=[i * 0.01, 0, 0], feed_rate=0.05)
            for i in range(10)
        ]
        timestamps = profiler.compute_timestamps(wps)
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i - 1]

    def test_corner_slows_down(self):
        profiler = VelocityProfiler(max_print_velocity=0.05, max_acceleration=0.5)
        # Straight line
        straight = [
            Waypoint(position=[i * 0.01, 0, 0], feed_rate=0.05)
            for i in range(5)
        ]
        # 90-degree corner
        corner = [
            Waypoint(position=[0, 0, 0], feed_rate=0.05),
            Waypoint(position=[0.02, 0, 0], feed_rate=0.05),
            Waypoint(position=[0.02, 0.02, 0], feed_rate=0.05),  # 90deg turn
        ]
        t_straight = profiler.compute_timestamps(straight)
        t_corner = profiler.compute_timestamps(corner)

        # Corner path should take longer per unit distance due to slowdown
        dist_straight = 0.04
        dist_corner = 0.04
        time_per_dist_straight = t_straight[-1] / dist_straight
        time_per_dist_corner = t_corner[-1] / dist_corner
        # Corner should be slower (more time per distance)
        assert time_per_dist_corner > time_per_dist_straight

    def test_travel_faster_than_print(self):
        profiler = VelocityProfiler(
            max_print_velocity=0.05,
            max_travel_velocity=0.15,
        )
        dist = 0.05  # 50mm

        print_wps = [
            Waypoint(position=[0, 0, 0], feed_rate=0.05, is_travel=False),
            Waypoint(position=[dist, 0, 0], feed_rate=0.05, is_travel=False),
        ]
        travel_wps = [
            Waypoint(position=[0, 0, 0], feed_rate=0.15, is_travel=True),
            Waypoint(position=[dist, 0, 0], feed_rate=0.15, is_travel=True),
        ]

        t_print = profiler.compute_timestamps(print_wps)
        t_travel = profiler.compute_timestamps(travel_wps)

        # Travel should be faster (less time)
        assert t_travel[-1] < t_print[-1]

    def test_densify_waypoints(self):
        profiler = VelocityProfiler()
        wps = [
            Waypoint(position=[0, 0, 0]),
            Waypoint(position=[0.01, 0, 0]),  # 10mm apart
        ]
        densified = profiler.densify_waypoints(wps, max_segment_length=0.002)
        # Should have at least 5 segments (10mm / 2mm)
        assert len(densified) >= 6

    def test_densify_preserves_endpoints(self):
        profiler = VelocityProfiler()
        wps = [
            Waypoint(position=[0, 0, 0], line_number=1),
            Waypoint(position=[0.01, 0, 0], line_number=2),
        ]
        densified = profiler.densify_waypoints(wps, max_segment_length=0.002)
        np.testing.assert_array_almost_equal(densified[0].position, [0, 0, 0])
        np.testing.assert_array_almost_equal(densified[-1].position, [0.01, 0, 0])

    def test_densify_short_segment_unchanged(self):
        profiler = VelocityProfiler()
        wps = [
            Waypoint(position=[0, 0, 0]),
            Waypoint(position=[0.001, 0, 0]),  # 1mm, below 2mm threshold
        ]
        densified = profiler.densify_waypoints(wps, max_segment_length=0.002)
        assert len(densified) == 2

    def test_empty_waypoints(self):
        profiler = VelocityProfiler()
        assert profiler.compute_timestamps([]) == []
        assert profiler.densify_waypoints([]) == []


class TestCornerAngle:
    def test_straight_line(self):
        angle = VelocityProfiler._corner_angle(
            np.array([0, 0, 0]),
            np.array([1, 0, 0]),
            np.array([2, 0, 0]),
        )
        assert angle == pytest.approx(0.0, abs=1e-6)

    def test_right_angle(self):
        angle = VelocityProfiler._corner_angle(
            np.array([0, 0, 0]),
            np.array([1, 0, 0]),
            np.array([1, 1, 0]),
        )
        assert angle == pytest.approx(math.pi / 2, abs=0.01)

    def test_reversal(self):
        angle = VelocityProfiler._corner_angle(
            np.array([0, 0, 0]),
            np.array([1, 0, 0]),
            np.array([0, 0, 0]),
        )
        assert angle == pytest.approx(math.pi, abs=0.01)

    def test_zero_length_segment(self):
        angle = VelocityProfiler._corner_angle(
            np.array([0, 0, 0]),
            np.array([0, 0, 0]),
            np.array([1, 0, 0]),
        )
        assert angle == 0.0
