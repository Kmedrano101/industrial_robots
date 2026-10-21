"""Cell settings endpoints: read, update, reset, capture poses, request a
restart of the ROS stack so changes take effect."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from backend import deps
from backend.cell_settings import (
    BED_POINT_NAMES, EXTRUDER_PARAMS, HOT_PRINT_NODE_PARAMS, PRINT_NODE_PARAMS, ros_overlay,
    restart_diff, same_value,
)
from backend.config import settings as env

router = APIRouter()

RESTART_REQUEST = "restart.request"
EFFECTIVE_TIMEOUT_S = 2.0


class SettingsPatch(BaseModel):
    patch: dict[str, Any] = Field(description="Partial settings document, grouped")
    source: str = Field(default="web", max_length=40)


class ResetRequest(BaseModel):
    group: Optional[str] = Field(default=None, description="extruder | bed | robot | motion; all when omitted")


class CaptureRequest(BaseModel):
    target: str = Field(description="robot.home_joints or robot.bed_points.<p1|p2|p3|p4|center>")


async def _effective() -> dict[str, Optional[dict[str, Any]]]:
    """What print_node and extruder_controller are running with, or None
    per node when it cannot be asked (bridge down, node not up)."""
    bridge = deps.get_bridge()
    if bridge is None or not bridge.running:
        return {"print_node": None, "extruder_controller": None}
    pn, ex = await asyncio.gather(
        bridge.get_parameters("print_node", list(PRINT_NODE_PARAMS), EFFECTIVE_TIMEOUT_S),
        bridge.get_parameters("extruder_controller", list(EXTRUDER_PARAMS), EFFECTIVE_TIMEOUT_S),
    )
    return {"print_node": pn, "extruder_controller": ex}


async def apply_hot() -> dict[str, Any]:
    """Push the saved hot parameters into the running print_node.

    Only the ones whose running value differs are sent, in one atomic
    batch. print_node refuses while a print runs; the values then stay
    saved and show as pending until the next apply or restart."""
    store = deps.cell_settings
    bridge = deps.get_bridge()
    if store is None or bridge is None or not bridge.running:
        return {"applied": [], "apply_error": "ROS not available"}
    wanted = ros_overlay(store.get())["print_node"]["ros__parameters"]
    live = await bridge.get_parameters("print_node", list(HOT_PRINT_NODE_PARAMS), EFFECTIVE_TIMEOUT_S)
    if live is None:
        return {"applied": [], "apply_error": "print_node not reachable"}
    changed = {k: wanted[k] for k in HOT_PRINT_NODE_PARAMS
               if k in wanted and not same_value(wanted[k], live.get(k))}
    if not changed:
        return {"applied": [], "apply_error": None}
    ok, reason = await bridge.set_parameters("print_node", changed)
    if not ok:
        return {"applied": [], "apply_error": reason or "rejected by print_node"}
    return {"applied": sorted(changed), "apply_error": None}


def _restart_requested_at() -> Optional[float]:
    try:
        return os.path.getmtime(os.path.join(env.data_dir, RESTART_REQUEST))
    except OSError:
        return None


async def _document(apply: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    store = deps.require_cell_settings()
    cs = store.get()
    effective = await _effective()
    diff = restart_diff(ros_overlay(cs), effective)
    return {
        "settings": cs.model_dump(),
        "defaults": store.defaults.model_dump(),
        "extruder_profiles": store.extruder_profiles(),
        "effective": effective,
        # None = unknown (ROS not reachable); [] = everything applied.
        "restart_required": None if diff is None else bool(diff),
        "pending": diff,
        "restart_requested_at": _restart_requested_at(),
        "updated_at": store.updated_at,
        "history": store.history(),
        "paths": {"settings": store.path, "overlay": store.overlay_path},
        # Result of pushing hot parameters to print_node on this request.
        "applied": (apply or {}).get("applied", []),
        "apply_error": (apply or {}).get("apply_error"),
    }


@router.get("/settings")
async def get_settings():
    return await _document()


@router.put("/settings")
async def update_settings(body: SettingsPatch):
    store = deps.require_cell_settings()
    try:
        store.update(body.patch, source=body.source)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=[
            {"loc": ".".join(str(x) for x in err["loc"]), "msg": err["msg"]} for err in e.errors()
        ])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return await _document(await apply_hot())


@router.post("/settings/reset")
async def reset_settings(body: ResetRequest):
    store = deps.require_cell_settings()
    try:
        store.reset(body.group)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return await _document(await apply_hot())


@router.post("/settings/capture")
async def capture_pose(body: CaptureRequest):
    """Store the robot's current joint pose as the home pose or as a bed
    reference point. Needs live joint states (a robot, or URSim)."""
    store = deps.require_cell_settings()
    bridge = deps.require_bridge()
    age = bridge.joint_states_age()
    if age is None or age > 2.0:
        raise HTTPException(status_code=409, detail="no fresh joint states: is the robot connected?")
    joints = [float(x) for x in bridge.latest_state["joint_states"]["positions"]]
    if body.target == "robot.home_joints":
        patch = {"robot": {"home_joints": joints}}
    elif body.target.startswith("robot.bed_points."):
        name = body.target.split(".", 2)[2]
        if name not in BED_POINT_NAMES:
            raise HTTPException(status_code=422, detail=f"bed point must be one of {BED_POINT_NAMES}")
        patch = {"robot": {"bed_points": {name: joints}}}
    else:
        raise HTTPException(status_code=422, detail="target must be robot.home_joints or robot.bed_points.<name>")
    store.update(patch, source="capture")
    return await _document(await apply_hot())


@router.post("/settings/restart")
async def request_restart():
    """Ask ur-printer to relaunch its ROS stack with the current overlay.
    The container watches this file (see docker-compose.yml)."""
    deps.require_cell_settings()
    path = os.path.join(env.data_dir, RESTART_REQUEST)
    with open(path, "w") as f:
        f.write(f"{time.time():.0f} web\n")
    os.utime(path, None)
    return {"success": True, "requested_at": os.path.getmtime(path)}
