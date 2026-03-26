"""Extruder control endpoint."""

from fastapi import APIRouter, HTTPException

from backend.models.requests import SetExtruderRequest
from backend.models.responses import ServiceResponse
from backend.ros_bridge import ROS2_AVAILABLE, ros_bridge

router = APIRouter()


@router.post("/extruder", response_model=ServiceResponse)
async def set_extruder(request: SetExtruderRequest):
    """Control the extruder (enable/disable, rate, retract, prime)."""
    if not ROS2_AVAILABLE or ros_bridge is None:
        raise HTTPException(status_code=503, detail="ROS2 not available")
    if ros_bridge.extruder_client is None:
        raise HTTPException(status_code=503, detail="SetExtruder service not available")

    from ur_3d_printer.srv import SetExtruder

    req = SetExtruder.Request()
    req.enable = request.enable
    req.rate = request.rate
    req.retract = request.retract
    req.prime = request.prime

    result = await ros_bridge.call_service(ros_bridge.extruder_client, req)
    if result is None:
        raise HTTPException(status_code=504, detail="Service call timed out")

    return ServiceResponse(success=result.success, message=result.message)
