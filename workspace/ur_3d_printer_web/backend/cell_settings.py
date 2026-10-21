"""Cell settings: the operator-editable configuration of the printer cell.

One validated document (extruder, bed, robot, motion) kept as YAML in the
data directory, shared by every device in the cell, with a short change
history. Saving it also writes a ROS parameter overlay
(``ros_params.yaml``) that ``ur-printer`` loads after ``print_params.yaml``
on its next launch, so the YAML baked into the image becomes the factory
default and this file the live configuration.

Nothing here talks to ROS. Which values the running nodes actually use is
read back through the bridge (``RosBridge.get_parameters``) and compared
with the overlay by ``restart_diff`` — that comparison, not a flag, is what
tells the UI "restart required".
"""

from __future__ import annotations

import glob
import logging
import math
import os
import threading
import time
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

TWO_PI = 2 * math.pi
JOINT_NAMES = [
    "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
    "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
]
BED_POINT_NAMES = ("p1", "p2", "p3", "p4", "center")
SERIAL_BAUDS = (0, 9600, 19200, 38400, 57600, 115200, 230400, 250000, 500000, 1000000)
HISTORY_MAX = 50
VERSION = 1


def _check_len(name: str, n: int):
    def _v(v: list[float]) -> list[float]:
        if len(v) != n:
            raise ValueError(f"{name} needs {n} values, got {len(v)}")
        return [float(x) for x in v]
    return _v


def _check_joints(v: list[float]) -> list[float]:
    v = _check_len("joints", 6)(v)
    if any(abs(x) > TWO_PI for x in v):
        raise ValueError("joint angles must be within ±2π rad")
    return v


class ExtruderSettings(BaseModel):
    """Which extruder is mounted and how to reach it (restart to apply)."""

    profile: str = Field(default="mahor_v5_m12_pro", min_length=1, max_length=64,
                         pattern=r"^[A-Za-z0-9_.-]+$")
    driver: Literal["", "mock", "gcode_serial", "topic", "ur_io"] = "mock"
    serial_port: str = Field(default="", max_length=64, pattern=r"^(/dev/[A-Za-z0-9_./-]+)?$")
    serial_baud: int = 0

    @field_validator("serial_baud")
    @classmethod
    def _baud(cls, v: int) -> int:
        if v not in SERIAL_BAUDS:
            raise ValueError(f"serial_baud must be one of {SERIAL_BAUDS}")
        return v


class BedSettings(BaseModel):
    """Where the print frame sits in the robot base frame."""

    print_origin_xyz: list[float] = [-0.3, 0.0, -0.01]
    print_origin_rpy: list[float] = [0.0, 0.0, 0.0]
    bed_tilt_rx: float = Field(default=0.0, ge=-0.2, le=0.2)
    bed_tilt_ry: float = Field(default=0.0, ge=-0.2, le=0.2)
    z_hop_enabled: bool = True
    z_hop_height: float = Field(default=0.008, ge=0.0, le=0.05)
    size_mm: list[float] = [300.0, 300.0]

    @field_validator("print_origin_xyz")
    @classmethod
    def _xyz(cls, v):
        v = _check_len("print_origin_xyz", 3)(v)
        if any(abs(x) > 2.0 for x in v):
            raise ValueError("print origin must be within ±2 m of the base")
        return v

    @field_validator("print_origin_rpy")
    @classmethod
    def _rpy(cls, v):
        v = _check_len("print_origin_rpy", 3)(v)
        if any(abs(x) > TWO_PI for x in v):
            raise ValueError("print origin rotation must be within ±2π rad")
        return v

    @field_validator("size_mm")
    @classmethod
    def _size(cls, v):
        v = _check_len("size_mm", 2)(v)
        if any(not 50.0 <= x <= 3000.0 for x in v):
            raise ValueError("bed size must be 50–3000 mm")
        return v


