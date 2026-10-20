"""Slicing endpoint — converts uploaded STL to G-code with toolpath data."""

import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.config import settings
from backend.models.requests import SliceRequest
from backend.models.responses import SliceResponse
from backend.slicer_service import slice_multiaxis, slice_planar

logger = logging.getLogger(__name__)
router = APIRouter()

# Slicing is CPU-bound and can take tens of seconds on a dense mesh. It
# runs on a worker thread so the event loop keeps serving the WebSocket,
# health checks and — above all — the E-stop endpoint while it works.
# Only one slice runs at a time: two concurrent slices would double the
# memory of an already heavy operation and finish no sooner.
_slice_slot = asyncio.Semaphore(1)


def _upload_path(path: str) -> str:
    """Resolve and confine a client-supplied path to the upload directory."""
    abs_path = os.path.abspath(path)
    abs_upload = os.path.abspath(settings.upload_dir)
    if os.path.commonpath([abs_path, abs_upload]) != abs_upload:
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="STL file not found")
    return abs_path


@router.post("/slice", response_model=SliceResponse)
async def slice_stl(request: SliceRequest):
    """Slice an uploaded STL file and return toolpath data for visualization."""
    stl_path = _upload_path(request.stl_filepath)

    common = dict(
        stl_filepath=stl_path,
        upload_dir=settings.upload_dir,
        layer_height=request.layer_height,
        nozzle_diameter=request.nozzle_diameter,
        print_speed=request.print_speed,
        travel_speed=request.travel_speed,
        infill_pattern=request.infill_pattern,
        infill_density=request.infill_density,
        infill_angle_base=request.infill_angle_base,
        infill_angle_increment=request.infill_angle_increment,
    )

    async with _slice_slot:
        try:
            if request.slicer_mode == "multiaxis":
                result = await run_in_threadpool(
                    slice_multiaxis, max_tilt=request.max_tilt, **common
                )
            else:
                result = await run_in_threadpool(
                    slice_planar, scale=request.scale, **common
                )
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("slicing failed")
            raise HTTPException(status_code=500, detail=f"Slicing failed: {e}")

    return SliceResponse(
        gcode_filepath=result["gcode_filepath"],
        num_layers=result["num_layers"],
        estimated_time=result["estimated_time"],
        layers=result["layers"],
    )
