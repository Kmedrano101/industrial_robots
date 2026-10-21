# Copyright 2024 Kevin Medrano
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Extruder Controller Node

Thin ROS 2 wrapper around ``ur_3d_printer.extruder``: loads the extruder
profile, builds the driver, and exposes the core over services and
topics. All policy lives in the core; all hardware access in the driver.

Parameters:
    profile        profile name in config/extruders (or a YAML path)
    driver         override the profile's driver: mock | gcode_serial | topic | ur_io
    serial_port    override driver.port for gcode_serial
    serial_baud    override driver.baud for gcode_serial
    publish_rate   state publish / control tick rate (Hz)

Services (all under the node name):
    ~/set_extruder          ur_3d_printer/SetExtruder  (print_node contract)
    ~/set_temperature       ur_3d_printer/SetExtruderTemperature
    ~/set_fan               ur_3d_printer/SetExtruderFan
    ~/purge                 ur_3d_printer/PurgeExtruder
    ~/reset_fault           std_srvs/Trigger
    ~/heaters_off           std_srvs/Trigger

Topics:
    ~/extruder_state        ur_3d_printer/ExtruderState   (publish_rate)
    ~/extruder_info         ur_3d_printer/ExtruderInfo    (latched)
"""

from __future__ import annotations

import logging
import os
import time

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Header
from std_srvs.srv import Trigger

from ur_3d_printer.extruder import ExtruderCore, load_profile
from ur_3d_printer.extruder.drivers import make_driver
from ur_3d_printer.msg import ExtruderInfo, ExtruderState
from ur_3d_printer.srv import (
    PurgeExtruder, SetExtruder, SetExtruderFan, SetExtruderTemperature,
)


class _RosLogAdapter(logging.Logger):
    """Route the core's logging calls to the node logger."""

    def __init__(self, ros_logger):
        super().__init__('extruder')
        self._ros = ros_logger

    def info(self, msg, *args, **kwargs):      # noqa: D102
        self._ros.info(msg % args if args else msg)

    def warning(self, msg, *args, **kwargs):   # noqa: D102
        self._ros.warn(msg % args if args else msg)

    def error(self, msg, *args, **kwargs):     # noqa: D102
        self._ros.error(msg % args if args else msg)


