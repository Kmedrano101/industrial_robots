"""Robot commissioning endpoints: gating and the server-side motion caps."""

import math

import pytest

from backend.config import settings
from backend.tests.conftest import _Msg


def test_status_without_bridge_is_blank(client, no_bridge):
    body = client.get("/api/robot/status").json()
    assert body["ros2_connected"] is False
    assert body["motion_allowed"] is False
    assert len(body["joint_states"]["positions"]) == 6


def test_status_reflects_bridge_state(client, bridge, test_panel):
    bridge.latest_state["robot_mode"] = {"mode": 7, "mode_name": "RUNNING"}
    bridge.latest_state["safety_mode"] = {"mode": 1, "mode_name": "NORMAL"}
    bridge.latest_state["controllers"] = {
        "motion_control_enabled": True,
        "active_trajectory_controller": "scaled_joint_trajectory_controller",
        "list": [],
    }
    body = client.get("/api/robot/status").json()
    assert body["ros2_connected"] is True
    assert body["motion_allowed"] is True
    assert body["motion_control_enabled"] is True


def test_status_motion_not_allowed_outside_normal_safety(client, bridge, test_panel):
    bridge.latest_state["robot_mode"] = {"mode": 7, "mode_name": "RUNNING"}
    bridge.latest_state["safety_mode"] = {"mode": 3, "mode_name": "PROTECTIVE_STOP"}
    assert client.get("/api/robot/status").json()["motion_allowed"] is False


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/robot/power_on", None),
        ("/api/robot/jog", {"joint_index": 0, "delta_rad": 0.01}),
        ("/api/robot/move_to_home", None),
        ("/api/robot/motion_control", {"enable": True}),
        ("/api/robot/goto_bed_point", {"point": "center"}),
    ],
)
def test_write_endpoints_are_gated_by_test_panel(client, bridge, monkeypatch, path, body):
    monkeypatch.setattr(settings, "enable_test_panel", False)
    assert client.post(path, json=body).status_code == 403
    assert bridge.calls == [] and bridge.published == []


def test_stop_is_always_allowed(client, bridge, monkeypatch):
    """The browser E-stop must work even with the test panel off."""
    monkeypatch.setattr(settings, "enable_test_panel", False)
    bridge.response = _Msg(success=True, message="stopped")
    res = client.post("/api/robot/stop")
    assert res.status_code == 200
    assert bridge.calls[0][0] == "stop"


def test_jog_rejects_delta_over_cap(client, bridge, test_panel):
    res = client.post(
        "/api/robot/jog",
        json={"joint_index": 2, "delta_rad": settings.jog_max_delta_rad * 2},
    )
    assert res.status_code == 400
    assert bridge.published == []


def test_jog_lengthens_duration_to_respect_velocity_cap(client, bridge, test_panel):
    delta = settings.jog_max_delta_rad
    res = client.post(
        "/api/robot/jog",
        json={"joint_index": 1, "delta_rad": delta, "duration_s": 0.01},
    )
    assert res.status_code == 200, res.text
    positions, duration = bridge.published[0]
    assert duration >= settings.jog_min_duration_s
    assert abs(delta) / duration <= settings.jog_max_velocity_rad_s + 1e-9
    assert positions[1] == pytest.approx(delta)
    assert positions[0] == 0.0  # other joints untouched


def test_jog_is_relative_to_current_pose(client, bridge, test_panel):
    bridge.latest_state["joint_states"] = {"positions": [0.5, 0, 0, 0, 0, 0]}
    client.post("/api/robot/jog", json={"joint_index": 0, "delta_rad": 0.01})
    assert bridge.published[0][0][0] == pytest.approx(0.51)


def test_move_to_home_uses_configured_pose(client, bridge, test_panel, monkeypatch):
    monkeypatch.setattr(settings, "ur_type", "ur7e")
    home = client.get("/api/robot/home_pose").json()
    res = client.post("/api/robot/move_to_home")
    assert res.status_code == 200
    assert bridge.published[0][0] == pytest.approx(home["rad"])


def test_home_pose_deg_matches_rad(client):
    body = client.get("/api/robot/home_pose").json()
    for rad, deg in zip(body["rad"], body["deg"]):
        assert deg == pytest.approx(math.degrees(rad), abs=0.01)


def test_goto_unknown_bed_point_is_404(client, bridge, test_panel):
    assert client.post("/api/robot/goto_bed_point", json={"point": "p9"}).status_code == 404


def test_motion_control_plays_program_first_when_not_running(client, bridge, test_panel, monkeypatch):
    import asyncio

    # Skip the 2 s settle wait so the test stays fast.
    async def _no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    bridge.latest_state["program_running"] = False
    bridge.response = _Msg(success=True, message="")
    res = client.post("/api/robot/motion_control", json={"enable": True})
    assert res.status_code == 200, res.text
    assert [c[0] for c in bridge.calls] == ["play", "switch_motion_control"]


def test_motion_control_skips_play_when_running(client, bridge, test_panel):
    bridge.latest_state["program_running"] = True
    client.post("/api/robot/motion_control", json={"enable": True})
    assert [c[0] for c in bridge.calls] == ["switch_motion_control"]


def test_motion_control_reports_switch_failure(client, bridge, test_panel):
    bridge.latest_state["program_running"] = True
    bridge.switch_result = (False, "switch_controller timed out")
    res = client.post("/api/robot/motion_control", json={"enable": False})
    assert res.status_code == 503
