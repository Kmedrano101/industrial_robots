"""WebSocket connection manager for broadcasting ROS2 data to clients."""

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


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

    async def broadcast(self, topic: str, data: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        if not self._connections:
            return

        message = json.dumps({"topic": topic, "data": data, "ts": time.time()})
        disconnected: list[WebSocket] = []

        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)

            for ws in disconnected:
                self._connections.discard(ws)

    async def heartbeat_loop(self) -> None:
        """Send periodic pings to keep connections alive."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            disconnected: list[WebSocket] = []

            async with self._lock:
                for ws in self._connections:
                    try:
                        await ws.send_text(
                            json.dumps({"topic": "heartbeat", "data": {}, "ts": time.time()})
                        )
                    except Exception:
                        disconnected.append(ws)

                for ws in disconnected:
                    self._connections.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


ws_manager = WebSocketManager()
