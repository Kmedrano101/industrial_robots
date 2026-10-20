"""Health check and state endpoints."""

from fastapi import APIRouter

from backend.config import settings
from backend.deps import get_bridge
from backend.models.responses import HealthResponse
from backend.ros_bridge import RosBridge
from backend.websocket_manager import ws_manager

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check backend health and ROS2 connectivity."""
    bridge = get_bridge()
    return HealthResponse(
        status="ok",
        ros2_connected=bridge is not None and bridge.running,
        websocket_clients=ws_manager.connection_count,
        test_panel_enabled=settings.enable_test_panel,
    )


@router.get("/state")
async def get_state():
    """Return the latest cached state snapshot for reconnection recovery.

    The same snapshot is pushed over the WebSocket on connect (topic
    ``snapshot``); this endpoint remains for clients that poll."""
    bridge = get_bridge()
    if bridge is None:
        # Standalone mode: hand back the bridge's own defaults so the two
        # paths can never disagree about the shape of the state.
        return RosBridge(ws_broadcast_fn=None).latest_state
    return bridge.latest_state
