"""Driver for extruders wired to the UR controller's own I/O through the
driver's ``io_and_status_controller/set_io`` service.

  * ``enable_pin``     digital output, ON while flow ≠ 0
  * ``direction_pin``  digital output, ON for reverse (optional)
  * ``rate_pin``       analog output; level = |flow| / max_flow (0..1 ratio,
                       i.e. 0..10 V or 4..20 mA as configured on the pendant)
  * ``fan_pin``        digital output (optional)

There is no temperature path here: heaters are run by an external
temperature controller (a PID box). Set ``thermal.feedback: false`` in the
profile and keep the interlocks on that controller.
"""

from __future__ import annotations

import time
from typing import Optional

from .base import DriverReading, ExtruderDriver


class UrIoExtruderDriver(ExtruderDriver):
    has_heaters = False
    has_temperature_feedback = False
    has_fan = True
    has_reverse = True

    def __init__(
        self,
        node,
        zones: int,
        max_flow_mm3_s: float,
        enable_pin: int = 0,
        direction_pin: int = -1,
        rate_pin: int = 0,
        fan_pin: int = -1,
        service: str = '/io_and_status_controller/set_io',
        **_ignored,
    ):
        from ur_msgs.srv import SetIO

        self._SetIO = SetIO
        self.node = node
        self.max_flow = float(max_flow_mm3_s)
        self.enable_pin, self.direction_pin = int(enable_pin), int(direction_pin)
        self.rate_pin, self.fan_pin = int(rate_pin), int(fan_pin)
        self.has_fan = self.fan_pin >= 0
        self.has_reverse = self.direction_pin >= 0
        self.service = service
        self._client = node.create_client(SetIO, service)
        self._flow = 0.0
        self._fan = 0.0
        self._error = ''
        self._last_ok = time.monotonic()
        self._n_zones = zones

    def connect(self) -> None:
        if not self._client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError(f'{self.service} not available (is the UR driver up?)')
        self.set_flow(0.0)

    def set_flow(self, mm3_s: float) -> None:
        self._flow = mm3_s
        level = min(1.0, abs(mm3_s) / self.max_flow) if self.max_flow > 0 else 0.0
        if self.direction_pin >= 0:
            self._io(self._SetIO.Request.FUN_SET_DIGITAL_OUT, self.direction_pin,
                     1.0 if mm3_s < 0 else 0.0)
        self._io(self._SetIO.Request.FUN_SET_ANALOG_OUT, self.rate_pin, level)
        self._io(self._SetIO.Request.FUN_SET_DIGITAL_OUT, self.enable_pin,
                 1.0 if mm3_s != 0 else 0.0)

    def set_fan(self, percent: float) -> None:
        if self.fan_pin < 0:
            return
        self._fan = percent
        self._io(self._SetIO.Request.FUN_SET_DIGITAL_OUT, self.fan_pin,
                 1.0 if percent > 0 else 0.0)

    def emergency_stop(self) -> None:
        self._flow = 0.0
        self._io(self._SetIO.Request.FUN_SET_DIGITAL_OUT, self.enable_pin, 0.0)
        self._io(self._SetIO.Request.FUN_SET_ANALOG_OUT, self.rate_pin, 0.0)

    def read(self) -> DriverReading:
        if self._error:
            return DriverReading(ok=False, error=self._error)
        return DriverReading(stamp=time.monotonic(), flow_mm3_s=self._flow, fan_percent=self._fan)

    def describe(self) -> str:
        return (f'UR I/O: enable DO{self.enable_pin}, rate AO{self.rate_pin}'
                + (f', dir DO{self.direction_pin}' if self.direction_pin >= 0 else ''))

    def _io(self, fun: int, pin: int, state: float) -> None:
        req = self._SetIO.Request()
        req.fun, req.pin, req.state = int(fun), int(pin), float(state)
        fut = self._client.call_async(req)
        fut.add_done_callback(self._done)

    def _done(self, fut) -> None:
        try:
            res: Optional[object] = fut.result()
            if res is None or not getattr(res, 'success', False):
                self._error = f'{self.service} refused the I/O command'
            else:
                self._last_ok = time.monotonic()
        except Exception as e:  # noqa: BLE001
            self._error = f'{self.service} failed: {e}'
