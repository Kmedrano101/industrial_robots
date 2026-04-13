"""Health check, state, and bridge endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings
from backend.models.responses import HealthResponse
from backend.ros_bridge import ROS2_AVAILABLE, ros_bridge
from backend.websocket_manager import ws_manager

router = APIRouter()

# Cache for bridge data (works without ROS2)
_bridge_cache: dict = {}


class JointUpdate(BaseModel):
    positions: list[float]


class StateUpdate(BaseModel):
    state: int
    state_name: str
    error_message: str = ""


class ProgressUpdate(BaseModel):
    current_layer: int = 0
    total_layers: int = 0
    layer_progress: float = 0.0
    overall_progress: float = 0.0
    elapsed_time: float = 0.0
    estimated_remaining: float = 0.0
    current_z_height: float = 0.0


@router.post("/bridge/joints")
async def bridge_joints(update: JointUpdate):
    """Receive joint states from an external bridge."""
    if len(update.positions) >= 6:
        data = {"positions": update.positions[:6]}
        _bridge_cache["joint_states"] = data
        await ws_manager.broadcast("joint_states", data)
    return {"ok": True}


@router.post("/bridge/state")
async def bridge_state(update: StateUpdate):
    """Receive print state from an external bridge."""
    data = update.model_dump()
    _bridge_cache["print_state"] = data
    await ws_manager.broadcast("print_state", data)
    return {"ok": True}


@router.post("/bridge/progress")
async def bridge_progress(update: ProgressUpdate):
    """Receive print progress from an external bridge."""
    data = update.model_dump()
    _bridge_cache["print_progress"] = data
    await ws_manager.broadcast("print_progress", data)
    return {"ok": True}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check backend health and ROS2 connectivity."""
    return HealthResponse(
        status="ok",
        ros2_connected=ROS2_AVAILABLE and ros_bridge is not None,
        websocket_clients=ws_manager.connection_count,
    )


@router.get("/state")
async def get_state():
    """Return the latest cached state snapshot for reconnection recovery."""
    if ros_bridge is None:
        return {
            "print_state": {"state": 0, "state_name": "IDLE", "error_message": ""},
            "print_progress": {
                "current_layer": 0,
                "total_layers": 0,
                "overall_progress": 0.0,
                "elapsed_time": 0.0,
                "estimated_remaining": 0.0,
                "current_z_height": 0.0,
            },
            "extruder_state": {"state": 0, "extrusion_rate": 0.0, "temperature": 0.0},
            "joint_states": _bridge_cache.get("joint_states", {"positions": [0.0] * 6}),
        }
    return ros_bridge.latest_state
