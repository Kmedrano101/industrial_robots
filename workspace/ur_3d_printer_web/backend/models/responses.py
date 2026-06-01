"""Pydantic response models for the API endpoints."""

from typing import Any, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Response from file upload."""

    filepath: str
    filename: str
    size: int
    file_type: str
    bounding_box: Optional[dict[str, float]] = None
    triangle_count: Optional[int] = None


class SliceResponse(BaseModel):
    """Response from slicing operation."""

    gcode_filepath: str
    num_layers: int
    estimated_time: float
    layers: list[dict[str, Any]]


class ServiceResponse(BaseModel):
    """Generic response from a ROS2 service call."""

    success: bool
    message: str
    data: Optional[dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    ros2_connected: bool
    websocket_clients: int
    test_panel_enabled: bool = False
