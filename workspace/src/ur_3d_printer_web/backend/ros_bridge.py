"""ROS2 bridge node that subscribes to topics and provides service clients."""

import asyncio
import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ROS2 imports are optional — the backend can run in standalone mode for
# frontend development without a ROS2 environment.
try:
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.node import Node
    from sensor_msgs.msg import JointState

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    logger.warning("rclpy not available — running in standalone mode (no ROS2)")


class RosBridge:
    """Bridges ROS2 topics/services to the web backend via callbacks."""

    def __init__(self, ws_broadcast_fn):
        self._ws_broadcast = ws_broadcast_fn
        self._node: Optional[Any] = None
        self._executor: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Cached latest state for GET /api/state
        self.latest_state: dict[str, Any] = {
            "print_state": {"state": 0, "state_name": "IDLE", "error_message": ""},
            "print_progress": {
                "current_layer": 0,
                "total_layers": 0,
                "layer_progress": 0.0,
                "overall_progress": 0.0,
                "elapsed_time": 0.0,
                "estimated_remaining": 0.0,
                "current_z_height": 0.0,
            },
            "extruder_state": {
                "state": 0,
                "extrusion_rate": 0.0,
                "temperature": 0.0,
                "target_temperature": 0.0,
                "at_temperature": False,
            },
            "joint_states": {"positions": [0.0] * 6},
        }

        self._last_joint_broadcast = 0.0
        self._joint_throttle_interval = 0.1  # 10 Hz

    def start(self) -> None:
        """Start the ROS2 node in a background thread."""
        if not ROS2_AVAILABLE:
            logger.info("ROS2 not available — bridge running in standalone mode")
            return

        if self._running:
            return

        rclpy.init()
        self._node = rclpy.create_node("web_interface_bridge")
        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._node)

        self._setup_subscriptions()
        self._setup_service_clients()

        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        logger.info("ROS2 bridge node started")

    def _spin(self) -> None:
        """Spin the executor in a background thread."""
        try:
            self._executor.spin()
        except Exception:
            logger.exception("ROS2 executor error")

    def _setup_subscriptions(self) -> None:
        """Create topic subscriptions."""
        try:
            from ur_3d_printer.msg import ExtruderState, PrintProgress, PrintState

            self._node.create_subscription(
                PrintState, "/print_node/state", self._on_print_state, 10
            )
            self._node.create_subscription(
                PrintProgress, "/print_node/progress", self._on_print_progress, 10
            )
            self._node.create_subscription(
                ExtruderState,
                "/extruder_controller/extruder_state",
                self._on_extruder_state,
                10,
            )
        except ImportError:
            logger.warning("ur_3d_printer messages not available — skipping custom subs")

        self._node.create_subscription(
            JointState, "/joint_states", self._on_joint_states, 10
        )

    def _setup_service_clients(self) -> None:
        """Create service clients for print control."""
        try:
            from ur_3d_printer.srv import (
                CalibrateOrigin,
                CancelPrint,
                PausePrint,
                ResumePrint,
                SetExtruder,
                StartPrint,
            )

            self.start_print_client = self._node.create_client(
                StartPrint, "/print_node/start_print"
            )
            self.pause_print_client = self._node.create_client(
                PausePrint, "/print_node/pause_print"
            )
            self.resume_print_client = self._node.create_client(
                ResumePrint, "/print_node/resume_print"
            )
            self.cancel_print_client = self._node.create_client(
                CancelPrint, "/print_node/cancel_print"
            )
            self.calibrate_client = self._node.create_client(
                CalibrateOrigin, "/print_node/calibrate_origin"
            )
            self.extruder_client = self._node.create_client(
                SetExtruder, "/extruder_controller/set_extruder"
            )
        except ImportError:
            logger.warning("ur_3d_printer services not available — skipping clients")
            self.start_print_client = None
            self.pause_print_client = None
            self.resume_print_client = None
            self.cancel_print_client = None
            self.calibrate_client = None
            self.extruder_client = None

    def _broadcast_async(self, topic: str, data: dict) -> None:
        """Schedule a WebSocket broadcast from the ROS2 callback thread."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._ws_broadcast(topic, data))
        except RuntimeError:
            pass

    def _on_print_state(self, msg) -> None:
        data = {
            "state": msg.state,
            "state_name": msg.state_name,
            "error_message": msg.error_message,
        }
        self.latest_state["print_state"] = data
        self._broadcast_async("print_state", data)

    def _on_print_progress(self, msg) -> None:
        data = {
            "current_layer": msg.current_layer,
            "total_layers": msg.total_layers,
            "layer_progress": msg.layer_progress,
            "overall_progress": msg.overall_progress,
            "elapsed_time": msg.elapsed_time,
            "estimated_remaining": msg.estimated_remaining,
            "current_z_height": msg.current_z_height,
        }
        self.latest_state["print_progress"] = data
        self._broadcast_async("print_progress", data)

    def _on_extruder_state(self, msg) -> None:
        data = {
            "state": msg.state,
            "extrusion_rate": msg.extrusion_rate,
            "temperature": msg.temperature,
            "target_temperature": msg.target_temperature,
            "at_temperature": msg.at_temperature,
        }
        self.latest_state["extruder_state"] = data
        self._broadcast_async("extruder_state", data)

    def _on_joint_states(self, msg) -> None:
        now = time.time()
        if now - self._last_joint_broadcast < self._joint_throttle_interval:
            return
        self._last_joint_broadcast = now

        data = {"positions": list(msg.position[:6])}
        self.latest_state["joint_states"] = data
        self._broadcast_async("joint_states", data)

    async def call_service(self, client, request, timeout: float = 5.0):
        """Call a ROS2 service asynchronously from FastAPI."""
        if client is None:
            return None

        future = client.call_async(request)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: rclpy.spin_until_future_complete(self._node, future, timeout)
        )
        if future.done():
            return future.result()
        return None

    def shutdown(self) -> None:
        """Shutdown the ROS2 node."""
        self._running = False
        if self._executor:
            self._executor.shutdown()
        if self._node:
            self._node.destroy_node()
        if ROS2_AVAILABLE:
            try:
                rclpy.shutdown()
            except Exception:
                pass
        logger.info("ROS2 bridge node shutdown")


# Module-level singleton — initialized in main.py lifespan
ros_bridge: Optional[RosBridge] = None
