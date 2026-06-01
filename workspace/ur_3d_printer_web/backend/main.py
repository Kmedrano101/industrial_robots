"""FastAPI application — serves the web UI and bridges to ROS2."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routes import extruder, health, print_control, robot, slice, upload
from backend.websocket_manager import ws_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown: ROS2 bridge + WebSocket heartbeat."""
    from backend import ros_bridge as rb_module
    from backend.ros_bridge import RosBridge

    # Start ROS2 bridge
    bridge = RosBridge(ws_broadcast_fn=ws_manager.broadcast)
    bridge.start()
    rb_module.ros_bridge = bridge

    # Start WebSocket heartbeat
    heartbeat_task = asyncio.create_task(ws_manager.heartbeat_loop())

    logger.info("Web interface backend started on port %d", settings.web_port)
    yield

    # Shutdown
    heartbeat_task.cancel()
    bridge.shutdown()
    logger.info("Web interface backend stopped")


app = FastAPI(
    title="UR 3D Printer Web Interface",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(slice.router, prefix="/api", tags=["slice"])
app.include_router(print_control.router, prefix="/api", tags=["print"])
app.include_router(extruder.router, prefix="/api", tags=["extruder"])
app.include_router(robot.router, prefix="/api", tags=["robot"])


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time ROS2 data streaming."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — client can send messages if needed
            data = await websocket.receive_text()
            # Currently no client→server messages expected
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


# Serve frontend static files (production build)
if os.path.isdir(settings.static_dir):
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.web_port,
        reload=True,
    )
