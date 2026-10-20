"""Material / process profiles: named sets of slicer settings.

Stored server-side as one JSON file in the data directory so every tablet
and browser in the cell sees the same list — the alternative, browser
localStorage, would give each device its own, which is exactly how two
operators end up printing the same part with different settings.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Optional

# Keys a profile may carry; anything else sent by a client is dropped.
PROFILE_FIELDS = (
    "slicer_mode", "material", "layer_height", "nozzle_diameter", "print_speed",
    "travel_speed", "scale", "max_tilt", "infill_pattern", "infill_density",
    "infill_angle_base", "infill_angle_increment",
)

_BUILTIN: list[dict[str, Any]] = [
    {
        "id": "pla-standard",
        "name": "PLA · 0.2 mm",
        "builtin": True,
        "settings": {
            "slicer_mode": "planar", "material": "pla", "layer_height": 0.2,
            "nozzle_diameter": 0.4, "print_speed": 3000, "travel_speed": 9000,
            "scale": 1.0, "max_tilt": 30.0, "infill_pattern": "linear",
            "infill_density": 0.2, "infill_angle_base": 45.0, "infill_angle_increment": 90.0,
        },
    },
    {
        "id": "clay-coarse",
        "name": "Arcilla · 1.0 mm",
        "builtin": True,
        "settings": {
            "slicer_mode": "planar", "material": "clay", "layer_height": 1.0,
            "nozzle_diameter": 2.0, "print_speed": 1500, "travel_speed": 6000,
            "scale": 1.0, "max_tilt": 30.0, "infill_pattern": "none",
            "infill_density": 0.2, "infill_angle_base": 45.0, "infill_angle_increment": 90.0,
        },
    },
]


def _slug(name: str) -> str:
    s = "".join(c.lower() if c.isalnum() else "-" for c in name.strip())
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "profile"


class ProfileStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path) as f:
                data = json.load(f)
            self._items = {p["id"]: p for p in data if "id" in p}
        except (FileNotFoundError, ValueError, KeyError):
            self._items = {}

    def _save_locked(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(list(self._items.values()), f, indent=1)
        os.replace(tmp, self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            user = sorted(self._items.values(), key=lambda p: p["name"].lower())
            return [*_BUILTIN, *user]

    def get(self, profile_id: str) -> Optional[dict[str, Any]]:
        for p in _BUILTIN:
            if p["id"] == profile_id:
                return p
        with self._lock:
            return self._items.get(profile_id)

    def upsert(self, name: str, settings: dict[str, Any], profile_id: Optional[str] = None) -> dict[str, Any]:
        clean = {k: settings[k] for k in PROFILE_FIELDS if k in settings}
        with self._lock:
            pid = profile_id or _slug(name)
            if any(b["id"] == pid for b in _BUILTIN):
                # Saving over a built-in makes a user copy instead.
                pid = f"{pid}-{int(time.time())}"
            item = {"id": pid, "name": name.strip(), "builtin": False,
                    "settings": clean, "updated_at": time.time()}
            self._items[pid] = item
            self._save_locked()
            return item

    def delete(self, profile_id: str) -> bool:
        with self._lock:
            if profile_id not in self._items:
                return False
            del self._items[profile_id]
            self._save_locked()
            return True
