"""Print and extruder commands reach the bridge that exists at request time."""

import pytest

from backend.tests.conftest import _Msg


@pytest.mark.parametrize(
    "path,body,client_name",
    [
        ("/api/print/start", {"gcode_filepath": "/uploads/x.gcode"}, "start_print"),
        ("/api/print/pause", None, "pause_print"),
        ("/api/print/resume", None, "resume_print"),
        ("/api/print/cancel", {"retract_and_home": False}, "cancel_print"),
        ("/api/calibrate", {"use_current_pose": True}, "calibrate"),
        ("/api/extruder", {"enable": True, "rate": 1.5}, "extruder"),
    ],
)
def test_command_calls_matching_service(client, bridge, path, body, client_name):
    bridge.response = _Msg(
        success=True, message="ok", num_layers=3, estimated_time=12.0,
        print_frame=[0.0] * 6,
    )
    res = client.post(path, json=body)
    assert res.status_code == 200, res.text
    assert res.json()["success"] is True
    assert [c[0] for c in bridge.calls] == [client_name]


def test_start_forwards_request_fields(client, bridge):
    bridge.response = _Msg(success=True, message="", num_layers=1, estimated_time=1.0)
    client.post("/api/print/start", json={"gcode_filepath": "/u/a.gcode", "validate_only": True})
    _, req = bridge.calls[0]
    assert req.gcode_filepath == "/u/a.gcode"
    assert req.validate_only is True


def test_cancel_forwards_retract_flag(client, bridge):
    bridge.response = _Msg(success=True, message="")
    client.post("/api/print/cancel", json={"retract_and_home": False})
    assert bridge.calls[0][1].retract_and_home is False


def test_extruder_forwards_fields(client, bridge):
    bridge.response = _Msg(success=True, message="")
    client.post("/api/extruder", json={"enable": False, "rate": 0.0, "retract": True})
    req = bridge.calls[0][1]
    assert (req.enable, req.retract, req.prime) == (False, True, False)


def test_command_without_bridge_is_503(client, no_bridge):
    res = client.post("/api/print/pause")
    assert res.status_code == 503


def test_command_with_stopped_bridge_is_503(client, bridge):
    bridge.running = False
    assert client.post("/api/print/pause").status_code == 503


def test_command_without_client_is_503(client, bridge):
    bridge.pause_print_client = None
    res = client.post("/api/print/pause")
    assert res.status_code == 503
    assert "PausePrint" in res.json()["detail"]


def test_command_timeout_is_504(client, bridge):
    bridge.response = None
    assert client.post("/api/print/pause").status_code == 504


def test_service_failure_is_reported_not_raised(client, bridge):
    bridge.response = _Msg(success=False, message="not printing")
    body = client.post("/api/print/pause").json()
    assert body == {"success": False, "message": "not printing", "data": None}
