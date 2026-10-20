"""RosBridge logic that does not need rclpy: service-call plumbing,
joint-state ordering/throttling and the WebSocket manager."""

import asyncio
import json
import threading

import pytest

from backend.ros_bridge import RosBridge
from backend.websocket_manager import WebSocketManager


# ── call_service ───────────────────────────────────────────────────────────


class FakeRosFuture:
    """Mimics rclpy.task.Future: callbacks run on whatever thread completes
    the future, or immediately if it is already done."""

    def __init__(self):
        self._result = None
        self._done = False
        self._callbacks = []

    def add_done_callback(self, cb):
        if self._done:
            cb(self)
        else:
            self._callbacks.append(cb)

    def set_result(self, value):
        self._result = value
        self._done = True
        for cb in self._callbacks:
            cb(self)

    def result(self):
        return self._result


class FakeRclpyClient:
    def __init__(self):
        self.future = FakeRosFuture()
        self.removed = []

    def call_async(self, request):
        return self.future

    def remove_pending_request(self, future):
        self.removed.append(future)


@pytest.mark.asyncio
async def test_call_service_resolves_from_executor_thread():
    bridge = RosBridge(ws_broadcast_fn=None)
    client = FakeRclpyClient()

    # Complete the rclpy future from another thread, as the executor would.
    threading.Timer(0.05, client.future.set_result, args=("done",)).start()
    result = await bridge.call_service(client, object(), timeout=1.0)
    assert result == "done"


@pytest.mark.asyncio
async def test_call_service_resolves_when_already_done():
    bridge = RosBridge(ws_broadcast_fn=None)
    client = FakeRclpyClient()
    client.future.set_result("early")
    assert await bridge.call_service(client, object(), timeout=1.0) == "early"


@pytest.mark.asyncio
async def test_call_service_times_out_and_cancels_pending_request():
    bridge = RosBridge(ws_broadcast_fn=None)
    client = FakeRclpyClient()
    result = await bridge.call_service(client, object(), timeout=0.05)
    assert result is None
    assert client.removed == [client.future]


@pytest.mark.asyncio
async def test_call_service_without_client_returns_none():
    bridge = RosBridge(ws_broadcast_fn=None)
    assert await bridge.call_service(None, object()) is None


# ── joint states ───────────────────────────────────────────────────────────


class JointMsg:
    def __init__(self, name, position):
        self.name = name
        self.position = position


def test_joint_states_are_reordered_by_name():
    bridge = RosBridge(ws_broadcast_fn=None, joint_state_hz=1000)
    sent = []
    bridge._broadcast_async = lambda topic, data: sent.append((topic, data))
    # UR driver order: shoulder_pan LAST.
    bridge._on_joint_states(JointMsg(
        ["shoulder_lift_joint", "elbow_joint", "wrist_1_joint",
         "wrist_2_joint", "wrist_3_joint", "shoulder_pan_joint"],
        [1.0, 2.0, 3.0, 4.0, 5.0, 0.5],
    ))
    assert sent[0][1]["positions"] == [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
    assert bridge.latest_state["joint_states"]["positions"][0] == 0.5


def test_joint_states_are_throttled_but_timestamp_is_not():
    bridge = RosBridge(ws_broadcast_fn=None, joint_state_hz=1)  # 1 s window
    sent = []
    bridge._broadcast_async = lambda topic, data: sent.append(topic)
    msg = JointMsg(bridge.joint_names, [0.0] * 6)
    bridge._on_joint_states(msg)
    bridge._on_joint_states(msg)
    bridge._on_joint_states(msg)
    assert sent == ["joint_states"]
    assert bridge.joint_states_age() is not None and bridge.joint_states_age() < 0.5


def test_bridge_not_running_without_rclpy_start():
    bridge = RosBridge(ws_broadcast_fn=None)
    assert bridge.running is False


# ── WebSocket manager ──────────────────────────────────────────────────────


class FakeWs:
    def __init__(self, fail=False, delay=0.0):
        self.fail = fail
        self.delay = delay
        self.sent = []

    async def accept(self):
        pass

    async def send_text(self, message):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("closed")
        self.sent.append(json.loads(message))


@pytest.mark.asyncio
async def test_broadcast_reaches_all_and_drops_failed_clients():
    mgr = WebSocketManager()
    good, bad = FakeWs(), FakeWs(fail=True)
    await mgr.connect(good)
    await mgr.connect(bad)
    await mgr.broadcast("print_state", {"state": 1})
    assert good.sent[0]["topic"] == "print_state"
    assert good.sent[0]["data"] == {"state": 1}
    assert mgr.connection_count == 1


@pytest.mark.asyncio
async def test_broadcast_sends_concurrently(monkeypatch):
    import backend.websocket_manager as wsm

    monkeypatch.setattr(wsm, "SEND_TIMEOUT_S", 1.0)
    mgr = WebSocketManager()
    slow = [FakeWs(delay=0.2) for _ in range(5)]
    for ws in slow:
        await mgr.connect(ws)
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    await mgr.broadcast("heartbeat", {})
    # Sequential sends would take ~1.0 s; concurrent ones ~0.2 s.
    assert loop.time() - t0 < 0.6
    assert all(ws.sent for ws in slow)


@pytest.mark.asyncio
async def test_stalled_client_is_dropped_without_blocking_others(monkeypatch):
    import backend.websocket_manager as wsm

    monkeypatch.setattr(wsm, "SEND_TIMEOUT_S", 0.1)
    mgr = WebSocketManager()
    stalled, fine = FakeWs(delay=5.0), FakeWs()
    await mgr.connect(stalled)
    await mgr.connect(fine)
    await mgr.broadcast("heartbeat", {})
    assert fine.sent and not stalled.sent
    assert mgr.connection_count == 1


@pytest.mark.asyncio
async def test_send_to_one_client_drops_it_on_failure():
    mgr = WebSocketManager()
    bad = FakeWs(fail=True)
    await mgr.connect(bad)
    assert await mgr.send(bad, "snapshot", {}) is False
    assert mgr.connection_count == 0
