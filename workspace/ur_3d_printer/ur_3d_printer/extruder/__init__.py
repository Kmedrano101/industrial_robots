"""Modular extruder subsystem.

    profile.py   what the extruder is (YAML in config/extruders/)
    core.py      state machine + interlocks, hardware-independent
    drivers/     how to talk to the electronics (mock, gcode_serial, topic, ur_io)

The ROS node in ``ur_3d_printer.extruder_controller`` is a thin wrapper
that exposes the core over services/topics.
"""

from .core import ExtruderCore, ExtruderStatus
from .profile import ExtruderProfile, ProfileError, load_profile

__all__ = ['ExtruderCore', 'ExtruderStatus', 'ExtruderProfile', 'ProfileError', 'load_profile']