class RobotSettings(BaseModel):
    """Poses and tool geometry measured on the cell."""

    home_joints: list[float] = [3.1416, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]
    tool_offset_xyz: list[float] = [0.0, 0.0, 0.105]
    tool_offset_rpy: list[float] = [0.0, 0.0, 0.0]
    bed_points: dict[str, list[float]] = {}

    @field_validator("home_joints")
    @classmethod
    def _home(cls, v):
        return _check_joints(v)

    @field_validator("tool_offset_xyz")
    @classmethod
    def _tool(cls, v):
        v = _check_len("tool_offset_xyz", 3)(v)
        if not 0.0 <= v[2] <= 0.6 or any(abs(x) > 0.3 for x in v[:2]):
            raise ValueError("tool offset z must be 0–0.6 m and x/y within ±0.3 m")
        return v

    @field_validator("tool_offset_rpy")
    @classmethod
    def _tool_rpy(cls, v):
        v = _check_len("tool_offset_rpy", 3)(v)
        if any(abs(x) > TWO_PI for x in v):
            raise ValueError("tool rotation must be within ±2π rad")
        return v

    @field_validator("bed_points")
    @classmethod
    def _points(cls, v):
        out = {}
        for name, joints in v.items():
            if name not in BED_POINT_NAMES:
                raise ValueError(f"bed point must be one of {BED_POINT_NAMES}, got {name!r}")
            out[name] = _check_joints(joints)
        return out


class MotionSettings(BaseModel):
    """Speed envelope of the arm while printing."""

    max_print_velocity: float = Field(default=0.05, ge=0.001, le=0.5)
    max_travel_velocity: float = Field(default=0.15, ge=0.001, le=1.0)
    max_acceleration: float = Field(default=0.5, ge=0.01, le=5.0)
    corner_blend_radius: float = Field(default=0.002, ge=0.0, le=0.02)
    singularity_velocity_scale: float = Field(default=0.3, ge=0.05, le=1.0)


class CellSettings(BaseModel):
    version: int = VERSION
    extruder: ExtruderSettings = ExtruderSettings()
    bed: BedSettings = BedSettings()
    robot: RobotSettings = RobotSettings()
    motion: MotionSettings = MotionSettings()


# ── defaults ──────────────────────────────────────────────────────────────

# Safe upright pose per UR model; the ur7e entry is the print-bed centre
# captured on the real cell from the teach pendant.
HOME_POSES: dict[str, list[float]] = {
    "ur7e": [-1.816539, -1.082977, 2.063154, 3.744953, 4.697728, 2.902657],
}
_GENERIC_HOME = [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0]

# Bed corners + centre of the temporary test bed, measured on the ur7e cell.
BED_REFERENCE_POSES: dict[str, list[float]] = {
    "p1": [-2.039243, -0.559029, 1.024508, 4.255462, 4.695110, 2.679779],
    "p2": [-1.421571, -0.553968, 1.011593, 4.272915, 4.702615, 3.297451],
    "p3": [-1.199739, -1.320865, 2.492330, 3.561344, 4.707328, 3.519456],
    "p4": [-2.647315, -1.320865, 2.508038, 3.521900, 4.695285, 2.071706],
    "center": [-1.816539, -1.082977, 2.063154, 3.744953, 4.697728, 2.902657],
}

_PRINT_NODE_KEYS = {
    "bed": ("print_origin_xyz", "print_origin_rpy", "bed_tilt_rx", "bed_tilt_ry",
            "z_hop_enabled", "z_hop_height"),
    "robot": ("home_joints", "tool_offset_xyz", "tool_offset_rpy"),
    "motion": ("max_print_velocity", "max_travel_velocity", "max_acceleration",
               "corner_blend_radius", "singularity_velocity_scale"),
}


