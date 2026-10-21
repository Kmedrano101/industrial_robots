"""Shared fixtures.

The suite runs without ROS: the bridge is replaced by a fake that records
service calls, and the ROS interface modules the routes import inside
their handlers (``ur_3d_printer.srv``, ``std_srvs.srv``, ...) are stubbed
when the real ones are not importable. This keeps the tests runnable on a
developer machine and in CI, and makes them about the HTTP layer rather
than about DDS.
"""

from __future__ import annotations

import os
import sys
import types
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend import ros_bridge as rb_module
from backend.config import settings
from backend.ros_bridge import RosBridge

# Import the slicer first: it puts the real `ur_3d_printer` source package
# on sys.path. Only the *generated* interface modules (`.srv`, `.msg`) are
# missing outside the container, and those are what gets stubbed below.
import backend.slicer_service  # noqa: E402,F401


# ── ROS interface stubs ────────────────────────────────────────────────────


class _Msg:
    """Attribute bag standing in for a generated ROS message/request."""

    def __init__(self, **kw: Any):
        self.__dict__.update(kw)


def _service(**response_defaults: Any):
    """Build a stand-in for a generated service type: ``Svc.Request()`` and
    ``Svc.Response(**fields)`` with the given defaults."""

    class Svc:
        class Request(_Msg):
            pass

        class Response(_Msg):
            def __init__(self, **kw: Any):
                super().__init__(**{**response_defaults, **kw})

    return Svc


def _install_stub(name: str, **attrs: Any) -> None:
    """Register a stub module unless a real one providing `attrs` exists.

    Note the source tree's `ur_3d_printer/srv/` directory (the .srv text
    files) imports as an *empty* namespace package, so "importable" alone
    is not enough — the generated classes have to actually be there."""
    try:
        mod = sys.modules.get(name) or __import__(name, fromlist=["_"])
        if all(hasattr(mod, a) for a in attrs):
            return
    except ImportError:
        pass
    parent, _, child = name.rpartition(".")
    if parent:
        _install_stub(parent)
    mod = types.ModuleType(name)
    mod.__path__ = []  # behave as a package so submodules can hang off it
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    if parent:
        setattr(sys.modules[parent], child, mod)


_install_stub(
    "ur_3d_printer.srv",
    StartPrint=_service(success=True, message="", num_layers=0, estimated_time=0.0),
    PausePrint=_service(success=True, message=""),
    ResumePrint=_service(success=True, message=""),
    CancelPrint=_service(success=True, message=""),
    CalibrateOrigin=_service(success=True, message="", print_frame=[0.0] * 6),
    SetExtruder=_service(success=True, message=""),
)
_install_stub("std_srvs.srv", Trigger=_service(success=True, message=""))
_install_stub("geometry_msgs.msg", Point=_Msg, Vector3=_Msg)


# ── Fake bridge ────────────────────────────────────────────────────────────


class FakeClient:
    def __init__(self, name: str, ready: bool = True):
        self.name = name
        self._ready = ready

    def service_is_ready(self) -> bool:
        return self._ready

    def wait_for_service(self, timeout_sec: float = 0.0) -> bool:
        return self._ready


class FakeBridge:
    """Stands in for RosBridge: same attributes the routes touch, plus a
    log of every service call and a programmable response."""

    joint_names = list(RosBridge(ws_broadcast_fn=None).joint_names)

    def __init__(self) -> None:
        self.running = True
        self.latest_state = RosBridge(ws_broadcast_fn=None).latest_state
        self.calls: list[tuple[str, Any]] = []
        self.published: list[tuple[list[float], float]] = []
        self.response: Any = None  # None → the call times out
        # {node_name: {param: value}}; a missing node → None (unreachable)
        self.parameters: dict[str, dict[str, Any]] = {}
        self.set_parameters_result: tuple[bool, str] = (True, "")
        self.switch_result = (True, "motion control enabled")
        for name in (
            "start_print", "pause_print", "resume_print", "cancel_print",
            "calibrate", "extruder", "power_on", "power_off",
            "brake_release", "play", "stop",
        ):
            setattr(self, f"{name}_client", FakeClient(name))

    async def call_service(self, client, request, timeout: float = 5.0):
        self.calls.append((client.name, request))
        return self.response

    def publish_joint_trajectory(self, positions, duration_s: float) -> bool:
        if len(positions) != 6:
            raise ValueError("expected 6 joints")
        self.published.append((list(positions), duration_s))
        return True

    async def switch_motion_control(self, enable: bool, timeout: float = 6.0):
        self.calls.append(("switch_motion_control", enable))
        return self.switch_result

    def joint_states_age(self):
        return 0.0

    async def set_parameters(self, node_name, values, timeout=3.0):
        self.calls.append(("set_parameters", (node_name, dict(values))))
        if self.set_parameters_result[0] and node_name in self.parameters:
            self.parameters[node_name].update(values)
        return self.set_parameters_result

    async def get_parameters(self, node_name, names, timeout=2.0):
        live = self.parameters.get(node_name)
        if live is None:
            return None
        return {n: live.get(n) for n in names}


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def bridge(monkeypatch):
    fake = FakeBridge()
    monkeypatch.setattr(rb_module, "ros_bridge", fake)
    return fake


@pytest.fixture
def no_bridge(monkeypatch):
    monkeypatch.setattr(rb_module, "ros_bridge", None)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def test_panel(monkeypatch):
    monkeypatch.setattr(settings, "enable_test_panel", True)


@pytest.fixture
def client():
    # No `with`: the lifespan (which would start a real RosBridge) must not
    # run. The bridge is injected by the fixtures above instead.
    from backend.main import app

    return TestClient(app)


# tests/ → backend/ → ur_3d_printer_web/ → workspace/ → the ROS package
ROS_PKG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))), "ur_3d_printer")


@pytest.fixture
def cell(tmp_path, monkeypatch):
    """A CellSettingsStore in a temp dir with the repo's factory defaults."""
    from backend import deps
    from backend.cell_settings import CellSettingsStore, default_settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ros_pkg_dir", ROS_PKG_DIR)
    store = CellSettingsStore(
        str(tmp_path / "settings.yaml"),
        defaults=default_settings(os.path.join(ROS_PKG_DIR, "config", "print_params.yaml"),
                                  ur_type="ur7e"),
        overlay_path=str(tmp_path / "ros_params.yaml"),
        profiles_dir=os.path.join(ROS_PKG_DIR, "config", "extruders"),
    )
    monkeypatch.setattr(deps, "cell_settings", store)
    return store
