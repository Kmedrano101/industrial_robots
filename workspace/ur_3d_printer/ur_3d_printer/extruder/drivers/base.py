"""Driver interface: the only thing that knows how to talk to the
extruder's electronics.

The controller core calls ``set_flow`` / ``set_temperature`` / ``set_fan``
when a setpoint changes and ``read`` on every tick; a driver that streams
(serial boards) does its I/O in ``tick``. Drivers never decide policy —
whether the nozzle is hot enough to turn the screw is the core's job.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import Optional


@dataclass
class DriverReading:
    """What the hardware reports. Lists are indexed like profile zones."""

    stamp: float = field(default_factory=time.monotonic)
    zone_temperatures: list[float] = field(default_factory=list)
    zone_targets: list[float] = field(default_factory=list)
    zone_heater_duty: list[float] = field(default_factory=list)
    flow_mm3_s: float = 0.0          # measured, or the echo of the command
    fan_percent: float = 0.0
    ok: bool = True                  # False → comms fault (core latches FAULT)
    error: str = ''


class ExtruderDriver(ABC):
    """Base class. Subclasses set the capability flags that are true for
    their electronics; the profile may further restrict them."""

    has_heaters = False
    has_temperature_feedback = False
    has_fan = False
    has_reverse = False               # can run the motor backwards

    def connect(self) -> None:
        """Connect. Raise on failure."""

    def close(self) -> None:
        """Release the hardware; always leaves heaters and motor off."""

    @abstractmethod
    def set_flow(self, mm3_s: float) -> None:
        """Volumetric flow setpoint; negative = reverse, 0 = stop."""

    def set_temperature(self, zone: int, target_c: float) -> None:
        """Heater setpoint, 0 = off. No-op for unheated drivers."""

    def set_fan(self, percent: float) -> None:
        """Fan duty 0..100. No-op without a fan."""

    def emergency_stop(self) -> None:
        """Everything off, immediately, without waiting for acks."""
        self.set_flow(0.0)

    def tick(self, now: float) -> None:
        """Called at the controller rate; streaming drivers do I/O here."""

    @abstractmethod
    def read(self) -> DriverReading:
        """Latest known state; must be cheap (no blocking I/O)."""

    def describe(self) -> Optional[str]:
        """One line for the log, e.g. the port and firmware."""
        return None
