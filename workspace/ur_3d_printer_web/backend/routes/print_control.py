"""Print control endpoints — start, pause, resume, cancel, calibrate."""

from fastapi import APIRouter, HTTPException

from backend.models.requests import (
    CalibrateOriginRequest,
    CancelPrintRequest,
    StartPrintRequest,
)
from backend.models.responses import ServiceResponse
from backend.ros_bridge import ROS2_AVAILABLE, ros_bridge

router = APIRouter()


def _check_ros2():
    if not ROS2_AVAILABLE or ros_bridge is None:
        raise HTTPException(
            status_code=503, detail="ROS2 not available"
        )


@router.post("/print/start", response_model=ServiceResponse)
async def start_print(request: StartPrintRequest):
    """Start a print job with a sliced G-code file."""
    _check_ros2()
    if ros_bridge.start_print_client is None:
        raise HTTPException(status_code=503, detail="StartPrint service not available")

    from ur_3d_printer.srv import StartPrint

    req = StartPrint.Request()
    req.gcode_filepath = request.gcode_filepath
    req.validate_only = request.validate_only

    result = await ros_bridge.call_service(ros_bridge.start_print_client, req)
    if result is None:
        raise HTTPException(status_code=504, detail="Service call timed out")

    return ServiceResponse(
        success=result.success,
        message=result.message,
        data={
            "num_layers": result.num_layers,
            "estimated_time": result.estimated_time,
        },
    )


@router.post("/print/pause", response_model=ServiceResponse)
async def pause_print():
    """Pause the current print."""
    _check_ros2()
    if ros_bridge.pause_print_client is None:
        raise HTTPException(status_code=503, detail="PausePrint service not available")

    from ur_3d_printer.srv import PausePrint

    req = PausePrint.Request()
    result = await ros_bridge.call_service(ros_bridge.pause_print_client, req)
    if result is None:
        raise HTTPException(status_code=504, detail="Service call timed out")

    return ServiceResponse(success=result.success, message=result.message)


@router.post("/print/resume", response_model=ServiceResponse)
async def resume_print():
    """Resume a paused print."""
    _check_ros2()
    if ros_bridge.resume_print_client is None:
        raise HTTPException(status_code=503, detail="ResumePrint service not available")

    from ur_3d_printer.srv import ResumePrint

    req = ResumePrint.Request()
    result = await ros_bridge.call_service(ros_bridge.resume_print_client, req)
    if result is None:
        raise HTTPException(status_code=504, detail="Service call timed out")

    return ServiceResponse(success=result.success, message=result.message)


@router.post("/print/cancel", response_model=ServiceResponse)
async def cancel_print(request: CancelPrintRequest):
    """Cancel the current print."""
    _check_ros2()
    if ros_bridge.cancel_print_client is None:
        raise HTTPException(status_code=503, detail="CancelPrint service not available")

    from ur_3d_printer.srv import CancelPrint

    req = CancelPrint.Request()
    req.retract_and_home = request.retract_and_home

    result = await ros_bridge.call_service(ros_bridge.cancel_print_client, req)
    if result is None:
        raise HTTPException(status_code=504, detail="Service call timed out")

    return ServiceResponse(success=result.success, message=result.message)


@router.post("/calibrate", response_model=ServiceResponse)
async def calibrate_origin(request: CalibrateOriginRequest):
    """Calibrate the print origin."""
    _check_ros2()
    if ros_bridge.calibrate_client is None:
        raise HTTPException(
            status_code=503, detail="CalibrateOrigin service not available"
        )

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

    result = await ros_bridge.call_service(ros_bridge.calibrate_client, req)
    if result is None:
        raise HTTPException(status_code=504, detail="Service call timed out")

    return ServiceResponse(
        success=result.success,
        message=result.message,
        data={"print_frame": list(result.print_frame)},
    )
