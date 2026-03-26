"""STL slicing service wrapping existing ur_3d_printer slicer code."""

import logging
import os
import struct
import sys
import uuid
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# Add ur_3d_printer resource directory to path for slicer imports
_PACKAGE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "ur_3d_printer")
)
_RESOURCE_DIR = os.path.join(_PACKAGE_ROOT, "resource")
if _RESOURCE_DIR not in sys.path:
    sys.path.insert(0, _RESOURCE_DIR)
if _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, os.path.dirname(_PACKAGE_ROOT))

try:
    from ur_3d_printer.resource.stl_slicer import load_stl, to_gcode, slice_at_z, connect_segments
except ImportError:
    logger.warning("stl_slicer not available — using built-in STL loader only")
    load_stl = None
    to_gcode = None

try:
    from ur_3d_printer.resource.multiaxis_slicer import _toolpath_to_gcode
    from ur_3d_printer.multiaxis_planner import MultiAxisConfig, MultiAxisToolpathGenerator
except ImportError:
    logger.warning("multiaxis_slicer not available")
    _toolpath_to_gcode = None


def load_stl_file(filepath: str) -> np.ndarray:
    """Load an STL file and return triangle vertices as (N, 3, 3) array."""
    if load_stl is not None:
        return load_stl(filepath)

    # Fallback built-in loader
    with open(filepath, "rb") as f:
        header = f.read(80)
        raw = f.read()

    count = struct.unpack("<I", raw[:4])[0]
    dt = np.dtype([
        ("normal", "<f4", 3),
        ("v0", "<f4", 3),
        ("v1", "<f4", 3),
        ("v2", "<f4", 3),
        ("attr", "<u2"),
    ])
    data = np.frombuffer(raw[: 4 + count * 50], dtype=dt, offset=4)
    return np.stack([data["v0"], data["v1"], data["v2"]], axis=1)


def get_stl_info(filepath: str) -> dict[str, Any]:
    """Get STL file metadata: bounding box and triangle count."""
    triangles = load_stl_file(filepath)
    verts = triangles.reshape(-1, 3)
    return {
        "triangle_count": len(triangles),
        "bounding_box": {
            "x_min": float(verts[:, 0].min()),
            "x_max": float(verts[:, 0].max()),
            "y_min": float(verts[:, 1].min()),
            "y_max": float(verts[:, 1].max()),
            "z_min": float(verts[:, 2].min()),
            "z_max": float(verts[:, 2].max()),
        },
    }


def slice_planar(
    stl_filepath: str,
    upload_dir: str,
    layer_height: float = 1.0,
    nozzle_diameter: float = 0.4,
    print_speed: int = 3000,
    travel_speed: int = 9000,
    scale: float = 1.0,
) -> dict[str, Any]:
    """Slice an STL file using planar slicing and return metadata + toolpath."""
    if to_gcode is None:
        raise RuntimeError("stl_slicer module not available")

    triangles = load_stl_file(stl_filepath)

    gcode = to_gcode(
        triangles,
        layer_height=layer_height,
        nozzle_d=nozzle_diameter,
        print_speed=print_speed,
        travel_speed=travel_speed,
        scale=scale,
    )

    # Save G-code
    gcode_filename = f"{uuid.uuid4().hex}.gcode"
    gcode_filepath = os.path.join(upload_dir, gcode_filename)
    with open(gcode_filepath, "w") as f:
        f.write(gcode)

    # Extract toolpath layers for visualization
    layers = _extract_layers_from_gcode(gcode)

    num_layers = len(layers)
    # Rough time estimate: total extrusion length / print speed
    total_points = sum(len(layer["points"]) for layer in layers)
    estimated_time = total_points * 0.1  # rough estimate in seconds

    return {
        "gcode_filepath": gcode_filepath,
        "num_layers": num_layers,
        "estimated_time": estimated_time,
        "layers": layers,
    }


def slice_multiaxis(
    stl_filepath: str,
    upload_dir: str,
    layer_height: float = 1.0,
    max_tilt: float = 30.0,
    print_speed: int = 3000,
    travel_speed: int = 9000,
) -> dict[str, Any]:
    """Slice an STL file using multi-axis slicing."""
    if _toolpath_to_gcode is None:
        raise RuntimeError("multiaxis_slicer module not available")

    triangles = load_stl_file(stl_filepath)

    config = MultiAxisConfig(
        layer_height=layer_height / 1000.0,  # mm to meters
        max_tilt_angle=np.radians(max_tilt),
    )
    generator = MultiAxisToolpathGenerator(config)
    toolpath = generator.generate(triangles / 1000.0)  # mm to meters

    gcode = _toolpath_to_gcode(
        toolpath,
        print_speed=print_speed / 60.0,  # mm/min to mm/s
        travel_speed=travel_speed / 60.0,
    )

    gcode_filename = f"{uuid.uuid4().hex}_multiaxis.gcode"
    gcode_filepath = os.path.join(upload_dir, gcode_filename)
    with open(gcode_filepath, "w") as f:
        f.write(gcode)

    layers = _extract_layers_from_gcode(gcode)

    return {
        "gcode_filepath": gcode_filepath,
        "num_layers": len(layers),
        "estimated_time": sum(len(l["points"]) for l in layers) * 0.1,
        "layers": layers,
    }


def _extract_layers_from_gcode(gcode: str) -> list[dict[str, Any]]:
    """Parse G-code to extract layer-by-layer toolpath points for visualization."""
    layers: list[dict[str, Any]] = []
    current_layer: dict[str, Any] = {"z": 0.0, "index": 0, "points": []}
    current_z = 0.0
    current_x = 0.0
    current_y = 0.0

    for raw_line in gcode.splitlines():
        stripped = raw_line.strip()

        # Check for layer markers before stripping comments
        if stripped.startswith("; LAYER:") or stripped.startswith(";LAYER:"):
            if current_layer["points"]:
                layers.append(current_layer)
            layer_idx = len(layers)
            current_layer = {"z": current_z, "index": layer_idx, "points": []}
            continue

        # Strip comments for G-code parsing
        line = raw_line.split(";")[0].strip()
        if not line:
            continue

        if not (line.startswith("G0") or line.startswith("G1")):
            continue

        is_travel = line.startswith("G0")
        params = {}
        for token in line.split():
            if token[0] in "XYZEF" and len(token) > 1:
                try:
                    params[token[0]] = float(token[1:])
                except ValueError:
                    pass

        if "X" in params:
            current_x = params["X"]
        if "Y" in params:
            current_y = params["Y"]
        if "Z" in params:
            current_z = params["Z"]

        current_layer["z"] = current_z
        current_layer["points"].append({
            "x": current_x,
            "y": current_y,
            "z": current_z,
            "type": "travel" if is_travel else "extrude",
        })

    if current_layer["points"]:
        layers.append(current_layer)

    return layers