class ExtruderControllerNode(Node):
    def __init__(self):
        super().__init__('extruder_controller')

        self.declare_parameter('profile', 'generic_fdm')
        self.declare_parameter('driver', '')
        self.declare_parameter('serial_port', '')
        self.declare_parameter('serial_baud', 0)
        self.declare_parameter('publish_rate', 50.0)

        profile_name = self.get_parameter('profile').value
        driver_override = self.get_parameter('driver').value or None
        publish_rate = float(self.get_parameter('publish_rate').value)

        share = get_package_share_directory('ur_3d_printer')
        search = [os.path.join(share, 'config', 'extruders')]
        self.profile = load_profile(profile_name, search)

        overrides = {
            'port': self.get_parameter('serial_port').value,
            'baud': self.get_parameter('serial_baud').value or None,
        }
        self.driver = make_driver(self.profile, driver_override, node=self, overrides=overrides)
        self.core = ExtruderCore(self.profile, self.driver,
                                 logger=_RosLogAdapter(self.get_logger()))
        self.core.connect()

        self.get_logger().info(
            f'Extruder: {self.profile.name} ({self.profile.kind}), '
            f'driver {driver_override or self.profile.driver}'
            + (f' — {self.driver.describe()}' if self.driver.describe() else '')
        )
        if self.profile.thermal.zones and not self.core.has_feedback:
            self.get_logger().warn(
                'No temperature feedback with this driver: the cold-extrusion and '
                'runaway interlocks are OFF. Keep them on the external controller.')

        cb = ReentrantCallbackGroup()
        self.create_service(SetExtruder, '~/set_extruder', self._on_set_extruder,
                            callback_group=cb)
        self.create_service(SetExtruderTemperature, '~/set_temperature',
                            self._on_set_temperature, callback_group=cb)
        self.create_service(SetExtruderFan, '~/set_fan', self._on_set_fan, callback_group=cb)
        self.create_service(PurgeExtruder, '~/purge', self._on_purge, callback_group=cb)
        self.create_service(Trigger, '~/reset_fault', self._on_reset_fault, callback_group=cb)
        self.create_service(Trigger, '~/heaters_off', self._on_heaters_off, callback_group=cb)

        self.state_pub = self.create_publisher(ExtruderState, '~/extruder_state', 10)
        latched = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.info_pub = self.create_publisher(ExtruderInfo, '~/extruder_info', latched)
        self.info_pub.publish(self._info_msg())

        self.timer = self.create_timer(1.0 / publish_rate, self._tick)

    # ── services ─────────────────────────────────────────────────────────
    def _on_set_extruder(self, req: SetExtruder.Request, res: SetExtruder.Response):
        """print_node contract: enable/rate (m³/s), retract, prime."""
        flow = req.rate * 1e9 if req.rate > 0 else self.profile.flow.default_mm3_s
        if req.retract:
            ok, msg = self.core.retract(then_flow=flow if req.enable else 0.0)
        elif req.prime:
            ok, msg = self.core.prime(then_flow=flow if req.enable else 0.0)
        elif req.enable:
            ok, msg = self.core.set_flow(flow)
        else:
            self.core.stop()
            ok, msg = True, 'extruder off'
        res.success, res.message = ok, msg
        if not ok:
            self.get_logger().warn(f'set_extruder refused: {msg}')
        return res

    def _on_set_temperature(self, req, res):
        res.success, res.message = self.core.set_temperature(int(req.zone), float(req.target))
        return res

    def _on_set_fan(self, req, res):
        res.success, res.message = self.core.set_fan(float(req.percent))
        return res

    def _on_purge(self, req, res):
        res.success, res.message, res.duration_s = self.core.purge(
            float(req.volume_mm3), float(req.rate_mm3_s))
        return res

    def _on_reset_fault(self, _req, res):
        res.success, res.message = self.core.reset_fault()
        return res

    def _on_heaters_off(self, _req, res):
        self.core.heaters_off()
        res.success, res.message = True, 'heaters off'
        return res

    # ── periodic ─────────────────────────────────────────────────────────
    def _tick(self):
        st = self.core.tick(time.monotonic())
        msg = ExtruderState()
        msg.header = Header(stamp=self.get_clock().now().to_msg())
        msg.state = st.state
        msg.extrusion_rate = st.flow_mm3_s * 1e-9
        msg.temperature = st.zone_temperatures[0] if st.zone_temperatures else 0.0
        msg.target_temperature = st.zone_targets[0] if st.zone_targets else 0.0
        msg.at_temperature = st.at_temperature
        msg.target_flow_mm3_s = st.target_flow_mm3_s
        msg.flow_mm3_s = st.flow_mm3_s
        msg.zone_temperatures = st.zone_temperatures
        msg.zone_targets = st.zone_targets
        msg.zone_heater_duty = st.zone_heater_duty
        msg.fan_percent = st.fan_percent
        msg.heaters_on = st.heaters_on
        msg.ready = st.ready
        msg.fault = st.fault
        self.state_pub.publish(msg)

    def _info_msg(self) -> ExtruderInfo:
        p = self.profile
        m = ExtruderInfo()
        m.name, m.model, m.kind = p.name, p.model, p.kind
        m.driver = self.get_parameter('driver').value or p.driver
        m.nozzle_diameter_mm = p.nozzle_diameter_mm
        m.zone_names = p.zone_names
        m.zone_max_temperature = [z.max_temperature for z in p.thermal.zones]
        m.min_extrusion_temperature = p.thermal.min_extrusion_temperature
        m.at_temperature_tolerance = p.thermal.at_temperature_tolerance
        m.max_flow_mm3_s = p.flow.max_mm3_s
        m.default_flow_mm3_s = p.flow.default_mm3_s
        m.has_heaters = bool(p.thermal.zones) and self.driver.has_heaters
        m.has_temperature_feedback = self.core.has_feedback
        m.has_fan = p.fan.present and self.driver.has_fan
        m.has_retract = p.has_retract and self.driver.has_reverse
        m.has_purge = p.has_purge
        m.purge_volume_mm3 = p.purge.volume_mm3
        m.purge_rate_mm3_s = p.purge.rate_mm3_s
        return m

    def destroy_node(self):
        try:
            self.core.close()
        finally:
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ExtruderControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
