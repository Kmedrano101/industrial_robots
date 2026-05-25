"""Health check and state endpoints."""

from fastapi import APIRouter

from backend.config import settings
from backend.models.responses import HealthResponse
from backend.ros_bridge import ROS2_AVAILABLE, ros_bridge
from backend.websocket_manager import ws_manager

router = APIRouter()


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
            "joint_states": {"positions": [0.0] * 6},
        }
    return ros_bridge.latest_state
