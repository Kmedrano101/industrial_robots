"""Robot status + commissioning endpoints.

Exposed to the browser as a "Test" panel for bring-up / commissioning. All
write endpoints (dashboard commands, jog, move_to_home) are gated by
``settings.enable_test_panel`` — set ``ENABLE_TEST_PANEL=true`` in the
environment to enable them. The read-only status endpoint is always
available so the regular Live panel can show robot mode / safety mode.

Safety-critical caps (jog delta / velocity / minimum duration) are
applied server-side and CANNOT be bypassed by the client.
"""

from __future__ import annotations

import logging
import math
from typing import Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
from backend import ros_bridge as rb_module

logger = logging.getLogger(__name__)
router = APIRouter()


# Predefined safe home poses per UR model. Joint order matches
# `RosBridge.joint_names`. These keep the arm in a known, collision-free
# pose with the TCP roughly above the base — adjust per cell.
HOME_POSES: dict[str, List[float]] = {
    "ur3e": [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0],
    "ur5e": [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0],
    "ur7e": [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0],
    "ur10e": [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0],
    "ur12e": [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0],
    "ur16e": [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0],
    "ur20": [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0],
    "ur30": [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0],
}


# ── Pydantic models ─────────────────────────────────────────────────────


class RobotModeState(BaseModel):
    mode: int
    mode_name: str


class JointPositions(BaseModel):
    positions: List[float]


class RobotStatus(BaseModel):
    test_panel_enabled: bool
    ros2_connected: bool
    ur_type: str
    joint_names: List[str]
    joint_states: JointPositions
    robot_mode: RobotModeState
    safety_mode: RobotModeState
    motion_allowed: bool = Field(
        description="True iff dashboard commands are accepted right now "
                    "(test panel on, robot reachable, safety NORMAL)."
    )


class JogRequest(BaseModel):
    joint_index: int = Field(ge=0, le=5, description="0=base, 5=wrist 3")
    delta_rad: float = Field(description="Signed angular delta")
    duration_s: float = Field(
        default=1.0, gt=0,
        description="Time to execute the move (clamped server-side)",
    )


class CommandResponse(BaseModel):
    success: bool
    message: str = ""


# ── Helpers ─────────────────────────────────────────────────────────────


def _bridge():
    """Return the active RosBridge singleton or 503."""
    bridge = rb_module.ros_bridge
    if bridge is None:
        raise HTTPException(
            status_code=503, detail="ROS bridge not initialised"
        )
    return bridge


def _require_test_panel():
    if not settings.enable_test_panel:
        raise HTTPException(
            status_code=403,
            detail="Test panel disabled. Set ENABLE_TEST_PANEL=true to enable.",
        )


async def _call_trigger(client, name: str) -> CommandResponse:
    """Call a std_srvs/Trigger service via the bridge."""
    if client is None:
        raise HTTPException(
            status_code=503, detail=f"{name} service client unavailable"
        )
    try:
        from std_srvs.srv import Trigger  # noqa: WPS433
    except ImportError:
        raise HTTPException(
            status_code=503, detail="rclpy / std_srvs not available"
        )

    if not client.service_is_ready():
        client.wait_for_service(timeout_sec=1.0)
    if not client.service_is_ready():
        raise HTTPException(
            status_code=504, detail=f"{name}: service not reachable",
        )

    bridge = _bridge()
    result = await bridge.call_service(client, Trigger.Request(), timeout=5.0)
    if result is None:
        raise HTTPException(status_code=504, detail=f"{name}: timeout")
    return CommandResponse(success=bool(result.success), message=result.message)


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get("/robot/status", response_model=RobotStatus)
async def robot_status():
    """Always-on, read-only snapshot of the robot's state."""
    bridge = rb_module.ros_bridge
    if bridge is None:
        # Backend running in standalone mode (no ROS). Return a blank
        # snapshot so the UI can still render.
        return RobotStatus(
            test_panel_enabled=settings.enable_test_panel,
            ros2_connected=False,
            ur_type=settings.ur_type,
            joint_names=[
                "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
                "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
            ],
            joint_states=JointPositions(positions=[0.0] * 6),
            robot_mode=RobotModeState(mode=-1, mode_name="UNKNOWN"),
            safety_mode=RobotModeState(mode=0, mode_name="UNKNOWN"),
            motion_allowed=False,
        )

    rm = bridge.latest_state.get("robot_mode", {"mode": -1, "mode_name": "UNKNOWN"})
    sm = bridge.latest_state.get("safety_mode", {"mode": 0, "mode_name": "UNKNOWN"})
    js = bridge.latest_state.get("joint_states", {"positions": [0.0] * 6})

    motion_allowed = (
        settings.enable_test_panel
        and rm.get("mode_name") in {"IDLE", "RUNNING"}
        and sm.get("mode_name") == "NORMAL"
    )

    return RobotStatus(
        test_panel_enabled=settings.enable_test_panel,
        ros2_connected=rm.get("mode_name") not in ("UNKNOWN", "DISCONNECTED"),
        ur_type=settings.ur_type,
        joint_names=list(bridge.joint_names),
        joint_states=JointPositions(positions=js.get("positions", [0.0] * 6)),
        robot_mode=RobotModeState(**rm),
        safety_mode=RobotModeState(**sm),
        motion_allowed=motion_allowed,
    )


