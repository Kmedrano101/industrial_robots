"""Cell settings: defaults, validation, persistence, ROS overlay, restart
detection and the HTTP surface."""

import math
import os

import pytest
import yaml

from backend import deps
from backend.cell_settings import (
    BED_REFERENCE_POSES, CellSettings, CellSettingsStore, default_settings, restart_diff,
    ros_overlay,
)
from backend.tests.conftest import ROS_PKG_DIR, _Msg

PRINT_PARAMS = os.path.join(ROS_PKG_DIR, "config", "print_params.yaml")


# ── defaults ───────────────────────────────────────────────────────────────


def test_defaults_come_from_print_params_and_env():
    cs = default_settings(PRINT_PARAMS, ur_type="ur7e", extruder_profile="generic_fdm",
                          extruder_driver="gcode_serial", extruder_serial_port="/dev/ttyACM0")
    assert cs.bed.print_origin_xyz == [-0.3, 0.0, -0.01]
    assert cs.motion.max_print_velocity == 0.05
    assert cs.robot.tool_offset_xyz[2] == 0.105
    assert cs.robot.home_joints == BED_REFERENCE_POSES["center"]
    assert set(cs.robot.bed_points) == {"p1", "p2", "p3", "p4", "center"}
    assert cs.extruder.profile == "generic_fdm" and cs.extruder.driver == "gcode_serial"


def test_defaults_without_print_params_still_valid(tmp_path):
    cs = default_settings(str(tmp_path / "missing.yaml"), ur_type="ur5e")
    assert cs.robot.home_joints[1] == pytest.approx(-math.pi / 2)
    assert cs.robot.bed_points == {}
    CellSettings.model_validate(cs.model_dump())


# ── validation ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("patch, needle", [
    ({"motion": {"max_print_velocity": 2.0}}, "max_print_velocity"),
    ({"bed": {"z_hop_height": -1}}, "z_hop_height"),
    ({"bed": {"print_origin_xyz": [0, 0]}}, "needs 3 values"),
    ({"robot": {"home_joints": [0, 0, 0, 0, 0, 99]}}, "±2π"),
    ({"robot": {"bed_points": {"p9": [0] * 6}}}, "bed point must be"),
    ({"robot": {"tool_offset_xyz": [0, 0, 1.5]}}, "tool offset"),
    ({"extruder": {"driver": "canbus"}}, "driver"),
    ({"extruder": {"serial_port": "ttyACM0"}}, "serial_port"),
    ({"extruder": {"serial_baud": 1234}}, "serial_baud"),
])
def test_invalid_patches_are_rejected(cell, patch, needle):
    before = cell.get().model_dump()
    with pytest.raises(Exception) as e:
        cell.update(patch)
    assert needle in str(e.value)
    assert cell.get().model_dump() == before, "rejected patch must not leak"


def test_unknown_extruder_profile_is_rejected(cell):
    with pytest.raises(ValueError, match="unknown extruder profile"):
        cell.update({"extruder": {"profile": "nope"}})
    cell.update({"extruder": {"profile": "generic_fdm"}})
    assert cell.get().extruder.profile == "generic_fdm"


def test_profiles_listed_from_the_package(cell):
    ids = [p["id"] for p in cell.extruder_profiles()]
    assert "mahor_v5_m12_pro" in ids and "paste_syringe" in ids
    mahor = next(p for p in cell.extruder_profiles() if p["id"] == "mahor_v5_m12_pro")
    assert mahor["name"] == "Mahor V5 M12 PRO" and mahor["kind"] == "pellet_screw"


# ── persistence ────────────────────────────────────────────────────────────


def test_update_persists_merges_and_records_history(cell, tmp_path):
    cell.update({"motion": {"max_print_velocity": 0.08}, "bed": {"z_hop_height": 0.01}}, source="test")
    cs = cell.get()
    assert cs.motion.max_print_velocity == 0.08 and cs.motion.max_travel_velocity == 0.15
    again = CellSettingsStore(str(tmp_path / "settings.yaml"), defaults=cell.defaults,
                              overlay_path=str(tmp_path / "ros_params.yaml"))
    assert again.get().bed.z_hop_height == 0.01
    h = again.history()
    assert h[0]["source"] == "test"
    assert sorted(h[0]["changed"]) == ["bed.z_hop_height", "motion.max_print_velocity"]


