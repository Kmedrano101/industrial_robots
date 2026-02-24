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
Velocity Profiler

Computes timestamps for toolpath waypoints using trapezoidal velocity profiles
with corner blending. Reduces velocity at sharp corners based on angle.
No ROS dependencies.
"""

import math
from typing import List

import numpy as np

from .toolpath import Waypoint


class VelocityProfiler:
    """Compute timed velocity profiles for toolpath waypoints.

    Args:
        max_print_velocity: Maximum velocity during printing (m/s).
        max_travel_velocity: Maximum velocity during travel moves (m/s).
        max_acceleration: Maximum acceleration (m/s^2).
        corner_blend_radius: Blend radius at corners (m).
        min_segment_time: Minimum time per segment (s).
    """

    def __init__(
        self,
        max_print_velocity: float = 0.05,
        max_travel_velocity: float = 0.15,
        max_acceleration: float = 0.5,
        corner_blend_radius: float = 0.002,
        min_segment_time: float = 0.01,
    ):
        self.max_print_velocity = max_print_velocity
        self.max_travel_velocity = max_travel_velocity
        self.max_acceleration = max_acceleration
        self.corner_blend_radius = corner_blend_radius
        self.min_segment_time = min_segment_time

    def compute_timestamps(self, waypoints: List[Waypoint]) -> List[float]:
        """Compute cumulative timestamps for each waypoint.

        Applies trapezoidal velocity profile with corner speed reduction.

        Args:
            waypoints: Ordered list of waypoints.

        Returns:
            List of cumulative timestamps (seconds), same length as waypoints.
            First waypoint has timestamp 0.0.
        """
        if len(waypoints) <= 1:
            return [0.0] * len(waypoints)

        # Step 1: Compute corner angles and max velocity at each waypoint
        max_velocities = self._compute_corner_velocities(waypoints)

        # Step 2: Forward pass - limit velocity by acceleration from start
        forward_vel = [0.0] * len(waypoints)
        forward_vel[0] = max_velocities[0]
        for i in range(1, len(waypoints)):
            dist = waypoints[i].distance_to(waypoints[i - 1])
            # v^2 = v0^2 + 2*a*d
            v_max_accel = math.sqrt(
                forward_vel[i - 1] ** 2 + 2.0 * self.max_acceleration * dist
            )
            forward_vel[i] = min(max_velocities[i], v_max_accel)

        # Step 3: Backward pass - limit velocity by deceleration to end
        backward_vel = [0.0] * len(waypoints)
        backward_vel[-1] = max_velocities[-1]
        for i in range(len(waypoints) - 2, -1, -1):
            dist = waypoints[i].distance_to(waypoints[i + 1])
            v_max_decel = math.sqrt(
                backward_vel[i + 1] ** 2 + 2.0 * self.max_acceleration * dist
            )
            backward_vel[i] = min(forward_vel[i], v_max_decel)

        # Step 4: Final velocity is minimum of forward and backward
        final_vel = [min(f, b) for f, b in zip(forward_vel, backward_vel)]

        # Step 5: Compute timestamps from velocities and distances
        timestamps = [0.0]
        for i in range(1, len(waypoints)):
            dist = waypoints[i].distance_to(waypoints[i - 1])
            avg_vel = (final_vel[i] + final_vel[i - 1]) / 2.0

            if avg_vel > 1e-9:
                dt = dist / avg_vel
            else:
                dt = self.min_segment_time

            dt = max(dt, self.min_segment_time)
            timestamps.append(timestamps[-1] + dt)

        return timestamps

    def _compute_corner_velocities(self, waypoints: List[Waypoint]) -> List[float]:
        """Compute max allowed velocity at each waypoint based on corner angle.

        Sharp corners get reduced velocity; straight segments get full speed.
        """
        n = len(waypoints)
        velocities = []

        for i in range(n):
            # Base max velocity from feed rate and move type
            max_vel = waypoints[i].feed_rate
            if max_vel <= 0:
                max_vel = (self.max_travel_velocity if waypoints[i].is_travel
                           else self.max_print_velocity)

            # Clamp to configured maximums
            if waypoints[i].is_travel:
                max_vel = min(max_vel, self.max_travel_velocity)
            else:
                max_vel = min(max_vel, self.max_print_velocity)

            # Corner speed reduction for interior points
            if 0 < i < n - 1:
                angle = self._corner_angle(
                    waypoints[i - 1].position,
                    waypoints[i].position,
                    waypoints[i + 1].position,
                )
                # angle is deviation from straight (0 = straight, pi = full reversal)
                if angle > 0.01:  # More than ~0.5 degrees deviation
                    # Junction speed: v = sqrt(a * r * sin(angle/2) / (1 - sin(angle/2)))
                    sin_half = math.sin(angle / 2.0)
                    if sin_half < 0.999:
                        v_junction = math.sqrt(
                            self.max_acceleration * self.corner_blend_radius
                            * sin_half / (1.0 - sin_half + 1e-9)
                        )
                        max_vel = min(max_vel, v_junction)
                    else:
                        # Near 180-degree turn, use very low speed
                        max_vel = min(max_vel, 0.001)

            velocities.append(max_vel)

        return velocities

    @staticmethod
    def _corner_angle(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> float:
        """Compute corner deviation angle at p1 between segments p0→p1 and p1→p2.

        Returns angle in radians (0 = straight, pi = full reversal).
        """
        v1 = p1 - p0
        v2 = p2 - p1
        len1 = np.linalg.norm(v1)
        len2 = np.linalg.norm(v2)

        if len1 < 1e-9 or len2 < 1e-9:
            return 0.0

        cos_angle = np.dot(v1, v2) / (len1 * len2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        # Deviation from straight: angle between vectors = 0 means straight
        return math.acos(cos_angle)

    def densify_waypoints(
        self, waypoints: List[Waypoint], max_segment_length: float = 0.002
    ) -> List[Waypoint]:
        """Insert intermediate waypoints so no segment exceeds max_segment_length.

        Args:
            waypoints: Input waypoints.
            max_segment_length: Maximum distance between consecutive waypoints (m).

        Returns:
            Densified waypoint list.
        """
        if len(waypoints) <= 1:
            return list(waypoints)

        result = [waypoints[0]]

        for i in range(1, len(waypoints)):
            prev = waypoints[i - 1]
            curr = waypoints[i]
            dist = prev.distance_to(curr)

            if dist > max_segment_length:
                n_subdivisions = int(math.ceil(dist / max_segment_length))
                for j in range(1, n_subdivisions):
                    frac = j / n_subdivisions
                    interp_pos = prev.position + frac * (curr.position - prev.position)
                    # Interpolate orientation (simple linear for small angles)
                    interp_wp = Waypoint(
                        position=interp_pos,
                        orientation=curr.orientation.copy(),
                        feed_rate=curr.feed_rate,
                        extrusion_rate=curr.extrusion_rate,
                        is_travel=curr.is_travel,
                        layer_index=curr.layer_index,
                        line_number=curr.line_number,
                    )
                    result.append(interp_wp)

            result.append(curr)

        return result