@router.post("/robot/power_on", response_model=CommandResponse)
async def power_on():
    _require_test_panel()
    return await _call_trigger(_bridge().power_on_client, "power_on")


@router.post("/robot/power_off", response_model=CommandResponse)
async def power_off():
    _require_test_panel()
    return await _call_trigger(_bridge().power_off_client, "power_off")


@router.post("/robot/brake_release", response_model=CommandResponse)
async def brake_release():
    _require_test_panel()
    return await _call_trigger(_bridge().brake_release_client, "brake_release")


@router.post("/robot/play", response_model=CommandResponse)
async def play():
    _require_test_panel()
    return await _call_trigger(_bridge().play_client, "play")


@router.post("/robot/stop", response_model=CommandResponse)
async def stop():
    """Stops the running URScript program. Always allowed regardless of
    ENABLE_TEST_PANEL — this is the e-stop equivalent from the browser."""
    return await _call_trigger(_bridge().stop_client, "stop")


@router.post("/robot/jog", response_model=CommandResponse)
async def jog(req: JogRequest):
    """Move one joint by ``delta_rad`` over ``duration_s``.

    Server-side hard caps:
      * ``|delta_rad|`` ≤ ``settings.jog_max_delta_rad`` (default 5°)
      * derived velocity ≤ ``settings.jog_max_velocity_rad_s``
      * ``duration_s`` ≥ ``settings.jog_min_duration_s``
    """
    _require_test_panel()
    bridge = _bridge()

    if abs(req.delta_rad) > settings.jog_max_delta_rad + 1e-9:
        raise HTTPException(
            status_code=400,
            detail=(
                f"|delta_rad|={abs(req.delta_rad):.4f} exceeds the "
                f"{settings.jog_max_delta_rad:.4f} rad server cap"
            ),
        )

    duration = max(settings.jog_min_duration_s, float(req.duration_s))
    velocity = abs(req.delta_rad) / duration
    if velocity > settings.jog_max_velocity_rad_s + 1e-9:
        # Lengthen the duration to bring velocity within the cap rather
        # than rejecting outright — clients can't always know the cap.
        duration = abs(req.delta_rad) / settings.jog_max_velocity_rad_s

    current = bridge.latest_state.get("joint_states", {}).get(
        "positions", [0.0] * 6
    )
    if len(current) != 6:
        raise HTTPException(
            status_code=503,
            detail="joint_states not yet available — is the driver up?",
        )

    target = list(current)
    target[req.joint_index] = float(target[req.joint_index] + req.delta_rad)

    try:
        ok = bridge.publish_joint_trajectory(target, duration_s=duration)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not ok:
        raise HTTPException(
            status_code=503, detail="joint_trajectory publisher unavailable",
        )

    return CommandResponse(
        success=True,
        message=(
            f"jog joint {req.joint_index} by {req.delta_rad:+.4f} rad "
            f"over {duration:.2f} s"
        ),
    )


@router.post("/robot/move_to_home", response_model=CommandResponse)
async def move_to_home():
    """Send the configured HOME pose for the current UR_TYPE."""
    _require_test_panel()
    bridge = _bridge()

    pose = HOME_POSES.get(settings.ur_type.lower())
    if pose is None:
        raise HTTPException(
            status_code=400,
            detail=f"No home pose defined for ur_type={settings.ur_type}",
        )

    # Conservative duration: 4 s, plenty of margin under the velocity cap
    # for ±90° joint motions.
    try:
        ok = bridge.publish_joint_trajectory(pose, duration_s=4.0)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(
            status_code=503, detail="joint_trajectory publisher unavailable",
        )
    return CommandResponse(success=True, message="move_to_home dispatched")
