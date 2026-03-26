"""File upload endpoint for STL files."""

import os
import time
import re

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from backend.config import settings
from backend.models.responses import UploadResponse
from backend.slicer_service import get_stl_info

router = APIRouter()

ALLOWED_EXTENSIONS = {".stl"}
MAX_SIZE = settings.max_upload_size_mb * 1024 * 1024


def _sanitize_filename(filename: str) -> str:
    """Remove unsafe characters from filename."""
    name = os.path.basename(filename)
    name = re.sub(r"[^\w\-.]", "_", name)
    return name


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile):
    """Upload an STL file with validation."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb} MB",
        )

    if len(content) < 84:
        raise HTTPException(status_code=400, detail="File too small to be a valid STL")

    # Validate STL: binary STL starts with 80-byte header + 4-byte count
    # ASCII STL starts with "solid"
    is_ascii = content[:5].lower() == b"solid"
    if not is_ascii:
        try:
            import struct

            tri_count = struct.unpack("<I", content[80:84])[0]
            expected = 84 + tri_count * 50
            if len(content) < expected:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid binary STL: file size does not match triangle count",
                )
        except Exception as e:
            if "Invalid binary STL" in str(e):
                raise
            raise HTTPException(status_code=400, detail="Invalid STL file format")

    # Save file
    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = _sanitize_filename(file.filename)
    filename = f"{int(time.time())}_{safe_name}"
    filepath = os.path.join(settings.upload_dir, filename)

    with open(filepath, "wb") as f:
        f.write(content)

    # Get STL metadata
    try:
        stl_info = get_stl_info(filepath)
    except Exception:
        stl_info = {"bounding_box": None, "triangle_count": None}

    return UploadResponse(
        filepath=filepath,
        filename=safe_name,
        size=len(content),
        file_type="stl",
        bounding_box=stl_info.get("bounding_box"),
        triangle_count=stl_info.get("triangle_count"),
    )


@router.get("/stl-preview")
async def get_stl_preview(filepath: str = Query(...)):
    """Serve an uploaded STL file for 3D preview in the browser."""
    # Security: only serve files from the upload directory
    abs_path = os.path.abspath(filepath)
    abs_upload = os.path.abspath(settings.upload_dir)
    if not abs_path.startswith(abs_upload):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(abs_path, media_type="application/octet-stream")
