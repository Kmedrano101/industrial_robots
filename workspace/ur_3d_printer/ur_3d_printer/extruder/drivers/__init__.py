"""Extruder drivers and the factory that builds one from a profile."""

from __future__ import annotations

from typing import Any, Optional

from ..profile import ExtruderProfile
from .base import DriverReading, ExtruderDriver

__all__ = ['DriverReading', 'ExtruderDriver', 'make_driver']


def make_driver(
    profile: ExtruderProfile,
    driver_type: Optional[str] = None,
    node=None,
    overrides: Optional[dict[str, Any]] = None,
) -> ExtruderDriver:
    """Instantiate the driver named by ``driver_type`` (default: the
    profile's) with the profile's driver params plus ``overrides``.

    Drivers that need ROS (topic, ur_io) take the node; the others do not,
    which is what lets the core run in plain pytest.
    """
    kind = driver_type or profile.driver
    params: dict[str, Any] = dict(profile.driver_params)
    params.update({k: v for k, v in (overrides or {}).items() if v not in (None, '')})
    zones = len(profile.thermal.zones)

    if kind == 'mock':
        from .mock import MockExtruderDriver

        return MockExtruderDriver(zones=zones, **params)
    if kind == 'gcode_serial':
        from .gcode_serial import GcodeSerialDriver

        params.setdefault('zone_heaters', [z.gcode_heater for z in profile.thermal.zones])
        params.setdefault('min_extrusion_temperature', profile.thermal.min_extrusion_temperature)
        return GcodeSerialDriver(zones=zones, **params)
    if kind == 'topic':
        from .topic import TopicExtruderDriver

        if node is None:
            raise ValueError('topic driver needs a ROS node')
        return TopicExtruderDriver(node=node, zones=zones, **params)
    if kind == 'ur_io':
        from .ur_io import UrIoExtruderDriver

        if node is None:
            raise ValueError('ur_io driver needs a ROS node')
        return UrIoExtruderDriver(node=node, zones=zones,
                                  max_flow_mm3_s=profile.flow.max_mm3_s, **params)
    raise ValueError(f'unknown extruder driver {kind!r}')
