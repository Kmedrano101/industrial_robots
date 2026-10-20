"""/api/health and /api/state must reflect the bridge created at startup."""


def test_health_reports_connected_when_bridge_runs(client, bridge):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["ros2_connected"] is True


def test_health_reports_disconnected_without_bridge(client, no_bridge):
    assert client.get("/api/health").json()["ros2_connected"] is False


def test_health_reports_disconnected_when_bridge_not_running(client, bridge):
    bridge.running = False
    assert client.get("/api/health").json()["ros2_connected"] is False


def test_state_returns_live_snapshot(client, bridge):
    bridge.latest_state["robot_mode"] = {"mode": 7, "mode_name": "RUNNING"}
    body = client.get("/api/state").json()
    assert body["robot_mode"]["mode_name"] == "RUNNING"


def test_state_without_bridge_has_same_shape(client, bridge, no_bridge):
    body = client.get("/api/state").json()
    assert set(body) == set(bridge.latest_state)
