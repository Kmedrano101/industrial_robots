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
"""Tests for toolpath data structures."""

import numpy as np
import pytest

from ur_3d_printer.toolpath import Waypoint, Layer, Toolpath


class TestWaypoint:
    def test_creation(self):
        wp = Waypoint(position=[0.1, 0.2, 0.3])
        assert wp.x == pytest.approx(0.1)
        assert wp.y == pytest.approx(0.2)
        assert wp.z == pytest.approx(0.3)

    def test_defaults(self):
        wp = Waypoint(position=[0, 0, 0])
        assert wp.feed_rate == 0.0
        assert wp.extrusion_rate == 0.0
        assert wp.is_travel is False
        assert wp.layer_index == 0
        np.testing.assert_array_equal(wp.orientation, np.eye(3))

    def test_distance_to(self):
        wp1 = Waypoint(position=[0.0, 0.0, 0.0])
        wp2 = Waypoint(position=[3.0, 4.0, 0.0])
        assert wp1.distance_to(wp2) == pytest.approx(5.0)

    def test_to_homogeneous(self):
        wp = Waypoint(position=[1.0, 2.0, 3.0])
        T = wp.to_homogeneous()
        assert T.shape == (4, 4)
        np.testing.assert_array_almost_equal(T[:3, 3], [1.0, 2.0, 3.0])
        np.testing.assert_array_equal(T[:3, :3], np.eye(3))
        assert T[3, 3] == 1.0

    def test_custom_orientation(self):
        R = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
        wp = Waypoint(position=[0, 0, 0], orientation=R)
        T = wp.to_homogeneous()
        np.testing.assert_array_almost_equal(T[:3, :3], R)


class TestLayer:
    def _make_layer(self, n=5):
        waypoints = []
        for i in range(n):
            waypoints.append(Waypoint(
                position=[float(i) * 0.01, 0.0, 0.001],
                feed_rate=0.05,
                is_travel=(i == 0),
                layer_index=0,
            ))
        return Layer(index=0, z_height=0.001, waypoints=waypoints, layer_height=0.001)

    def test_num_waypoints(self):
        layer = self._make_layer(5)
        assert layer.num_waypoints == 5

    def test_extrusion_vs_travel(self):
        layer = self._make_layer(5)
        assert len(layer.extrusion_waypoints) == 4
        assert len(layer.travel_waypoints) == 1

    def test_path_length(self):
        layer = self._make_layer(5)
        # 4 segments of 0.01m each
        assert layer.path_length() == pytest.approx(0.04)

    def test_extrusion_length(self):
        layer = self._make_layer(5)
        # Segments 0→1, 1→2, 2→3, 3→4: wp[1..4].is_travel=False, so all 4 counted
        assert layer.extrusion_length() == pytest.approx(0.04)


class TestToolpath:
    def _make_toolpath(self):
        layers = []
        for li in range(3):
            waypoints = []
            z = (li + 1) * 0.0002
            for i in range(4):
                waypoints.append(Waypoint(
                    position=[float(i) * 0.01, 0.0, z],
                    feed_rate=0.05,
                    is_travel=(i == 0),
                    layer_index=li,
                ))
            layers.append(Layer(
                index=li, z_height=z,
                waypoints=waypoints, layer_height=0.0002,
            ))
        return Toolpath(layers=layers)

    def test_num_layers(self):
        tp = self._make_toolpath()
        assert tp.num_layers == 3

    def test_num_waypoints(self):
        tp = self._make_toolpath()
        assert tp.num_waypoints == 12

    def test_bounding_box(self):
        tp = self._make_toolpath()
        bb_min, bb_max = tp.bounding_box
        assert bb_min[0] == pytest.approx(0.0)
        assert bb_max[0] == pytest.approx(0.03)
        assert bb_min[2] == pytest.approx(0.0002)
        assert bb_max[2] == pytest.approx(0.0006)

    def test_estimated_time(self):
        tp = self._make_toolpath()
        # Each segment is 0.01m at 0.05 m/s = 0.2s, 3 segments per layer, 3 layers
        # plus layer transitions
        assert tp.estimated_time > 0.0

    def test_empty_bounding_box(self):
        tp = Toolpath()
        bb_min, bb_max = tp.bounding_box
        np.testing.assert_array_equal(bb_min, [0, 0, 0])
        np.testing.assert_array_equal(bb_max, [0, 0, 0])

    def test_transform_to_robot_frame(self):
        tp = self._make_toolpath()
        # Translate print frame 0.5m in X
        tp.print_frame = np.eye(4)
        tp.print_frame[0, 3] = 0.5
        transformed = tp.transform_to_robot_frame()
        # All X positions should be shifted by 0.5
        for wp in transformed:
            assert wp.x >= 0.5

    def test_bounding_box_robot_frame(self):
        tp = self._make_toolpath()
        tp.print_frame = np.eye(4)
        tp.print_frame[0, 3] = 1.0
        bb_min, bb_max = tp.bounding_box_robot_frame()
        assert bb_min[0] == pytest.approx(1.0)
        assert bb_max[0] == pytest.approx(1.03)

    def test_metadata(self):
        tp = Toolpath(metadata={'slicer': 'test', 'material': 'PLA'})
        assert tp.metadata['slicer'] == 'test'
