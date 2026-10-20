"""Extruder control endpoint."""

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import require_bridge
from backend.models.requests import SetExtruderRequest
from backend.models.responses import ServiceResponse
from backend.ros_bridge import RosBridge

router = APIRouter()


@router.post("/extruder", response_model=ServiceResponse)
async def set_extruder(
    request: SetExtruderRequest, bridge: RosBridge = Depends(require_bridge)
):
    """Control the extruder (enable/disable, rate, retract, prime)."""
    if bridge.extruder_client is None:
        raise HTTPException(status_code=503, detail="SetExtruder service not available")

    from ur_3d_printer.srv import SetExtruder

    req = SetExtruder.Request()
    req.enable = request.enable
    req.rate = request.rate
    req.retract = request.retract
    req.prime = request.prime

    result = await bridge.call_service(bridge.extruder_client, req)
    if result is None:
        raise HTTPException(status_code=504, detail="SetExtruder: service call timed out")

    return ServiceResponse(success=bool(result.success), message=result.message)
