"""Driver that hands the setpoints to another ROS node over topics —
an Arduino/micro-ROS bridge, a PLC gateway, or any custom electronics.

  * ``<command_topic>``        std_msgs/Float64, flow in m³/s (legacy units,
                               kept so existing sketches keep working)
  * ``<temperature_cmd_topic>`` std_msgs/Float64MultiArray, °C per zone
  * ``<fan_topic>``            std_msgs/Float64, 0..100
  * ``<temperature_topic>``    std_msgs/Float64MultiArray, °C per zone,
                               published by the hardware (optional)

Feedback only exists if the hardware publishes temperatures; set
``thermal.feedback: false`` in the profile otherwise.
"""

from __future__ import annotations

import time

from .base import DriverReading, ExtruderDriver


class TopicExtruderDriver(ExtruderDriver):
    has_heaters = True
    has_temperature_feedback = True
    has_fan = True
    has_reverse = True

    def __init__(
        self,
        node,
        zones: int,
        command_topic: str = '~/extruder_command',
        temperature_cmd_topic: str = '~/extruder_target_temperature',
        temperature_topic: str = '~/extruder_temperature',
        fan_topic: str = '~/extruder_fan',
        **_ignored,
    ):
        from std_msgs.msg import Float64, Float64MultiArray

        self._Float64 = Float64
        self._Array = Float64MultiArray
        self.n = zones
        self.node = node
        self._cmd_pub = node.create_publisher(Float64, command_topic, 10)
        self._temp_pub = node.create_publisher(Float64MultiArray, temperature_cmd_topic, 10)
        self._fan_pub = node.create_publisher(Float64, fan_topic, 10)
        self._temp_sub = node.create_subscription(
            Float64MultiArray, temperature_topic, self._on_temps, 10)
        self._targets = [0.0] * zones
        self._temps = [0.0] * zones
        self._flow = 0.0
        self._fan = 0.0
        self._last_report = 0.0
        self.command_topic = command_topic

    def set_flow(self, mm3_s: float) -> None:
        self._flow = mm3_s
        self._cmd_pub.publish(self._Float64(data=mm3_s * 1e-9))

    def set_temperature(self, zone: int, target_c: float) -> None:
        self._targets[zone] = target_c
        self._temp_pub.publish(self._Array(data=list(self._targets)))

    def set_fan(self, percent: float) -> None:
        self._fan = percent
        self._fan_pub.publish(self._Float64(data=percent))

    def emergency_stop(self) -> None:
        self._flow = 0.0
        self._targets = [0.0] * self.n
        self._cmd_pub.publish(self._Float64(data=0.0))
        self._temp_pub.publish(self._Array(data=list(self._targets)))

    def read(self) -> DriverReading:
        return DriverReading(
            stamp=self._last_report or time.monotonic(),
            zone_temperatures=list(self._temps),
            zone_targets=list(self._targets),
            flow_mm3_s=self._flow,
            fan_percent=self._fan,
        )

    def describe(self) -> str:
        return f'topic driver, commands on {self.command_topic}'

    def _on_temps(self, msg) -> None:
        for i, v in enumerate(list(msg.data)[: self.n]):
            self._temps[i] = float(v)
        self._last_report = time.monotonic()
