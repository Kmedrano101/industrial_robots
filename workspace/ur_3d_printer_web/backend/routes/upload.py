"""File upload endpoint for STL files."""

import os
import re
import struct
import time
import uuid

import aiofiles
from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from backend.config import settings
from backend.models.responses import UploadResponse
from backend.slicer_service import get_stl_info

router = APIRouter()

ALLOWED_EXTENSIONS = {".stl"}
MAX_SIZE = settings.max_upload_size_mb * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
# 80-byte header + 4-byte triangle count: the smallest file that can be
# either STL flavour.
STL_HEADER_SIZE = 84


def _sanitize_filename(filename: str) -> str:
    """Remove unsafe characters from filename."""
    name = os.path.basename(filename)
    name = re.sub(r"[^\w\-.]", "_", name)
    return name


def validate_stl(header: bytes, total_size: int) -> None:
    """Raise 400 unless the header + size describe a plausible STL.

    ASCII STL starts with "solid"; binary STL is an 80-byte header, a
    uint32 triangle count, then 50 bytes per triangle."""
    if total_size < STL_HEADER_SIZE:
        raise HTTPException(status_code=400, detail="File too small to be a valid STL")
    if header[:5].lower() == b"solid":
        return
    tri_count = struct.unpack("<I", header[80:84])[0]
    if total_size < STL_HEADER_SIZE + tri_count * 50:
        raise HTTPException(
            status_code=400,
            detail="Invalid binary STL: file size does not match triangle count",
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile):
    """Upload an STL file with validation.

    The body is streamed to disk in chunks: a 100 MB mesh no longer has to
    fit in memory twice (once in the multipart buffer, once in `content`),
    and the size cap is enforced while receiving rather than after."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    os.makedirs(settings.upload_dir, exist_ok=True)
    safe_name = _sanitize_filename(file.filename)
    filename = f"{int(time.time())}_{safe_name}"
    filepath = os.path.join(settings.upload_dir, filename)
    # Write under a temporary name so a rejected or interrupted upload
    # never leaves a half-written file where the UI could pick it up.
    tmp_path = os.path.join(settings.upload_dir, f".{uuid.uuid4().hex}.part")

    size = 0
    header = b""
    try:
        async with aiofiles.open(tmp_path, "wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_SIZE:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File too large. Maximum size: {settings.max_upload_size_mb} MB",
                    )
                if len(header) < STL_HEADER_SIZE:
                    header += chunk[: STL_HEADER_SIZE - len(header)]
                await out.write(chunk)
        validate_stl(header, size)
        os.replace(tmp_path, filepath)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

    # Parsing the mesh is CPU work; keep it off the event loop.
    try:
        stl_info = await run_in_threadpool(get_stl_info, filepath)
    except Exception:
        stl_info = {"bounding_box": None, "triangle_count": None}

    return UploadResponse(
        filepath=filepath,
        filename=safe_name,
        size=size,
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
    if os.path.commonpath([abs_path, abs_upload]) != abs_upload:
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(abs_path, media_type="application/octet-stream")
