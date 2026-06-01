"""Slicing endpoint — converts uploaded STL to G-code with toolpath data."""

import os

from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.models.requests import SliceRequest
from backend.models.responses import SliceResponse
from backend.slicer_service import slice_multiaxis, slice_planar

router = APIRouter()


@router.post("/slice", response_model=SliceResponse)
async def slice_stl(request: SliceRequest):
    """Slice an uploaded STL file and return toolpath data for visualization."""
    if not os.path.isfile(request.stl_filepath):
        raise HTTPException(status_code=404, detail="STL file not found")

    try:
        if request.slicer_mode == "multiaxis":
            result = slice_multiaxis(
                stl_filepath=request.stl_filepath,
                upload_dir=settings.upload_dir,
                layer_height=request.layer_height,
                max_tilt=request.max_tilt,
                print_speed=request.print_speed,
                travel_speed=request.travel_speed,
                nozzle_diameter=request.nozzle_diameter,
                infill_pattern=request.infill_pattern,
                infill_density=request.infill_density,
                infill_angle_base=request.infill_angle_base,
                infill_angle_increment=request.infill_angle_increment,
            )
        else:
            result = slice_planar(
                stl_filepath=request.stl_filepath,
                upload_dir=settings.upload_dir,
                layer_height=request.layer_height,
                nozzle_diameter=request.nozzle_diameter,
                print_speed=request.print_speed,
                travel_speed=request.travel_speed,
                scale=request.scale,
                infill_pattern=request.infill_pattern,
                infill_density=request.infill_density,
                infill_angle_base=request.infill_angle_base,
                infill_angle_increment=request.infill_angle_increment,
            )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Slicing failed: {e}")

    return SliceResponse(
        gcode_filepath=result["gcode_filepath"],
        num_layers=result["num_layers"],
        estimated_time=result["estimated_time"],
        layers=result["layers"],
    )
