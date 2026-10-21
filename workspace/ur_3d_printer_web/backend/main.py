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
from backend.routes import (
    extruder, health, jobs, print_control, profiles, robot, settings as cell_settings_routes,
    slice, upload,
)
from backend.websocket_manager import ws_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown: ROS2 bridge + WebSocket heartbeat."""
    import os

    from backend import deps
    from backend import ros_bridge as rb_module
    from backend.cell_settings import CellSettingsStore, default_settings
    from backend.jobs import JobStore
    from backend.profiles import ProfileStore
    from backend.ros_bridge import RosBridge

    # Persistent stores (job history, profiles) under the data directory.
    os.makedirs(settings.data_dir, exist_ok=True)
    deps.jobs = JobStore(os.path.join(settings.data_dir, "jobs.sqlite"))
    deps.profiles = ProfileStore(os.path.join(settings.data_dir, "profiles.json"))
    deps.cell_settings = CellSettingsStore(
        os.path.join(settings.data_dir, "settings.yaml"),
        defaults=default_settings(
            os.path.join(settings.ros_pkg_dir, "config", "print_params.yaml"),
            ur_type=settings.ur_type,
            extruder_profile=settings.extruder_profile,
            extruder_driver=settings.extruder_driver,
            extruder_serial_port=settings.extruder_serial_port,
        ),
        overlay_path=os.path.join(settings.data_dir, "ros_params.yaml"),
        profiles_dir=os.path.join(settings.ros_pkg_dir, "config", "extruders"),
    )

    # Start ROS2 bridge
    bridge = RosBridge(
        ws_broadcast_fn=ws_manager.broadcast,
        joint_state_hz=settings.joint_state_throttle_hz,
    )
    bridge.jobs = deps.jobs
    bridge.start()
    rb_module.ros_bridge = bridge

    # Start WebSocket heartbeat
    heartbeat_task = asyncio.create_task(ws_manager.heartbeat_loop())

    logger.info("Web interface backend started on port %d", settings.web_port)
    yield

    # Shutdown
    heartbeat_task.cancel()
    bridge.shutdown()
    rb_module.ros_bridge = None
    deps.jobs.close()
    deps.jobs = None
    deps.profiles = None
    deps.cell_settings = None
    logger.info("Web interface backend stopped")


app = FastAPI(
    title="UR 3D Printer Web Interface",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS. The wildcard origin cannot be combined with credentials — browsers
# reject such responses outright — so credentials are only enabled when an
# explicit origin list is configured.
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
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
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(cell_settings_routes.router, prefix="/api", tags=["settings"])
app.include_router(profiles.router, prefix="/api", tags=["profiles"])


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time ROS2 data streaming.

    On connect the client receives the full cached state as one
    ``snapshot`` frame, so a page load or reconnect shows the current
    robot/print state immediately instead of defaults until the next
    change is published."""
    from backend.deps import get_bridge

    await ws_manager.connect(websocket)
    try:
        bridge = get_bridge()
        if bridge is not None:
            if not await ws_manager.send(websocket, "snapshot", bridge.latest_state):
                return
        while True:
            # Keep connection alive — client can send messages if needed
            await websocket.receive_text()
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
