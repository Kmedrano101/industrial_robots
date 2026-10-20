"""FastAPI dependencies shared by the route modules."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from backend import ros_bridge as rb_module
from backend.jobs import JobStore
from backend.profiles import ProfileStore
from backend.ros_bridge import RosBridge

# Singletons created in the application lifespan (main.py). Read through
# this module at request time — see get_bridge() for why.
jobs: Optional[JobStore] = None
profiles: Optional[ProfileStore] = None


def get_bridge() -> Optional[RosBridge]:
    """The live RosBridge singleton, or None before startup.

    Always read through the module attribute. The bridge is created in the
    application lifespan, which runs *after* every route module has been
    imported, so a name bound with ``from backend.ros_bridge import
    ros_bridge`` captures the initial ``None`` and never sees the real
    object. That is exactly what happened to the print, extruder and health
    routes: with the bridge up and streaming, ``POST /api/print/pause``
    still answered "ROS2 not available".
    """
    return rb_module.ros_bridge


def require_bridge() -> RosBridge:
    """The running bridge, or 503 when ROS is not available."""
    bridge = rb_module.ros_bridge
    if bridge is None or not bridge.running:
        raise HTTPException(status_code=503, detail="ROS2 not available")
    return bridge


def require_jobs() -> JobStore:
    if jobs is None:
        raise HTTPException(status_code=503, detail="Job history not available")
    return jobs


def require_profiles() -> ProfileStore:
    if profiles is None:
        raise HTTPException(status_code=503, detail="Profiles not available")
    return profiles