def default_settings(
    print_params_path: Optional[str] = None,
    ur_type: str = "ur5e",
    extruder_profile: str = "mahor_v5_m12_pro",
    extruder_driver: str = "mock",
    extruder_serial_port: str = "",
) -> CellSettings:
    """Factory defaults: the package's print_params.yaml (when readable)
    plus the environment's extruder selection and the cell's measured poses."""
    pn: dict[str, Any] = {}
    if print_params_path and os.path.isfile(print_params_path):
        try:
            with open(print_params_path) as f:
                doc = yaml.safe_load(f) or {}
            pn = (doc.get("print_node") or {}).get("ros__parameters") or {}
        except (OSError, yaml.YAMLError) as e:
            logger.warning("cannot read %s: %s", print_params_path, e)
    groups: dict[str, dict[str, Any]] = {}
    for group, keys in _PRINT_NODE_KEYS.items():
        groups[group] = {k: pn[k] for k in keys if k in pn}
    groups["robot"]["home_joints"] = HOME_POSES.get(ur_type.lower(), pn.get("home_joints", _GENERIC_HOME))
    groups["robot"]["bed_points"] = dict(BED_REFERENCE_POSES) if ur_type.lower() == "ur7e" else {}
    return CellSettings(
        extruder=ExtruderSettings(profile=extruder_profile, driver=extruder_driver,
                                  serial_port=extruder_serial_port),
        bed=BedSettings(**groups["bed"]),
        robot=RobotSettings(**groups["robot"]),
        motion=MotionSettings(**groups["motion"]),
    )


# ── ROS parameter overlay ─────────────────────────────────────────────────

EXTRUDER_PARAMS = ("profile", "driver", "serial_port", "serial_baud")
PRINT_NODE_PARAMS = tuple(k for keys in _PRINT_NODE_KEYS.values() for k in keys)


def ros_overlay(cs: CellSettings) -> dict[str, Any]:
    """The settings as a ROS 2 parameter file (what ur-printer loads)."""
    pn: dict[str, Any] = {}
    for group, keys in _PRINT_NODE_KEYS.items():
        g = getattr(cs, group)
        for k in keys:
            pn[k] = getattr(g, k)
    return {
        "print_node": {"ros__parameters": pn},
        "extruder_controller": {"ros__parameters": {
            "profile": cs.extruder.profile,
            "driver": cs.extruder.driver,
            "serial_port": cs.extruder.serial_port,
            "serial_baud": cs.extruder.serial_baud,
        }},
    }


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-6)
    return a == b


def restart_diff(overlay: dict[str, Any], effective: dict[str, Optional[dict[str, Any]]]) -> Optional[list[str]]:
    """Parameters whose running value differs from the overlay, as
    ``node.param``. None when a node could not be read (unknown)."""
    out: list[str] = []
    for node, block in overlay.items():
        live = effective.get(node)
        if live is None:
            return None
        for k, v in block["ros__parameters"].items():
            if k not in live or not _same(v, live[k]):
                out.append(f"{node}.{k}")
    return out


# ── store ─────────────────────────────────────────────────────────────────


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _changed_keys(before: dict[str, Any], after: dict[str, Any], prefix: str = "") -> list[str]:
    keys: list[str] = []
    for k in sorted(set(before) | set(after)):
        a, b = before.get(k), after.get(k)
        if isinstance(a, dict) and isinstance(b, dict):
            keys += _changed_keys(a, b, f"{prefix}{k}.")
        elif not _same(a, b):
            keys.append(f"{prefix}{k}")
    return keys