def test_noop_update_writes_no_history(cell):
    cell.update({"motion": {"max_print_velocity": cell.get().motion.max_print_velocity}})
    assert cell.history() == []


def test_reset_group_and_all(cell):
    cell.update({"motion": {"max_acceleration": 1.0}, "bed": {"z_hop_enabled": False}})
    cell.reset("motion")
    assert cell.get().motion.max_acceleration == cell.defaults.motion.max_acceleration
    assert cell.get().bed.z_hop_enabled is False
    cell.reset()
    assert cell.get().model_dump() == cell.defaults.model_dump()
    with pytest.raises(ValueError):
        cell.reset("nope")


def test_corrupt_file_is_set_aside(tmp_path):
    path = tmp_path / "settings.yaml"
    path.write_text("settings: {motion: {max_print_velocity: 'fast'}}\n")
    store = CellSettingsStore(str(path), defaults=default_settings(), overlay_path=str(tmp_path / "o.yaml"))
    assert store.get().motion.max_print_velocity == 0.05
    assert (tmp_path / "settings.yaml.invalid").exists()
    assert yaml.safe_load(path.read_text())["settings"]["motion"]["max_print_velocity"] == 0.05


# ── ROS overlay ────────────────────────────────────────────────────────────


def test_overlay_is_a_ros_parameter_file(cell, tmp_path):
    cell.update({"motion": {"max_print_velocity": 0.07}, "extruder": {"driver": "gcode_serial",
                                                                      "serial_port": "/dev/ttyUSB0"}})
    doc = yaml.safe_load((tmp_path / "ros_params.yaml").read_text())
    pn = doc["print_node"]["ros__parameters"]
    assert pn["max_print_velocity"] == 0.07 and pn["home_joints"] == cell.get().robot.home_joints
    assert pn["z_hop_enabled"] is True
    ex = doc["extruder_controller"]["ros__parameters"]
    assert ex == {"profile": "mahor_v5_m12_pro", "driver": "gcode_serial",
                  "serial_port": "/dev/ttyUSB0", "serial_baud": 0}
    assert "size_mm" not in pn, "UI-only keys stay out of the overlay"


def test_restart_diff():
    cs = CellSettings()
    ov = ros_overlay(cs)
    live = {n: dict(b["ros__parameters"]) for n, b in ov.items()}
    assert restart_diff(ov, live) == []
    live["print_node"]["max_print_velocity"] += 1e-9
    assert restart_diff(ov, live) == [], "float noise is not a change"
    live["print_node"]["z_hop_height"] = 0.02
    live["extruder_controller"]["driver"] = "gcode_serial"
    assert restart_diff(ov, live) == ["print_node.z_hop_height", "extruder_controller.driver"]
    assert restart_diff(ov, {"print_node": live["print_node"], "extruder_controller": None}) is None


# ── HTTP ───────────────────────────────────────────────────────────────────


def test_get_without_bridge_reports_unknown_restart(client, cell, no_bridge):
    body = client.get("/api/settings").json()
    assert body["settings"]["motion"]["max_print_velocity"] == 0.05
    assert body["restart_required"] is None and body["effective"]["print_node"] is None
    assert any(p["id"] == "mahor_v5_m12_pro" for p in body["extruder_profiles"])


def test_put_then_restart_required_until_nodes_match(client, cell, bridge):
    ov = ros_overlay(cell.get())
    bridge.parameters = {n: dict(b["ros__parameters"]) for n, b in ov.items()}
    assert client.get("/api/settings").json()["restart_required"] is False
    res = client.put("/api/settings", json={"patch": {"motion": {"max_travel_velocity": 0.2}}})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["restart_required"] is True and body["pending"] == ["print_node.max_travel_velocity"]
    bridge.parameters["print_node"]["max_travel_velocity"] = 0.2
    assert client.get("/api/settings").json()["restart_required"] is False


