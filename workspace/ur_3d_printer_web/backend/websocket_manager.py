"""WebSocket connection manager for broadcasting ROS2 data to clients."""

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# A client that cannot take a frame within this long is treated as gone.
# ROS callbacks queue a broadcast per message; one stalled tablet on a bad
# Wi-Fi link must not back up telemetry for everyone else.
SEND_TIMEOUT_S = 2.0


class WebSocketManager:
    """Manages WebSocket connections and broadcasts ROS2 topic data."""

    def __init__(self, heartbeat_interval: float = 5.0):
        self._connections: set[WebSocket] = set()
        self._heartbeat_interval = heartbeat_interval
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info(
            "WebSocket client connected. Total: %d", len(self._connections)
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        logger.info(
            "WebSocket client disconnected. Total: %d", len(self._connections)
        )

    @staticmethod
    def encode(topic: str, data: Any) -> str:
        return json.dumps({"topic": topic, "data": data, "ts": time.time()})

    async def send(self, websocket: WebSocket, topic: str, data: Any) -> bool:
        """Send one frame to one client. Returns False if the client is
        gone (it is then dropped from the set)."""
        ok = await self._send_raw(websocket, self.encode(topic, data))
        if not ok:
            await self.disconnect(websocket)
        return ok

    async def _send_raw(self, websocket: WebSocket, message: str) -> bool:
        try:
            await asyncio.wait_for(websocket.send_text(message), SEND_TIMEOUT_S)
            return True
        except Exception:
            return False

    async def broadcast(self, topic: str, data: Any) -> None:
        """Broadcast a message to all connected clients.

        Sends run concurrently and the lock is only held to snapshot the
        set, so a slow client cannot delay the others or the ROS callback
        that scheduled this. Clients that fail or time out are dropped.
        """
        async with self._lock:
            targets = list(self._connections)
        if not targets:
            return

        message = self.encode(topic, data)
        results = await asyncio.gather(
            *(self._send_raw(ws, message) for ws in targets)
        )
        dead = [ws for ws, ok in zip(targets, results) if not ok]
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)
            logger.info(
                "Dropped %d unresponsive WebSocket client(s). Total: %d",
                len(dead), len(self._connections),
            )

    async def heartbeat_loop(self) -> None:
        """Send periodic pings to keep connections alive and detect dead
        ones even when ROS is quiet."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await self.broadcast("heartbeat", {})

    @property
    def connection_count(self) -> int:
        return len(self._connections)


ws_manager = WebSocketManager()
