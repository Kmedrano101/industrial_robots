"""Hardware-independent extruder controller.

Owns the state machine, the safety interlocks and the timing of
retract / prime / purge pulses. It is driven by ``tick(now)`` from the ROS
node's timer and talks to the hardware only through an ``ExtruderDriver``,
so the whole of it is unit-testable with a mock driver and a fake clock.

Interlocks (all derived from the profile):
  * cold extrusion — the screw/filament motor is never turned with zone 0
    below ``min_extrusion_temperature`` (a pellet screw turned cold strips
    its gearbox);
  * maximum temperature per zone — targets above it are rejected, readings
    above it latch a fault;
  * thermal runaway — a zone that is told to heat and does not rise, or
    that drifts away from its target, latches a fault and cuts the heaters;
  * driver watchdog — stale or failed readings latch a fault.
A fault stops the motor and the heaters and stays latched until
``reset_fault``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import math
from typing import Callable, Optional

from .drivers.base import DriverReading, ExtruderDriver
from .profile import ExtruderProfile

# Same numbering as msg/ExtruderState.msg
OFF = 0
EXTRUDING = 1
RETRACTING = 2
PRIMING = 3
HEATING = 4
PURGING = 5
FAULT = 6

STATE_NAMES = {
    OFF: 'OFF', EXTRUDING: 'EXTRUDING', RETRACTING: 'RETRACTING',
    PRIMING: 'PRIMING', HEATING: 'HEATING', PURGING: 'PURGING', FAULT: 'FAULT',
}

WATCHDOG_S = 3.0


@dataclass
class ExtruderStatus:
    state: int = OFF
    target_flow_mm3_s: float = 0.0
    flow_mm3_s: float = 0.0
    zone_temperatures: list[float] = field(default_factory=list)
    zone_targets: list[float] = field(default_factory=list)
    zone_heater_duty: list[float] = field(default_factory=list)
    fan_percent: float = 0.0
    heaters_on: bool = False
    at_temperature: bool = True
    ready: bool = False
    fault: str = ''

    @property
    def state_name(self) -> str:
        return STATE_NAMES.get(self.state, 'UNKNOWN')


@dataclass
class _Pulse:
    """A timed flow burst: retract, prime or purge."""

    state: int
    flow: float
    ends_at: float
    then_flow: float = 0.0           # flow to continue with when it ends


@dataclass
class _ZoneWatch:
    window_start: float = 0.0
    window_temp: float = 0.0
    deviation_since: Optional[float] = None


class ExtruderCore:
    def __init__(
        self,
        profile: ExtruderProfile,
        driver: ExtruderDriver,
        logger: Optional[logging.Logger] = None,
    ):
        self.profile = profile
        self.driver = driver
        self.log = logger or logging.getLogger('extruder')
        n = len(profile.thermal.zones)
        self._targets = [0.0] * n
        self._temps = [0.0] * n
        self._duty = [0.0] * n
        self._watch = [_ZoneWatch() for _ in range(n)]
        self._fan = 0.0
        self._fan_auto = False
        self._flow_target = 0.0        # what the operator / print asked for
        self._flow_cmd = 0.0           # what has been sent, after the slew limit
        self._pulse: Optional[_Pulse] = None
        self._fault = ''
        self._last_tick: Optional[float] = None
        self._last_reading: Optional[DriverReading] = None
        self._at_temp_since: Optional[float] = None
        self._opened = False
        self.on_fault: Optional[Callable[[str], None]] = None

    # ── lifecycle ────────────────────────────────────────────────────────
    def connect(self) -> None:
        self.driver.connect()
        self._opened = True
        if self.profile.fan.present and self.profile.fan.default_percent > 0 \
                and self.profile.fan.auto_on_above <= 0:
            self.set_fan(self.profile.fan.default_percent)

    def close(self) -> None:
        if self._opened:
            try:
                self.driver.set_flow(0.0)
                for z in range(len(self._targets)):
                    self.driver.set_temperature(z, 0.0)
            finally:
                self.driver.close()
                self._opened = False

    # ── queries ──────────────────────────────────────────────────────────
    @property
    def fault(self) -> str:
        return self._fault

    @property
    def has_feedback(self) -> bool:
        return self.profile.thermal.feedback and self.driver.has_temperature_feedback

    def zone_at_temperature(self, i: int) -> bool:
        if self._targets[i] <= 0:
            return True
        if not self.has_feedback:
            return True
        tol = self.profile.thermal.at_temperature_tolerance
        return abs(self._temps[i] - self._targets[i]) <= tol

    def at_temperature(self) -> bool:
        return all(self.zone_at_temperature(i) for i in range(len(self._targets)))

    def heaters_on(self) -> bool:
        return any(t > 0 for t in self._targets)

    def _hot_enough_to_extrude(self) -> tuple[bool, str]:
        """The cold-extrusion interlock."""
        t = self.profile.thermal
        if not t.zones or t.min_extrusion_temperature <= 0:
            return True, ''
        if not self.has_feedback:
            return True, ''
        nozzle = self._temps[0]
        if nozzle < t.min_extrusion_temperature:
            return False, (
                f'cold extrusion blocked: {t.zones[0].name} at {nozzle:.0f} °C, '
                f'minimum {t.min_extrusion_temperature:.0f} °C')
        return True, ''

    def ready(self) -> bool:
        if self._fault:
            return False
        if self._last_reading is None and self.has_feedback:
            return False
        ok, _ = self._hot_enough_to_extrude()
        return ok and self.at_temperature() and self._heatsoak_done()

    def _heatsoak_done(self) -> bool:
        soak = self.profile.thermal.heatsoak_s
        if soak <= 0 or not self.heaters_on() or not self.has_feedback:
            return True
        return self._at_temp_since is not None and \
            (self._last_tick or 0.0) - self._at_temp_since >= soak

    # ── commands ─────────────────────────────────────────────────────────
    def set_flow(self, mm3_s: float) -> tuple[bool, str]:
        """Steady extrusion at ``mm3_s`` (0 = stop). Rejected while faulted
        or cold; clamped to the profile envelope."""
        if mm3_s <= 0:
            self.stop()
            return True, 'extruder off'
        if self._fault:
            return False, f'extruder faulted: {self._fault}'
        ok, why = self._hot_enough_to_extrude()
        if not ok:
            return False, why
        flow = min(mm3_s, self.profile.flow.max_mm3_s)
        if self.profile.flow.min_mm3_s > 0:
            flow = max(flow, self.profile.flow.min_mm3_s)
        self._pulse = None
        self._flow_target = flow
        if self.profile.flow.slew_mm3_s2 >= 1e8:
            # No ramp configured: do not wait for the next tick.
            self._flow_cmd = flow
            self.driver.set_flow(flow)
        self.log.info('extruding at %.2f mm^3/s', flow)
        return True, f'extruding at {flow:.2f} mm^3/s'

    def stop(self) -> None:
        self._pulse = None
        self._flow_target = 0.0
        self._flow_cmd = 0.0
        self.driver.set_flow(0.0)

    def retract(self, then_flow: float = 0.0) -> tuple[bool, str]:
        """Reverse pulse before a travel move. Screw extruders have no
        useful retraction: the profile disables it and this becomes a stop
        (coast), reported as success so a print carries on."""
        r = self.profile.retraction
        if self._fault:
            self.stop()
            return False, f'extruder faulted: {self._fault}'
        if not self.profile.has_retract or not self.driver.has_reverse:
            self.stop()
            return True, 'retraction not available for this extruder: coasting'
        ok, why = self._hot_enough_to_extrude()
        if not ok:
            self.stop()
            return False, why
        duration = r.volume_mm3 / r.rate_mm3_s
        self._start_pulse(RETRACTING, -r.rate_mm3_s, duration, then_flow)
        return True, f'retracting {r.volume_mm3:.1f} mm^3'

    def prime(self, then_flow: float = 0.0) -> tuple[bool, str]:
        """Forward pulse that refills the nozzle after a retract/coast, then
        continues at ``then_flow`` (0 = stop). Without a configured prime
        volume it is just the start of extrusion."""
        if self._fault:
            return False, f'extruder faulted: {self._fault}'
        ok, why = self._hot_enough_to_extrude()
        if not ok:
            return False, why
        r = self.profile.retraction
        if r.prime_volume_mm3 <= 0:
            if then_flow > 0:
                return self.set_flow(then_flow)
            return True, 'no prime configured'
        duration = r.prime_volume_mm3 / r.prime_rate_mm3_s
        self._start_pulse(PRIMING, r.prime_rate_mm3_s, duration,
                          min(then_flow, self.profile.flow.max_mm3_s))
        return True, f'priming {r.prime_volume_mm3:.1f} mm^3'

    def purge(self, volume_mm3: float = 0.0, rate_mm3_s: float = 0.0) -> tuple[bool, str, float]:
        """Extrude a fixed volume to clear the nozzle, then stop."""
        if self._fault:
            return False, f'extruder faulted: {self._fault}', 0.0
        if self._flow_target > 0 or self._pulse is not None:
            return False, 'extruder busy', 0.0
        if not self.ready():
            ok, why = self._hot_enough_to_extrude()
            return False, why or 'extruder not at temperature', 0.0
        p = self.profile.purge
        volume = volume_mm3 if volume_mm3 > 0 else p.volume_mm3
        rate = rate_mm3_s if rate_mm3_s > 0 else p.rate_mm3_s
        if volume <= 0 or rate <= 0:
            return False, 'no purge volume/rate configured', 0.0
        rate = min(rate, self.profile.flow.max_mm3_s)
        duration = volume / rate
        self._start_pulse(PURGING, rate, duration, 0.0)
        return True, f'purging {volume:.0f} mm^3 at {rate:.1f} mm^3/s', duration

    def set_temperature(self, zone: int, target_c: float) -> tuple[bool, str]:
        zones = self.profile.thermal.zones
        if not zones or not self.driver.has_heaters:
            return False, 'this extruder has no controllable heater'
        idx = range(len(zones)) if zone < 0 else [zone]
        if zone >= len(zones):
            return False, f'zone {zone} out of range (0..{len(zones) - 1})'
        if self._fault and target_c > 0:
            return False, f'extruder faulted: {self._fault}'
        for i in idx:
            z = zones[i]
            if target_c > z.max_temperature:
                return False, (f'{z.name}: {target_c:.0f} °C above maximum '
                               f'{z.max_temperature:.0f} °C')
        for i in idx:
            self._set_zone_target(i, max(0.0, target_c))
        names = ', '.join(zones[i].name for i in idx)
        return True, (f'{names} → {target_c:.0f} °C' if target_c > 0 else f'{names} heater off')

    def set_fan(self, percent: float) -> tuple[bool, str]:
        if not (self.profile.fan.present and self.driver.has_fan):
            return False, 'this extruder has no controllable fan'
        self._fan = max(0.0, min(100.0, percent))
        self._fan_auto = False
        self.driver.set_fan(self._fan)
        return True, f'fan {self._fan:.0f} %'

    def heaters_off(self) -> None:
        for i in range(len(self._targets)):
            self._set_zone_target(i, 0.0)

    def emergency_stop(self) -> None:
        self._pulse = None
        self._flow_target = 0.0
        self._flow_cmd = 0.0
        for i in range(len(self._targets)):
            self._targets[i] = 0.0
        self.driver.emergency_stop()
        self._latch_fault('emergency stop')

    def reset_fault(self) -> tuple[bool, str]:
        if not self._fault:
            return True, 'no fault'
        self.log.warning('fault reset by operator: %s', self._fault)
        self._fault = ''
        self._last_reading = None
        for w in self._watch:
            w.window_start = 0.0
            w.deviation_since = None
        return True, 'fault cleared'

    # ── periodic ─────────────────────────────────────────────────────────
    def tick(self, now: float) -> ExtruderStatus:
        dt = 0.0 if self._last_tick is None else max(0.0, now - self._last_tick)
        first = self._last_tick is None
        self._last_tick = now

        self.driver.tick(now)
        reading = self.driver.read()
        self._ingest(reading, now, first)

        if not self._fault:
            self._check_runaway(now)
            self._check_cooled_while_extruding()
        if not self._fault:
            self._auto_fan()
            self._advance_pulse(now)
            self._slew_flow(dt)
        return self.status()

    def status(self) -> ExtruderStatus:
        if self._fault:
            state = FAULT
        elif self._pulse is not None:
            state = self._pulse.state
        elif self._flow_target > 0:
            state = EXTRUDING
        elif self.heaters_on() and not (self.at_temperature() and self._heatsoak_done()):
            state = HEATING
        else:
            state = OFF
        return ExtruderStatus(
            state=state,
            target_flow_mm3_s=self._pulse.flow if self._pulse else self._flow_target,
            flow_mm3_s=self._last_reading.flow_mm3_s if self._last_reading else self._flow_cmd,
            zone_temperatures=list(self._temps),
            zone_targets=list(self._targets),
            zone_heater_duty=list(self._duty),
            fan_percent=self._fan,
            heaters_on=self.heaters_on(),
            at_temperature=self.at_temperature(),
            ready=self.ready(),
            fault=self._fault,
        )

    # ── internals ────────────────────────────────────────────────────────
    def _set_zone_target(self, i: int, target: float) -> None:
        if self._targets[i] == target:
            return
        self._targets[i] = target
        self._watch[i] = _ZoneWatch(window_start=self._last_tick or 0.0,
                                    window_temp=self._temps[i])
        self._at_temp_since = None
        self.driver.set_temperature(i, target)

    def _start_pulse(self, state: int, flow: float, duration: float, then_flow: float) -> None:
        now = self._last_tick or 0.0
        self._pulse = _Pulse(state=state, flow=flow, ends_at=now + duration, then_flow=then_flow)
        self._flow_target = then_flow
        # Pulses bypass the slew limit: a retract that ramps is no retract.
        self._flow_cmd = flow
        self.driver.set_flow(flow)

    def _advance_pulse(self, now: float) -> None:
        p = self._pulse
        if p is None or now < p.ends_at:
            return
        self._pulse = None
        self._flow_target = p.then_flow
        # After a forward pulse (prime) the melt path is already moving:
        # step straight to the print flow. After a retract, ramp up from 0
        # through the slew limit.
        self._flow_cmd = p.then_flow if p.flow > 0 else 0.0
        self.driver.set_flow(self._flow_cmd)

    def _slew_flow(self, dt: float) -> None:
        if self._pulse is not None or dt <= 0:
            return
        target = self._flow_target
        delta = target - self._flow_cmd
        if abs(delta) < 1e-9:
            return
        step = self.profile.flow.slew_mm3_s2 * dt
        new = target if abs(delta) <= step else self._flow_cmd + math.copysign(step, delta)
        self._flow_cmd = new
        self.driver.set_flow(new)

    def _ingest(self, r: DriverReading, now: float, first: bool) -> None:
        if not r.ok:
            self._latch_fault(f'driver error: {r.error or "unknown"}')
            return
        if self._last_reading is not None and now - r.stamp > WATCHDOG_S and self.has_feedback:
            self._latch_fault(f'no data from extruder driver for {now - r.stamp:.0f} s')
            return
        self._last_reading = r
        n = len(self._temps)
        for i in range(min(n, len(r.zone_temperatures))):
            self._temps[i] = r.zone_temperatures[i]
        for i in range(min(n, len(r.zone_heater_duty))):
            self._duty[i] = r.zone_heater_duty[i]
        if self.driver.has_fan and r.fan_percent:
            self._fan = r.fan_percent
        for i, z in enumerate(self.profile.thermal.zones):
            if self.has_feedback and self._temps[i] > z.max_temperature + 5.0:
                self._latch_fault(
                    f'{z.name} over temperature: {self._temps[i]:.0f} °C > '
                    f'{z.max_temperature:.0f} °C')
                return
        if self.heaters_on() and self.at_temperature():
            if self._at_temp_since is None:
                self._at_temp_since = now
        else:
            self._at_temp_since = None

    def _check_runaway(self, now: float) -> None:
        if not self.has_feedback:
            return
        t = self.profile.thermal
        for i, z in enumerate(t.zones):
            target = self._targets[i]
            w = self._watch[i]
            if target <= 0:
                continue
            temp = self._temps[i]
            if temp < target - t.at_temperature_tolerance:
                # Heating phase: must keep rising.
                w.deviation_since = None
                if w.window_start == 0.0:
                    w.window_start, w.window_temp = now, temp
                elif now - w.window_start >= t.runaway_window_s:
                    if temp - w.window_temp < t.runaway_min_rise:
                        self._latch_fault(
                            f'thermal runaway on {z.name}: {w.window_temp:.0f} → {temp:.0f} °C '
                            f'in {t.runaway_window_s:.0f} s with heater on')
                        return
                    w.window_start, w.window_temp = now, temp
            else:
                w.window_start = 0.0
                if abs(temp - target) > t.runaway_max_deviation:
                    if w.deviation_since is None:
                        w.deviation_since = now
                    elif now - w.deviation_since >= t.runaway_window_s:
                        self._latch_fault(
                            f'thermal runaway on {z.name}: {temp:.0f} °C, target {target:.0f} °C')
                        return
                else:
                    w.deviation_since = None

    def _check_cooled_while_extruding(self) -> None:
        """The cold-extrusion interlock, continuously: the check at command
        time does not cover a heater that is switched off (or dies) while
        the screw is turning. 10 °C of hysteresis below the minimum so a
        dip at the tolerance edge does not abort a print."""
        t = self.profile.thermal
        if not t.zones or t.min_extrusion_temperature <= 0 or not self.has_feedback:
            return
        forward = self._flow_target > 0 or (self._pulse is not None and self._pulse.flow > 0)
        if forward and self._temps[0] < t.min_extrusion_temperature - 10.0:
            self._latch_fault(
                f'{t.zones[0].name} cooled to {self._temps[0]:.0f} °C while extruding '
                f'(minimum {t.min_extrusion_temperature:.0f} °C)')

    def _auto_fan(self) -> None:
        f = self.profile.fan
        if not (f.present and self.driver.has_fan and f.auto_on_above > 0 and self.has_feedback):
            return
        if not self._temps:
            return
        hot = self._temps[0] >= f.auto_on_above
        if hot and self._fan <= 0 and not self._fan_auto:
            self._fan = f.default_percent or 100.0
            self._fan_auto = True
            self.driver.set_fan(self._fan)
        elif not hot and self._fan_auto and self._temps[0] < f.auto_on_above - 10.0 \
                and not self.heaters_on():
            self._fan = 0.0
            self._fan_auto = False
            self.driver.set_fan(0.0)

    def _latch_fault(self, why: str) -> None:
        if self._fault:
            return
        self._fault = why
        self.log.error('EXTRUDER FAULT: %s', why)
        self._pulse = None
        self._flow_target = 0.0
        self._flow_cmd = 0.0
        for i in range(len(self._targets)):
            self._targets[i] = 0.0
        try:
            self.driver.emergency_stop()
            for i in range(len(self._targets)):
                self.driver.set_temperature(i, 0.0)
        except Exception as e:  # noqa: BLE001 — the fault must latch regardless
            self.log.error('driver failed during fault handling: %s', e)
        if self.on_fault:
            self.on_fault(why)