def test_put_invalid_is_422_with_location(client, cell, bridge):
    res = client.put("/api/settings", json={"patch": {"motion": {"max_acceleration": 50}}})
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == "motion.max_acceleration"
    res = client.put("/api/settings", json={"patch": {"extruder": {"profile": "nope"}}})
    assert res.status_code == 422 and "unknown extruder profile" in res.json()["detail"]


def test_reset_endpoint(client, cell, bridge):
    client.put("/api/settings", json={"patch": {"bed": {"z_hop_height": 0.02}}})
    body = client.post("/api/settings/reset", json={"group": "bed"}).json()
    assert body["settings"]["bed"]["z_hop_height"] == cell.defaults.bed.z_hop_height


def test_capture_bed_point_and_home_from_live_joints(client, cell, bridge):
    bridge.latest_state["joint_states"] = {"positions": [0.1, -1.2, 1.3, -1.4, -1.5, 0.6]}
    body = client.post("/api/settings/capture", json={"target": "robot.bed_points.p2"}).json()
    assert body["settings"]["robot"]["bed_points"]["p2"] == [0.1, -1.2, 1.3, -1.4, -1.5, 0.6]
    assert body["settings"]["robot"]["bed_points"]["p1"] == BED_REFERENCE_POSES["p1"], "others kept"
    client.post("/api/settings/capture", json={"target": "robot.home_joints"})
    assert cell.get().robot.home_joints == [0.1, -1.2, 1.3, -1.4, -1.5, 0.6]
    assert client.post("/api/settings/capture", json={"target": "robot.bed_points.p7"}).status_code == 422
    assert client.post("/api/settings/capture", json={"target": "bed.origin"}).status_code == 422


def test_capture_needs_fresh_joint_states(client, cell, bridge, monkeypatch):
    monkeypatch.setattr(bridge, "joint_states_age", lambda: 30.0)
    assert client.post("/api/settings/capture", json={"target": "robot.home_joints"}).status_code == 409


def test_restart_request_writes_the_flag_file(client, cell, tmp_path):
    body = client.post("/api/settings/restart").json()
    assert body["success"] and (tmp_path / "restart.request").exists()
    assert client.get("/api/settings").json()["restart_requested_at"] == pytest.approx(body["requested_at"])


def test_robot_endpoints_follow_the_settings(client, cell, bridge, test_panel, monkeypatch):
    monkeypatch.setattr(deps.cell_settings, "_settings", cell.get())
    cell.update({"robot": {"home_joints": [0.5, -1.0, 1.0, -1.0, -1.0, 0.0],
                           "bed_points": {"p1": [1, 1, 1, 1, 1, 1]}}})
    assert client.get("/api/robot/home_pose").json()["rad"] == [0.5, -1.0, 1.0, -1.0, -1.0, 0.0]
    client.post("/api/robot/move_to_home")
    assert bridge.published[-1][0] == [0.5, -1.0, 1.0, -1.0, -1.0, 0.0]
    pts = client.get("/api/robot/bed_points").json()["points"]
    assert pts["p1"]["rad"] == [1.0] * 6
    assert client.post("/api/robot/goto_bed_point", json={"point": "p1"}).status_code == 200


def test_calibrate_persists_the_origin(client, cell, bridge):
    frame = [1, 0, 0, -0.31, 0, 1, 0, 0.02, 0, 0, 1, -0.012, 0, 0, 0, 1]
    bridge.response = _Msg(success=True, message="Origin calibrated", print_frame=frame)
    res = client.post("/api/calibrate", json={"use_current_pose": True})
    assert res.status_code == 200, res.text
    assert cell.get().bed.print_origin_xyz == [-0.31, 0.02, -0.012]
    assert cell.history()[0]["source"] == "calibrate"
