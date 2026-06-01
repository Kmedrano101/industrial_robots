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
    from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
    from std_srvs.srv import Trigger

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
            # ur_dashboard_msgs/RobotMode mode int:
            #   -1 NO_CONTROLLER, 0 DISCONNECTED, 1 CONFIRM_SAFETY, 2 BOOTING,
            #    3 POWER_OFF, 4 POWER_ON, 5 IDLE, 6 BACKDRIVE, 7 RUNNING,
            #    8 UPDATING_FIRMWARE
            "robot_mode": {"mode": -1, "mode_name": "UNKNOWN"},
            # ur_dashboard_msgs/SafetyMode mode int:
            #   1 NORMAL, 2 REDUCED, 3 PROTECTIVE_STOP, 4 RECOVERY,
            #   5 SAFEGUARD_STOP, 6 SYSTEM_EMERGENCY_STOP,
            #   7 ROBOT_EMERGENCY_STOP, 8 VIOLATION, 9 FAULT,
            #   10 VALIDATE_JOINT_ID, 11 UNDEFINED_SAFETY_MODE
            "safety_mode": {"mode": 0, "mode_name": "UNKNOWN"},
        }

        self._last_joint_broadcast = 0.0
        self._joint_throttle_interval = 0.1  # 10 Hz

        # Dashboard service clients (std_srvs/Trigger). Populated in
        # _setup_dashboard_clients().
        self.power_on_client = None
        self.power_off_client = None
        self.brake_release_client = None
        self.play_client = None
        self.stop_client = None

        # Publisher for jog / move-to-home trajectories.
        self.joint_trajectory_pub = None
        self.joint_names: list[str] = [
            "shoulder_pan_joint",
            "shoulder_lift_joint",
            "elbow_joint",
            "wrist_1_joint",
            "wrist_2_joint",
            "wrist_3_joint",
        ]

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
        self._setup_dashboard_clients()
        self._setup_motion_publisher()

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

        # UR driver health topics. ur_dashboard_msgs may not be importable
        # in pure-standalone test environments, so guard the import.
        try:
            from ur_dashboard_msgs.msg import RobotMode, SafetyMode

            self._robot_mode_names = {
                -1: "NO_CONTROLLER",
                0: "DISCONNECTED",
                1: "CONFIRM_SAFETY",
                2: "BOOTING",
                3: "POWER_OFF",
                4: "POWER_ON",
                5: "IDLE",
                6: "BACKDRIVE",
                7: "RUNNING",
                8: "UPDATING_FIRMWARE",
            }
            self._safety_mode_names = {
                1: "NORMAL",
                2: "REDUCED",
                3: "PROTECTIVE_STOP",
                4: "RECOVERY",
                5: "SAFEGUARD_STOP",
                6: "SYSTEM_EMERGENCY_STOP",
                7: "ROBOT_EMERGENCY_STOP",
                8: "VIOLATION",
                9: "FAULT",
                10: "VALIDATE_JOINT_ID",
                11: "UNDEFINED_SAFETY_MODE",
            }
            self._node.create_subscription(
                RobotMode,
                "/io_and_status_controller/robot_mode",
                self._on_robot_mode,
                10,
            )
            self._node.create_subscription(
                SafetyMode,
                "/io_and_status_controller/safety_mode",
                self._on_safety_mode,
                10,
            )
        except ImportError:
            logger.warning(
                "ur_dashboard_msgs not available — robot/safety mode will stay UNKNOWN"
            )
            self._robot_mode_names = {}
            self._safety_mode_names = {}

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

    def _setup_dashboard_clients(self) -> None:
        """Create std_srvs/Trigger clients for the UR dashboard."""
        try:
            self.power_on_client = self._node.create_client(
                Trigger, "/dashboard_client/power_on"
            )
            self.power_off_client = self._node.create_client(
                Trigger, "/dashboard_client/power_off"
            )
            self.brake_release_client = self._node.create_client(
                Trigger, "/dashboard_client/brake_release"
            )
            self.play_client = self._node.create_client(
                Trigger, "/dashboard_client/play"
            )
            self.stop_client = self._node.create_client(
                Trigger, "/dashboard_client/stop"
            )
        except Exception:
            logger.exception("failed to create dashboard service clients")

    def _setup_motion_publisher(self) -> None:
        """Publisher for the joint trajectory controller's command topic."""
        try:
            self.joint_trajectory_pub = self._node.create_publisher(
                JointTrajectory,
                "/scaled_joint_trajectory_controller/joint_trajectory",
                10,
            )
        except Exception:
            logger.exception("failed to create joint trajectory publisher")

    def publish_joint_trajectory(
        self,
        target_positions: list[float],
        duration_s: float,
    ) -> bool:
        """Publish a single-point JointTrajectory to drive the robot.

        Returns True if the message was queued for publish, False if the
        publisher is unavailable.
        """
        if self.joint_trajectory_pub is None:
            return False
        if len(target_positions) != len(self.joint_names):
            raise ValueError(
                f"expected {len(self.joint_names)} joints, got {len(target_positions)}"
            )

        msg = JointTrajectory()
        msg.joint_names = list(self.joint_names)
        pt = JointTrajectoryPoint()
        pt.positions = [float(p) for p in target_positions]
        pt.velocities = [0.0] * len(self.joint_names)
        # time_from_start: builtin_interfaces/Duration
        sec = int(duration_s)
        nsec = int((duration_s - sec) * 1e9)
        pt.time_from_start.sec = sec
        pt.time_from_start.nanosec = nsec
        msg.points = [pt]
        self.joint_trajectory_pub.publish(msg)
        return True

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

    def _on_robot_mode(self, msg) -> None:
        data = {
            "mode": int(msg.mode),
            "mode_name": self._robot_mode_names.get(int(msg.mode), "UNKNOWN"),
        }
        self.latest_state["robot_mode"] = data
        self._broadcast_async("robot_mode", data)

    def _on_safety_mode(self, msg) -> None:
        data = {
            "mode": int(msg.mode),
            "mode_name": self._safety_mode_names.get(int(msg.mode), "UNKNOWN"),
        }
        self.latest_state["safety_mode"] = data
        self._broadcast_async("safety_mode", data)

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
