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

Abstract extruder controller supporting multiple control methods:
- digital_io: UR digital outputs (on/off)
- analog: UR analog outputs (variable rate)
- topic: Publishes Float64 to configurable topic (e.g., Arduino controller)

Follows the gripper_controller.py pattern from ur_pick_place.
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import Header, Float64

from ur_3d_printer.srv import SetExtruder
from ur_3d_printer.msg import ExtruderState


class ExtruderControllerNode(Node):
    """
    Extruder controller node.

    Services:
        ~/set_extruder: Enable/disable extrusion, set rate, retract, prime

    Publishers:
        ~/extruder_state: Current extruder state
        ~/extruder_command: Float64 command for external controllers (topic mode)
    """

    def __init__(self):
        super().__init__('extruder_controller')

        # Parameters
        self.declare_parameter('extruder_type', 'fdm')  # fdm, paste, digital
        self.declare_parameter('control_method', 'topic')  # digital_io, analog, topic
        self.declare_parameter('command_topic', '~/extruder_command')
        self.declare_parameter('nozzle_diameter', 0.4)  # mm
        self.declare_parameter('filament_diameter', 1.75)  # mm
        self.declare_parameter('max_rate', 0.00001)  # m^3/s
        self.declare_parameter('retraction_distance', 0.005)  # m (5mm filament)
        self.declare_parameter('retraction_speed', 0.001)  # m/s
        self.declare_parameter('prime_distance', 0.005)  # m
        self.declare_parameter('prime_speed', 0.0005)  # m/s
        self.declare_parameter('publish_rate', 50.0)
        self.declare_parameter('transition_time', 0.3)  # seconds

        self.extruder_type = self.get_parameter('extruder_type').value
        self.control_method = self.get_parameter('control_method').value
        self.nozzle_diameter = self.get_parameter('nozzle_diameter').value
        self.filament_diameter = self.get_parameter('filament_diameter').value
        self.max_rate = self.get_parameter('max_rate').value
        self.retraction_distance = self.get_parameter('retraction_distance').value
        self.retraction_speed = self.get_parameter('retraction_speed').value
        self.prime_distance = self.get_parameter('prime_distance').value
        self.prime_speed = self.get_parameter('prime_speed').value
        publish_rate = self.get_parameter('publish_rate').value
        self.transition_time = self.get_parameter('transition_time').value

        # State
        self.current_state = ExtruderState.OFF
        self.current_rate = 0.0
        self.target_rate = 0.0
        self.temperature = 0.0
        self.target_temperature = 0.0
        self.is_transitioning = False
        self.transition_timer_count = 0
        self.transition_total_steps = 0

        # Callback group
        self.callback_group = ReentrantCallbackGroup()

        # Service
        self.set_extruder_srv = self.create_service(
            SetExtruder,
            '~/set_extruder',
            self.set_extruder_callback,
            callback_group=self.callback_group,
        )

        # Publishers
        self.state_pub = self.create_publisher(ExtruderState, '~/extruder_state', 10)
        self.command_pub = self.create_publisher(Float64, '~/extruder_command', 10)

        # Timer
        self.timer = self.create_timer(1.0 / publish_rate, self.timer_callback)

        self.get_logger().info(
            f'Extruder controller initialized: type={self.extruder_type}, '
            f'method={self.control_method}'
        )

    def set_extruder_callback(
        self, request: SetExtruder.Request, response: SetExtruder.Response
    ) -> SetExtruder.Response:
        """Handle extruder set requests."""
        if request.retract:
            self._start_retract()
            response.success = True
            response.message = 'Retracting'
            return response

        if request.prime:
            self._start_prime()
            response.success = True
            response.message = 'Priming'
            return response

        if request.enable:
            rate = request.rate if request.rate > 0 else self.max_rate
            rate = min(rate, self.max_rate)
            self._start_extrusion(rate)
            response.success = True
            response.message = f'Extruding at {rate:.6e} m^3/s'
        else:
            self._stop_extrusion()
            response.success = True
            response.message = 'Extruder off'

        return response

    def _start_extrusion(self, rate: float):
        """Start extruding at given rate."""
        self.target_rate = rate
        self.current_state = ExtruderState.EXTRUDING
        self.is_transitioning = True
        self.transition_timer_count = 0
        self.transition_total_steps = max(
            1, int(self.transition_time * 50)
        )
        self.get_logger().info(f'Starting extrusion at rate {rate:.6e} m^3/s')

    def _stop_extrusion(self):
        """Stop extruding."""
        self.target_rate = 0.0
        self.current_state = ExtruderState.OFF
        self.current_rate = 0.0
        self.is_transitioning = False
        self._send_command(0.0)
        self.get_logger().info('Extruder stopped')

    def _start_retract(self):
        """Retract filament."""
        self.current_state = ExtruderState.RETRACTING
        self.is_transitioning = True
        self.transition_timer_count = 0
        retract_time = self.retraction_distance / self.retraction_speed
        self.transition_total_steps = max(1, int(retract_time * 50))
        self.get_logger().info('Retracting filament')

    def _start_prime(self):
        """Prime filament."""
        self.current_state = ExtruderState.PRIMING
        self.is_transitioning = True
        self.transition_timer_count = 0
        prime_time = self.prime_distance / self.prime_speed
        self.transition_total_steps = max(1, int(prime_time * 50))
        self.get_logger().info('Priming filament')

    def timer_callback(self):
        """Update extruder state and publish."""
        # Handle transitions
        if self.is_transitioning:
            self.transition_timer_count += 1
            progress = min(
                1.0, self.transition_timer_count / self.transition_total_steps
            )

            if self.current_state == ExtruderState.EXTRUDING:
                self.current_rate = self.target_rate * progress
                self._send_command(self.current_rate)
            elif self.current_state == ExtruderState.RETRACTING:
                self._send_command(-self.retraction_speed * (1.0 - progress))
            elif self.current_state == ExtruderState.PRIMING:
                self._send_command(self.prime_speed * (1.0 - progress))

            if progress >= 1.0:
                self.is_transitioning = False
                if self.current_state == ExtruderState.EXTRUDING:
                    self.current_rate = self.target_rate
                elif self.current_state in (
                    ExtruderState.RETRACTING, ExtruderState.PRIMING
                ):
                    self.current_state = ExtruderState.OFF
                    self.current_rate = 0.0
                    self._send_command(0.0)

        # Publish state
        state_msg = ExtruderState()
        state_msg.header = Header()
        state_msg.header.stamp = self.get_clock().now().to_msg()
        state_msg.state = self.current_state
        state_msg.extrusion_rate = self.current_rate
        state_msg.temperature = self.temperature
        state_msg.target_temperature = self.target_temperature
        state_msg.at_temperature = abs(
            self.temperature - self.target_temperature
        ) < 2.0 if self.target_temperature > 0 else True
        self.state_pub.publish(state_msg)

    def _send_command(self, value: float):
        """Send extruder command based on control method."""
        if self.control_method == 'topic':
            msg = Float64()
            msg.data = value
            self.command_pub.publish(msg)
        elif self.control_method == 'digital_io':
            # UR digital output: on if value > 0
            msg = Float64()
            msg.data = 1.0 if value > 0 else 0.0
            self.command_pub.publish(msg)
        elif self.control_method == 'analog':
            # Scale to 0-10V range
            if self.max_rate > 0:
                scaled = min(1.0, abs(value) / self.max_rate) * 10.0
            else:
                scaled = 0.0
            msg = Float64()
            msg.data = scaled
            self.command_pub.publish(msg)


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
