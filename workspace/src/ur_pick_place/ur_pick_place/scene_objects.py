#!/usr/bin/env python3
"""
Scene Object Manager

Manages visualization markers for pick/place locations and objects.
"""

from typing import List, Tuple
import numpy as np

from visualization_msgs.msg import Marker, MarkerArray
from geometry_msgs.msg import Point, Pose, Vector3
from std_msgs.msg import ColorRGBA, Header


class SceneObjectManager:
    """
    Manages scene objects and visualization markers.
    """

    def __init__(self, frame_id: str = 'world'):
        self.frame_id = frame_id
        self.objects = {}
        self.marker_id = 0

    def create_location_marker(self, position: List[float], color: Tuple[float, ...],
                                label: str, marker_id: int) -> Marker:
        """Create a marker for pick/place location."""
        marker = Marker()
        marker.header.frame_id = self.frame_id
        marker.ns = 'locations'
        marker.id = marker_id
        marker.type = Marker.CYLINDER
        marker.action = Marker.ADD

        marker.pose.position.x = position[0]
        marker.pose.position.y = position[1]
        marker.pose.position.z = position[2] - 0.01  # Slightly below surface
        marker.pose.orientation.w = 1.0

        marker.scale.x = 0.08  # Diameter
        marker.scale.y = 0.08
        marker.scale.z = 0.005  # Thin disk

        marker.color.r = color[0]
        marker.color.g = color[1]
        marker.color.b = color[2]
        marker.color.a = color[3] if len(color) > 3 else 0.8

        marker.lifetime.sec = 0  # Persistent

        return marker

    def create_location_label(self, position: List[float], label: str,
                               marker_id: int) -> Marker:
        """Create a text label for a location."""
        marker = Marker()
        marker.header.frame_id = self.frame_id
        marker.ns = 'labels'
        marker.id = marker_id
        marker.type = Marker.TEXT_VIEW_FACING
        marker.action = Marker.ADD

        marker.pose.position.x = position[0]
        marker.pose.position.y = position[1]
        marker.pose.position.z = position[2] + 0.15  # Above location
        marker.pose.orientation.w = 1.0

        marker.scale.z = 0.05  # Text height

        marker.color.r = 1.0
        marker.color.g = 1.0
        marker.color.b = 1.0
        marker.color.a = 1.0

        marker.text = label
        marker.lifetime.sec = 0

        return marker

    def create_object_marker(self, position: List[float], size: List[float],
                              color: Tuple[float, ...], object_id: str,
                              marker_id: int, shape: str = 'cube') -> Marker:
        """Create a marker for a scene object."""
        marker = Marker()
        marker.header.frame_id = self.frame_id
        marker.ns = 'objects'
        marker.id = marker_id

        if shape == 'cube':
            marker.type = Marker.CUBE
            marker.scale.x = size[0]
            marker.scale.y = size[1]
            marker.scale.z = size[2]
        elif shape == 'cylinder':
            marker.type = Marker.CYLINDER
            marker.scale.x = size[0] * 2  # Diameter
            marker.scale.y = size[0] * 2
            marker.scale.z = size[1]  # Height
        elif shape == 'sphere':
            marker.type = Marker.SPHERE
            marker.scale.x = size[0] * 2
            marker.scale.y = size[0] * 2
            marker.scale.z = size[0] * 2
        else:
            marker.type = Marker.CUBE
            marker.scale.x = size[0]
            marker.scale.y = size[1]
            marker.scale.z = size[2]

        marker.action = Marker.ADD

        marker.pose.position.x = position[0]
        marker.pose.position.y = position[1]
        marker.pose.position.z = position[2]
        marker.pose.orientation.w = 1.0

        marker.color.r = color[0]
        marker.color.g = color[1]
        marker.color.b = color[2]
        marker.color.a = color[3] if len(color) > 3 else 1.0

        marker.lifetime.sec = 0

        return marker

    def create_approach_marker(self, position: List[float], approach_height: float,
                                marker_id: int) -> Marker:
        """Create a marker showing approach path."""
        marker = Marker()
        marker.header.frame_id = self.frame_id
        marker.ns = 'approach'
        marker.id = marker_id
        marker.type = Marker.ARROW
        marker.action = Marker.ADD

        # Arrow from approach height down to position
        start = Point()
        start.x = position[0]
        start.y = position[1]
        start.z = position[2] + approach_height

        end = Point()
        end.x = position[0]
        end.y = position[1]
        end.z = position[2]

        marker.points = [start, end]

        marker.scale.x = 0.01  # Shaft diameter
        marker.scale.y = 0.02  # Head diameter
        marker.scale.z = 0.02  # Head length

        marker.color.r = 0.0
        marker.color.g = 1.0
        marker.color.b = 1.0
        marker.color.a = 0.6

        marker.lifetime.sec = 0

        return marker

    def create_pick_place_markers(self, pick_pos: List[float], place_pos: List[float],
                                   approach_height: float,
                                   object_size: List[float] = None) -> MarkerArray:
        """Create all markers for pick and place visualization."""
        markers = MarkerArray()

        # Pick location (green)
        markers.markers.append(
            self.create_location_marker(pick_pos, (0.2, 0.8, 0.2, 0.8), 'Pick', 0)
        )
        markers.markers.append(
            self.create_location_label(pick_pos, 'PICK (A)', 1)
        )
        markers.markers.append(
            self.create_approach_marker(pick_pos, approach_height, 2)
        )

        # Place location (blue)
        markers.markers.append(
            self.create_location_marker(place_pos, (0.2, 0.2, 0.8, 0.8), 'Place', 3)
        )
        markers.markers.append(
            self.create_location_label(place_pos, 'PLACE (B)', 4)
        )
        markers.markers.append(
            self.create_approach_marker(place_pos, approach_height, 5)
        )

        # Object at pick location
        if object_size is None:
            object_size = [0.04, 0.04, 0.04]

        obj_pos = [pick_pos[0], pick_pos[1], pick_pos[2] + object_size[2] / 2]
        markers.markers.append(
            self.create_object_marker(obj_pos, object_size, (0.9, 0.3, 0.1, 1.0),
                                       'object_1', 6, 'cube')
        )

        return markers

    def update_object_position(self, markers: MarkerArray, object_id: int,
                                new_position: List[float]) -> None:
        """Update position of an object marker."""
        for marker in markers.markers:
            if marker.ns == 'objects' and marker.id == object_id:
                marker.pose.position.x = new_position[0]
                marker.pose.position.y = new_position[1]
                marker.pose.position.z = new_position[2]
                break

    def create_gripper_target_marker(self, position: List[float],
                                      orientation: List[float],
                                      marker_id: int) -> Marker:
        """Create a marker showing gripper target pose."""
        marker = Marker()
        marker.header.frame_id = self.frame_id
        marker.ns = 'gripper_target'
        marker.id = marker_id
        marker.type = Marker.ARROW
        marker.action = Marker.ADD

        marker.pose.position.x = position[0]
        marker.pose.position.y = position[1]
        marker.pose.position.z = position[2]

        marker.pose.orientation.x = orientation[0]
        marker.pose.orientation.y = orientation[1]
        marker.pose.orientation.z = orientation[2]
        marker.pose.orientation.w = orientation[3]

        marker.scale.x = 0.1   # Length
        marker.scale.y = 0.015  # Width
        marker.scale.z = 0.015  # Height

        marker.color.r = 1.0
        marker.color.g = 0.5
        marker.color.b = 0.0
        marker.color.a = 0.8

        marker.lifetime.sec = 0

        return marker
