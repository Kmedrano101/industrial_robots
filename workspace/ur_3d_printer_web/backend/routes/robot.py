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
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
from backend import ros_bridge as rb_module
from backend.deps import require_bridge

logger = logging.getLogger(__name__)
router = APIRouter()


# Home pose and bed reference points come from the cell settings
# (settings.yaml in the data volume; factory defaults in
# backend.cell_settings), so they can be captured from the pendant pose
# through the UI instead of being edited here.
def _cell():
    from backend import deps
    from backend.cell_settings import default_settings

    store = deps.cell_settings
    return store.get() if store is not None else default_settings(ur_type=settings.ur_type)


def _home_pose() -> List[float]:
    return list(_cell().robot.home_joints)


def _bed_points() -> dict[str, List[float]]:
    return {k: list(v) for k, v in _cell().robot.bed_points.items()}


# Cartesian limits of the (temporary test) bed, DERIVED via forward kinematics
# from the corner poses above (flange/tool0 in the robot base_link frame, in
# metres). The 4 corners are coplanar at z≈0.111 m and span ~501x500 mm.
# Verified: the center pose sits on the corners' centroid within 0.2 mm.
# NOTE: these are flange positions; the extruder TCP tip is offset ~0.105 m
# along -Z. Useful as workspace bounds for the slicer / reachability checks.
BED_LIMITS: dict[str, Any] = {
    "frame": "base_link",
    "x": [-0.2481, 0.2526],
    "y": [-0.7825, -0.2828],
    "z": 0.1113,
    "center": [0.0023, -0.5326, 0.1113],
    "size_mm": [500.7, 499.7],
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
    # A — External Control program running + data freshness.
    program_running: bool = False
    joint_states_age_s: Optional[float] = None
    # C — motion-control / active trajectory controller.
    motion_control_enabled: bool = False
    active_trajectory_controller: str = "none"
    # E — key node liveness: {key: {"label": str, "alive": bool}}.
    nodes: dict[str, Any] = Field(default_factory=dict)


class MotionControlRequest(BaseModel):
    enable: bool = Field(description="True activates the jog/print controller; "
                                     "False deactivates all motion controllers.")


class GotoBedPointRequest(BaseModel):
    point: str = Field(description="Name of a bed reference point (p1..p4, center)")


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
    """Return the running RosBridge singleton or 503."""
    return require_bridge()


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

    ctrl = bridge.latest_state.get("controllers", {})

    return RobotStatus(
        test_panel_enabled=settings.enable_test_panel,
        ros2_connected=rm.get("mode_name") not in ("UNKNOWN", "DISCONNECTED"),
        ur_type=settings.ur_type,
        joint_names=list(bridge.joint_names),
        joint_states=JointPositions(positions=js.get("positions", [0.0] * 6)),
        robot_mode=RobotModeState(**rm),
        safety_mode=RobotModeState(**sm),
        motion_allowed=motion_allowed,
        program_running=bool(bridge.latest_state.get("program_running", False)),
        joint_states_age_s=bridge.joint_states_age(),
        motion_control_enabled=bool(ctrl.get("motion_control_enabled", False)),
        active_trajectory_controller=ctrl.get("active_trajectory_controller", "none"),
        nodes=bridge.latest_state.get("nodes", {}),
    )


@router.post("/robot/motion_control", response_model=CommandResponse)
async def motion_control(req: MotionControlRequest):
    """Enable/disable the ability to move the robot. Neither path commands
    motion by itself.

    enable=True:  start the External Control program (connect the reverse
                  interface) if not already running, then activate the
                  jog/print trajectory controller.
    enable=False: deactivate the trajectory controllers (read-only); the
                  External Control program is left running.
    """
    _require_test_panel()
    bridge = _bridge()
    import asyncio

    steps: list[str] = []

    if req.enable:
        # 1. Ensure External Control is running first. The driver's
        #    controller_stopper (re)activates the default controller when the
        #    program starts, so play BEFORE switching controllers.
        if not bridge.latest_state.get("program_running", False):
            await _call_trigger(bridge.play_client, "play")
            steps.append("External Control started")
            await asyncio.sleep(2.0)  # let controller_stopper settle
        else:
            steps.append("External Control already running")

    # 2. Switch the motion controller (activate scaled / deactivate all).
    ok, msg = await bridge.switch_motion_control(req.enable)
    if not ok:
        raise HTTPException(status_code=503, detail=msg)
    steps.append(msg)
    return CommandResponse(success=True, message="; ".join(steps))


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

    pose = _home_pose()

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


@router.get("/robot/bed_points")
async def bed_points():
    """Read-only: configurable print-bed reference poses (corners + center).

    Returns each point's joint pose in rad and deg. Always allowed."""
    out = {}
    for name, pose in _bed_points().items():
        out[name] = {
            "rad": [round(float(p), 6) for p in pose],
            "deg": [round(math.degrees(p), 2) for p in pose],
        }
    return {"joint_names": [
        "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
        "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
    ], "points": out, "limits": BED_LIMITS}


@router.get("/robot/home_pose")
async def home_pose():
    """Read-only: the configured HOME pose (rad + deg) for the current
    UR_TYPE. Always allowed — lets the frontend rehearse "move to home" in
    its disconnected simulation view using the exact same target the real
    /robot/move_to_home dispatches, with a single source of truth
    (the cell settings) instead of duplicating the pose client-side."""
    pose = _home_pose()
    return {
        "joint_names": [
            "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
            "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
        ],
        "rad": [round(float(p), 6) for p in pose],
        "deg": [round(math.degrees(p), 2) for p in pose],
    }


@router.post("/robot/goto_bed_point", response_model=CommandResponse)
async def goto_bed_point(req: GotoBedPointRequest):
    """Move to a configured bed reference point. Gated by the test panel;
    requires motion control enabled. This MOVES the robot."""
    _require_test_panel()
    bridge = _bridge()

    points = _bed_points()
    pose = points.get(req.point.lower())
    if pose is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown bed point {req.point!r}. Available: {list(points)}",
        )
    try:
        ok = bridge.publish_joint_trajectory(pose, duration_s=6.0)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(
            status_code=503, detail="joint_trajectory publisher unavailable",
        )
    return CommandResponse(success=True, message=f"goto bed point {req.point} dispatched")
