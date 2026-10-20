"""Print control endpoints — start, pause, resume, cancel, calibrate."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend import deps
from backend.deps import require_bridge
from backend.models.requests import (
    CalibrateOriginRequest,
    CancelPrintRequest,
    StartPrintRequest,
)
from backend.models.responses import ServiceResponse
from backend.ros_bridge import RosBridge

router = APIRouter()


# StartPrint parses the G-code, validates reachability and waits for the
# kinematics/driver services before answering — 30 s without a robot.
# CalibrateOrigin reads the live pose through the same services.
START_TIMEOUT_S = 60.0
CALIBRATE_TIMEOUT_S = 30.0


async def _call(bridge: RosBridge, client, request, name: str, timeout: float = 5.0):
    """Call a print_node service, mapping the failure modes to HTTP codes:
    no client (interfaces not built into this image) → 503, no answer
    within the timeout → 504."""
    if client is None:
        raise HTTPException(status_code=503, detail=f"{name} service not available")
    result = await bridge.call_service(client, request, timeout=timeout)
    if result is None:
        raise HTTPException(status_code=504, detail=f"{name}: service call timed out")
    return result


def _response(result, data: Optional[dict[str, Any]] = None) -> ServiceResponse:
    return ServiceResponse(success=bool(result.success), message=result.message, data=data)


@router.post("/print/start", response_model=ServiceResponse)
async def start_print(
    request: StartPrintRequest, bridge: RosBridge = Depends(require_bridge)
):
    """Start a print job with a sliced G-code file."""
    from ur_3d_printer.srv import StartPrint

    req = StartPrint.Request()
    req.gcode_filepath = request.gcode_filepath
    req.validate_only = request.validate_only

    result = await _call(bridge, bridge.start_print_client, req, "StartPrint", START_TIMEOUT_S)
    if not request.validate_only and deps.jobs is not None:
        meta = {
            **(request.meta or {}),
            "gcode_path": request.gcode_filepath,
            "num_layers": result.num_layers,
            "estimated_time": result.estimated_time,
        }
        if result.success:
            deps.jobs.start(meta)
        else:
            # print_node may have left IDLE before rejecting (parse or
            # validation failure); the bridge then recorded the attempt.
            deps.jobs.annotate_recent(meta)
    return _response(
        result,
        {"num_layers": result.num_layers, "estimated_time": result.estimated_time},
    )


@router.post("/print/pause", response_model=ServiceResponse)
async def pause_print(bridge: RosBridge = Depends(require_bridge)):
    """Pause the current print."""
    from ur_3d_printer.srv import PausePrint

    result = await _call(bridge, bridge.pause_print_client, PausePrint.Request(), "PausePrint")
    return _response(result)


@router.post("/print/resume", response_model=ServiceResponse)
async def resume_print(bridge: RosBridge = Depends(require_bridge)):
    """Resume a paused print."""
    from ur_3d_printer.srv import ResumePrint

    result = await _call(bridge, bridge.resume_print_client, ResumePrint.Request(), "ResumePrint")
    return _response(result)


@router.post("/print/cancel", response_model=ServiceResponse)
async def cancel_print(
    request: CancelPrintRequest, bridge: RosBridge = Depends(require_bridge)
):
    """Cancel the current print."""
    from ur_3d_printer.srv import CancelPrint

    req = CancelPrint.Request()
    req.retract_and_home = request.retract_and_home

    result = await _call(bridge, bridge.cancel_print_client, req, "CancelPrint")
    if result.success and deps.jobs is not None:
        deps.jobs.request_cancel()
    return _response(result)


@router.post("/calibrate", response_model=ServiceResponse)
async def calibrate_origin(
    request: CalibrateOriginRequest, bridge: RosBridge = Depends(require_bridge)
):
    """Calibrate the print origin."""
    from geometry_msgs.msg import Point, Vector3
    from ur_3d_printer.srv import CalibrateOrigin

    req = CalibrateOrigin.Request()
    req.use_current_pose = request.use_current_pose

    if request.origin_xyz:
        req.origin_xyz = Point(
            x=request.origin_xyz.get("x", 0.0),
            y=request.origin_xyz.get("y", 0.0),
            z=request.origin_xyz.get("z", 0.0),
        )
    if request.origin_rpy:
        req.origin_rpy = Vector3(
            x=request.origin_rpy.get("r", 0.0),
            y=request.origin_rpy.get("p", 0.0),
            z=request.origin_rpy.get("y", 0.0),
        )

    result = await _call(bridge, bridge.calibrate_client, req, "CalibrateOrigin", CALIBRATE_TIMEOUT_S)
    return _response(result, {"print_frame": list(result.print_frame)})
