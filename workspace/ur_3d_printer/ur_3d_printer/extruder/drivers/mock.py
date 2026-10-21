"""Simulated extruder electronics.

A first-order thermal model per zone and a flow that follows the command
with a short time constant. Used by the Docker stack when no extruder is
wired (so the UI and print_node behave as with real hardware), and by the
unit tests, which can also inject faults: a dead heater for the runaway
check, a comms failure for the watchdog.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from .base import DriverReading, ExtruderDriver


class MockExtruderDriver(ExtruderDriver):
    has_heaters = True
    has_temperature_feedback = True
    has_fan = True
    has_reverse = True

    def __init__(
        self,
        zones: int,
        ambient_c: float = 22.0,
        heating_rate_c_s: float = 4.0,     # CHC 80 W on a small barrel: fast
        cooling_tau_s: float = 120.0,
        flow_tau_s: float = 0.3,
        clock: Optional[Callable[[], float]] = None,
        **_ignored,
    ):
        self.n = zones
        self.ambient = ambient_c
        self.heating_rate = heating_rate_c_s
        self.cooling_tau = cooling_tau_s
        self.flow_tau = flow_tau_s
        self.clock = clock or time.monotonic
        self.temps = [ambient_c] * zones
        self.targets = [0.0] * zones
        self.duty = [0.0] * zones
        self.flow_cmd = 0.0
        self.flow = 0.0
        self.fan = 0.0
        self.heater_broken = [False] * zones      # test hook: runaway
        self.comms_ok = True                      # test hook: watchdog
        self.commands: list[tuple] = []           # test hook: what was sent
        self._last = None

    def connect(self) -> None:
        self._last = self.clock()

    def set_flow(self, mm3_s: float) -> None:
        self.flow_cmd = mm3_s
        self.commands.append(('flow', mm3_s))

    def set_temperature(self, zone: int, target_c: float) -> None:
        self.targets[zone] = target_c
        self.commands.append(('temp', zone, target_c))

    def set_fan(self, percent: float) -> None:
        self.fan = percent
        self.commands.append(('fan', percent))

    def emergency_stop(self) -> None:
        self.flow_cmd = 0.0
        self.targets = [0.0] * self.n
        self.commands.append(('estop',))

    def tick(self, now: float) -> None:
        if self._last is None:
            self._last = now
            return
        dt = max(0.0, now - self._last)
        self._last = now
        for i in range(self.n):
            t, target = self.temps[i], self.targets[i]
            if target > 0 and not self.heater_broken[i]:
                # Bang-bang with a proportional band, like a board's PID
                # near the setpoint; the "heater" is a fixed rise rate.
                self.duty[i] = max(0.0, min(1.0, (target - t) / 10.0))
            else:
                self.duty[i] = 0.0
            rise = self.duty[i] * self.heating_rate * dt
            fall = (t - self.ambient) / self.cooling_tau * dt
            self.temps[i] = t + rise - fall
        a = min(1.0, dt / self.flow_tau) if self.flow_tau > 0 else 1.0
        self.flow += (self.flow_cmd - self.flow) * a

    def read(self) -> DriverReading:
        if not self.comms_ok:
            return DriverReading(stamp=self.clock(), ok=False, error='simulated comms loss')
        return DriverReading(
            stamp=self.clock(),
            zone_temperatures=list(self.temps),
            zone_targets=list(self.targets),
            zone_heater_duty=list(self.duty),
            flow_mm3_s=self.flow,
            fan_percent=self.fan,
        )

    def describe(self) -> str:
        return f'mock extruder, {self.n} zone(s), ambient {self.ambient:.0f} °C'