class CellSettingsStore:
    def __init__(self, path: str, defaults: CellSettings, overlay_path: str,
                 profiles_dir: Optional[str] = None):
        self.path = path
        self.overlay_path = overlay_path
        self.profiles_dir = profiles_dir
        self.defaults = defaults
        self._lock = threading.Lock()
        self._settings: CellSettings = defaults
        self._history: list[dict[str, Any]] = []
        self.updated_at: Optional[float] = None
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._load()

    # ── reads ────────────────────────────────────────────────────────────
    def get(self) -> CellSettings:
        with self._lock:
            return self._settings

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history[-limit:])[::-1]

    def extruder_profiles(self) -> list[dict[str, str]]:
        """The profiles shipped in the ROS package (id, name, kind)."""
        if not self.profiles_dir or not os.path.isdir(self.profiles_dir):
            return []
        out = []
        for p in sorted(glob.glob(os.path.join(self.profiles_dir, "*.yaml"))):
            pid = os.path.splitext(os.path.basename(p))[0]
            try:
                with open(p) as f:
                    d = (yaml.safe_load(f) or {}).get("extruder", {})
            except (OSError, yaml.YAMLError):
                d = {}
            out.append({"id": pid, "name": str(d.get("name", pid)), "kind": str(d.get("kind", ""))})
        return out

    # ── writes ───────────────────────────────────────────────────────────
    def update(self, patch: dict[str, Any], source: str = "web") -> CellSettings:
        """Apply a partial document. Raises ValidationError / ValueError."""
        with self._lock:
            before = self._settings.model_dump()
            merged = _deep_merge(before, patch)
            merged["version"] = VERSION
            new = CellSettings.model_validate(merged)
            self._check_profile(new)
            changed = _changed_keys(before, new.model_dump())
            if changed:
                self._commit_locked(new, source, changed)
            return self._settings

    def reset(self, group: Optional[str] = None, source: str = "web") -> CellSettings:
        with self._lock:
            before = self._settings.model_dump()
            if group is None:
                new = self.defaults.model_copy(deep=True)
            else:
                if group not in ("extruder", "bed", "robot", "motion"):
                    raise ValueError(f"unknown settings group {group!r}")
                data = dict(before)
                data[group] = getattr(self.defaults, group).model_dump()
                new = CellSettings.model_validate(data)
            changed = _changed_keys(before, new.model_dump())
            if changed:
                self._commit_locked(new, source, changed)
            return self._settings

    # ── internals ────────────────────────────────────────────────────────
    def _check_profile(self, cs: CellSettings) -> None:
        ids = [p["id"] for p in self.extruder_profiles()]
        if ids and cs.extruder.profile not in ids:
            raise ValueError(f"unknown extruder profile {cs.extruder.profile!r}; available: {ids}")

    def _commit_locked(self, new: CellSettings, source: str, changed: list[str]) -> None:
        self._settings = new
        self.updated_at = time.time()
        self._history.append({"at": self.updated_at, "source": source, "changed": changed})
        del self._history[:-HISTORY_MAX]
        self._save_locked()
        logger.info("cell settings updated by %s: %s", source, ", ".join(changed))

    def _save_locked(self) -> None:
        doc = {"version": VERSION, "updated_at": self.updated_at,
               "settings": self._settings.model_dump(), "history": self._history}
        self._write_yaml(self.path, doc)
        self._write_yaml(self.overlay_path, ros_overlay(self._settings), header=(
            "# Generated by the web UI from settings.yaml — do not edit.\n"
            "# Loaded by ur-printer after print_params.yaml on its next launch.\n"))

    @staticmethod
    def _write_yaml(path: str, doc: dict[str, Any], header: str = "") -> None:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(header)
            yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=None)
        os.replace(tmp, path)

    def _load(self) -> None:
        if not os.path.isfile(self.path):
            # First run: materialise the defaults so ur-printer and the UI
            # see the same values from the start.
            self._save_locked()
            return
        try:
            with open(self.path) as f:
                doc = yaml.safe_load(f) or {}
            self._settings = CellSettings.model_validate(doc.get("settings") or {})
            self._history = list(doc.get("history") or [])[-HISTORY_MAX:]
            self.updated_at = doc.get("updated_at")
        except (OSError, yaml.YAMLError, ValidationError) as e:
            bad = self.path + ".invalid"
            logger.error("settings file unreadable (%s); moved to %s, using defaults", e, bad)
            try:
                os.replace(self.path, bad)
            except OSError:
                pass
            self._settings = self.defaults
            self._history = []
            self._save_locked()
            return
        if not os.path.isfile(self.overlay_path):
            self._save_locked()
