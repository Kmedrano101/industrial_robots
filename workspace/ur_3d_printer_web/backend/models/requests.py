"""Pydantic request models for the API endpoints."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SliceRequest(BaseModel):
    """Request to slice an uploaded STL file."""

    stl_filepath: str = Field(description="Server path to uploaded STL file")
    slicer_mode: Literal["planar", "multiaxis"] = "planar"
    layer_height: float = Field(default=1.0, gt=0, description="Layer height in mm")
    nozzle_diameter: float = Field(default=0.4, gt=0, description="Nozzle diameter in mm")
    print_speed: int = Field(default=3000, gt=0, description="Print speed in mm/min")
    travel_speed: int = Field(default=9000, gt=0, description="Travel speed in mm/min")
    scale: float = Field(default=1.0, gt=0, description="Scale factor")
    max_tilt: float = Field(
        default=30.0, ge=0, le=90, description="Max tilt angle in degrees (multiaxis only)"
    )


class StartPrintRequest(BaseModel):
    """Request to start a print job."""

    gcode_filepath: str = Field(description="Path to sliced G-code file")
    validate_only: bool = False


class CancelPrintRequest(BaseModel):
    """Request to cancel the current print."""

    retract_and_home: bool = True


class CalibrateOriginRequest(BaseModel):
    """Request to calibrate the print origin."""

    use_current_pose: bool = True
    origin_xyz: Optional[dict] = None
    origin_rpy: Optional[dict] = None


class SetExtruderRequest(BaseModel):
    """Request to control the extruder."""

    enable: bool
    rate: float = 0.0
    retract: bool = False
    prime: bool = False
