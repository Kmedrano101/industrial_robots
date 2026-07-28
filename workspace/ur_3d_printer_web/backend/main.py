"""FastAPI application — serves the web UI and bridges to ROS2."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

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


class StaticCacheControlMiddleware(BaseHTTPMiddleware):
    """Force revalidation for non-hashed static files.

    Vite content-hashes JS/CSS bundle filenames (assets/index-XXXXXXXX.js),
    so those are safe to cache forever -- a rebuild always gets a new URL.
    Everything else served by the StaticFiles mount below (index.html,
    locales/*.json, robots/*.urdf, meshes/*, the PWA manifest/sw.js) keeps
    a STABLE filename across rebuilds. StaticFiles sets ETag/Last-Modified
    but no Cache-Control, so without this middleware browsers are free to
    heuristically cache those responses indefinitely -- after a redeploy
    the frontend can end up running new JS against a stale locales JSON
    (missing translation keys render as raw "test.someKey" text) or a
    stale index.html, with no way to recover short of a hard refresh.
    `no-cache` still allows caching, it just forces a conditional GET
    (If-None-Match) on every request, which resolves to a cheap 304 when
    nothing changed and picks up new content immediately when it did.
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/"):
            return response
        if path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response


app.add_middleware(StaticCacheControlMiddleware)

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
