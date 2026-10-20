"""Job history: store transitions and the HTTP surface."""

import time

import pytest

from backend import deps
from backend.jobs import (
    ACTIVE_STATES, COMPLETED, ERROR, IDLE, PAUSED, CANCELLING, JobStore,
)
from backend.tests.conftest import _Msg

PRINTING = 5
LOADING = 1


@pytest.fixture
def store(tmp_path):
    s = JobStore(str(tmp_path / "jobs.sqlite"))
    yield s
    s.close()


@pytest.fixture
def jobs_api(store, monkeypatch):
    monkeypatch.setattr(deps, "jobs", store)
    return store


# ── store ──────────────────────────────────────────────────────────────────


def test_web_start_then_completed(store):
    job = store.start({"filename": "cube.stl", "material": "pla", "num_layers": 20})
    assert job["status"] == "running" and job["source"] == "web"
    store.on_print_state(LOADING)
    store.on_print_state(PRINTING)
    store.on_progress(12, 300.0)
    store.on_print_state(COMPLETED)
    store.on_print_state(IDLE)
    done = store.get(job["id"])
    assert done["status"] == "completed"
    assert done["layers_done"] == 12 and done["elapsed_time"] == 300.0
    assert done["finished_at"] >= done["started_at"]
    assert store.current() is None


def test_error_records_message(store):
    store.start({"filename": "a.stl"})
    store.on_print_state(PRINTING)
    store.on_print_state(ERROR, "nozzle jam")
    row = store.list()[0]
    assert row["status"] == "error" and row["error_message"] == "nozzle jam"


def test_cancel_closes_as_cancelled_on_return_to_idle(store):
    store.start({"filename": "a.stl"})
    store.on_print_state(PRINTING)
    store.on_print_state(CANCELLING)
    assert store.current()["status"] == "running"
    store.on_print_state(IDLE)
    assert store.list()[0]["status"] == "cancelled"


def test_external_print_is_recorded(store):
    """A print started from the CLI still shows up in the history."""
    store.on_print_state(LOADING)
    cur = store.current()
    assert cur is not None and cur["source"] == "external"
    store.on_print_state(PRINTING)
    store.on_print_state(COMPLETED)
    assert store.list()[0]["status"] == "completed"


def test_web_start_adopts_the_external_row_the_bridge_opened_first(store):
    # The bridge sees LOADING before the start endpoint returns.
    store.on_print_state(LOADING)
    first = store.current()
    job = store.start({"filename": "cube.stl", "num_layers": 7})
    assert job["id"] == first["id"]
    assert job["source"] == "web" and job["filename"] == "cube.stl" and job["num_layers"] == 7
    assert len(store.list()) == 1


def test_stale_external_row_is_not_adopted(store, monkeypatch):
    store.on_print_state(LOADING)
    old = store.current()
    monkeypatch.setattr(time, "time", lambda: old["started_at"] + 120)
    job = store.start({"filename": "new.stl"})
    assert job["id"] != old["id"]
    rows = {r["id"]: r for r in store.list()}
    assert rows[old["id"]]["status"] == "cancelled"
    assert rows[job["id"]]["status"] == "running"


def test_resume_from_paused_does_not_open_a_job(store):
    store.on_print_state(PAUSED)  # paused is not a start when nothing runs
    assert store.current() is None
    assert ACTIVE_STATES  # sanity: constant exported


def test_running_row_is_closed_as_error_on_restart(tmp_path):
    path = str(tmp_path / "jobs.sqlite")
    s = JobStore(path)
    s.start({"filename": "a.stl"})
    s.close()
    s2 = JobStore(path)
    row = s2.list()[0]
    assert row["status"] == "error"
    assert "restarted" in row["error_message"]
    s2.close()


def test_delete_refuses_running_job(store):
    job = store.start({"filename": "a.stl"})
    assert store.delete(job["id"]) is False
    store.on_print_state(PRINTING)
    store.on_print_state(COMPLETED)
    assert store.delete(job["id"]) is True
    assert store.list() == []


def test_clear_finished_keeps_running(store):
    a = store.start({"filename": "a"})
    store.on_print_state(PRINTING); store.on_print_state(COMPLETED)
    b = store.start({"filename": "b"})
    assert store.clear_finished() == 1
    ids = [r["id"] for r in store.list()]
    assert ids == [b["id"]] and a["id"] not in ids


# ── HTTP ───────────────────────────────────────────────────────────────────


def test_list_endpoint(client, jobs_api):
    jobs_api.start({"filename": "x.stl"})
    body = client.get("/api/jobs").json()
    assert body["current"]["filename"] == "x.stl"
    assert len(body["jobs"]) == 1


def test_delete_endpoints(client, jobs_api):
    job = jobs_api.start({"filename": "x.stl"})
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 409
    jobs_api.on_print_state(PRINTING); jobs_api.on_print_state(COMPLETED)
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 200
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 404
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_jobs_unavailable_is_503(client, monkeypatch):
    monkeypatch.setattr(deps, "jobs", None)
    assert client.get("/api/jobs").status_code == 503


def test_print_start_opens_a_job_with_meta(client, bridge, jobs_api):
    bridge.response = _Msg(success=True, message="", num_layers=9, estimated_time=42.0)
    res = client.post("/api/print/start", json={
        "gcode_filepath": "/data/uploads/a.gcode",
        "meta": {"filename": "a.stl", "material": "pla", "layer_height": 0.2, "ignored": 1},
    })
    assert res.status_code == 200, res.text
    cur = jobs_api.current()
    assert cur["filename"] == "a.stl" and cur["num_layers"] == 9
    assert cur["gcode_path"] == "/data/uploads/a.gcode"


def test_validate_only_start_opens_no_job(client, bridge, jobs_api):
    bridge.response = _Msg(success=True, message="", num_layers=9, estimated_time=1.0)
    client.post("/api/print/start", json={"gcode_filepath": "/x.gcode", "validate_only": True})
    assert jobs_api.current() is None


def test_failed_start_opens_no_job(client, bridge, jobs_api):
    bridge.response = _Msg(success=False, message="bad gcode", num_layers=0, estimated_time=0.0)
    client.post("/api/print/start", json={"gcode_filepath": "/x.gcode"})
    assert jobs_api.current() is None


def test_failed_start_annotates_the_attempt_the_bridge_recorded(client, bridge, jobs_api):
    # print_node left IDLE, failed validation and went to ERROR before the
    # service answered: the bridge opened and closed an external row.
    jobs_api.on_print_state(LOADING)
    jobs_api.on_print_state(ERROR, "Required services not available")
    bridge.response = _Msg(success=False, message="Required services not available",
                           num_layers=0, estimated_time=0.0)
    client.post("/api/print/start", json={"gcode_filepath": "/data/uploads/c.gcode",
                                          "meta": {"filename": "cube20.stl", "material": "pla"}})
    rows = jobs_api.list()
    assert len(rows) == 1
    assert rows[0]["status"] == "error" and rows[0]["source"] == "web"
    assert rows[0]["filename"] == "cube20.stl" and rows[0]["gcode_path"] == "/data/uploads/c.gcode"


def test_failed_start_with_nothing_recorded_opens_no_job(client, bridge, jobs_api):
    bridge.response = _Msg(success=False, message="bad gcode", num_layers=0, estimated_time=0.0)
    client.post("/api/print/start", json={"gcode_filepath": "/x.gcode", "meta": {"filename": "a"}})
    assert jobs_api.list() == []
