"""Driver for a 3D-printer control board (Marlin, Klipper, RepRapFirmware)
over USB serial.

This is the practical way to run a pellet extruder such as the Mahor V5:
the board carries the stepper driver, the heater MOSFETs and the
thermistor ADCs, closes the temperature loops with its own PID, and we
drive it with plain G-code:

  * heaters   — ``M104 T<n> S<t>`` per zone, ``M140`` for a zone mapped to
                the bed output; ``M105`` / ``M155`` for readings;
  * flow      — continuous extrusion is streamed as short relative
                ``G1 E<mm> F<mm/min>`` moves, kept ``lookahead_s`` ahead of
                the board's planner so the screw never starves and a stop
                takes effect within one chunk;
  * fan       — ``M106 S<0..255>``;
  * e-stop    — ``M112``.

The board's E axis must be calibrated in mm³: configure its steps/mm so
that one "E millimetre" is one cubic millimetre (``e_mm_per_mm3`` lets you
keep a differently calibrated board). Serial access goes through a small
transport interface so the tests run against a fake board.
"""

from __future__ import annotations

from collections import deque
import re
import time
from typing import Optional

from .base import DriverReading, ExtruderDriver

_TEMP_RE = re.compile(
    r'(?P<key>T\d?|B):\s*(?P<temp>-?\d+(?:\.\d+)?)\s*/\s*(?P<target>-?\d+(?:\.\d+)?)')
_DUTY_RE = re.compile(r'(?P<key>@\d?|B@):\s*(?P<pwm>\d+)')


class SerialTransport:
    """pyserial wrapper; imported lazily so the package loads without it."""

    def __init__(self, port: str, baud: int, timeout: float = 0.05):
        import serial  # noqa: WPS433 — optional dependency

        self._ser = serial.Serial(port, baudrate=baud, timeout=timeout, write_timeout=1.0)
        self._buf = b''

    def write_line(self, line: str) -> None:
        self._ser.write((line + '\n').encode('ascii'))

    def read_lines(self) -> list[str]:
        """Every complete line available now, without blocking."""
        n = self._ser.in_waiting
        if n:
            self._buf += self._ser.read(n)
        lines = []
        while b'\n' in self._buf:
            raw, self._buf = self._buf.split(b'\n', 1)
            lines.append(raw.decode('ascii', errors='replace').strip())
        return lines

    def close(self) -> None:
        self._ser.close()


class GcodeSerialDriver(ExtruderDriver):
    has_heaters = True
    has_temperature_feedback = True
    has_fan = True
    has_reverse = True

    def __init__(
        self,
        zones: int,
        port: str = '/dev/ttyACM0',
        baud: int = 250000,
        firmware: str = 'marlin',
        zone_heaters: Optional[list[str]] = None,   # ['T0', 'T1'] or ['T0', 'bed']
        e_mm_per_mm3: float = 1.0,
        chunk_s: float = 0.2,
        lookahead_s: float = 0.6,
        max_pending: int = 8,          # board planner slots we may fill
        temp_report_s: float = 1.0,
        min_extrusion_temperature: float = 0.0,
        transport=None,
        **_ignored,
    ):
        self.n = zones
        self.port, self.baud, self.firmware = port, int(baud), firmware
        self.zone_heaters = list(zone_heaters or [f'T{i}' for i in range(zones)])
        if len(self.zone_heaters) != zones:
            raise ValueError('zone_heaters must have one entry per zone')
        self.e_mm_per_mm3 = float(e_mm_per_mm3)
        self.chunk_s = float(chunk_s)
        self.lookahead_s = float(lookahead_s)
        self.max_pending = int(max_pending)
        self.temp_report_s = float(temp_report_s)
        self.min_extrusion_temperature = float(min_extrusion_temperature)
        self._tr = transport
        self._pending = 0                 # commands sent, not yet acked
        self._queue: deque[str] = deque()  # commands waiting for a slot
        self._flow = 0.0
        self._queued_until = 0.0          # board time covered by sent chunks
        self._temps = [0.0] * zones
        self._targets = [0.0] * zones
        self._duty = [0.0] * zones
        self._fan = 0.0
        self._last_report = 0.0
        self._last_poll = 0.0
        self._error = ''
        self._opened = False

    # ── lifecycle ────────────────────────────────────────────────────────
    def connect(self) -> None:
        if self._tr is None:
            self._tr = SerialTransport(self.port, self.baud)
        # Marlin resets on connect and prints a banner; give it a moment,
        # then drop whatever arrived.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if any('start' in ln or 'ok' in ln for ln in self._tr.read_lines()):
                break
            time.sleep(0.05)
        self._tr.read_lines()
        self._pending = 0
        self._send_now('M110 N0')            # reset line numbers
        self._send_now('M83')                # relative extrusion
        if self.min_extrusion_temperature > 0:
            self._send_now(f'M302 S{self.min_extrusion_temperature:.0f}')
        if self.firmware == 'marlin':
            self._send_now(f'M155 S{max(1, int(self.temp_report_s))}')  # auto temp report
        self._opened = True

    def close(self) -> None:
        if self._tr is None:
            return
        try:
            self._send_now('M107')
            for i in range(self.n):
                self.set_temperature(i, 0.0)
            self._flush_queue(force=True)
        finally:
            self._tr.close()
            self._opened = False

    # ── setpoints ────────────────────────────────────────────────────────
    def set_flow(self, mm3_s: float) -> None:
        self._flow = mm3_s
        if mm3_s == 0.0:
            # Drop chunks not yet sent; the board finishes what it has
            # (≤ lookahead_s of material).
            self._queue = deque(c for c in self._queue if not c.startswith('G1 E'))

    def set_temperature(self, zone: int, target_c: float) -> None:
        self._targets[zone] = target_c
        h = self.zone_heaters[zone]
        if h == 'bed':
            self._enqueue(f'M140 S{target_c:.0f}')
        else:
            idx = h[1:] or '0'
            self._enqueue(f'M104 T{idx} S{target_c:.0f}')

    def set_fan(self, percent: float) -> None:
        self._fan = max(0.0, min(100.0, percent))
        pwm = int(round(self._fan / 100.0 * 255.0))
        self._enqueue('M107' if self._fan <= 0 else f'M106 S{pwm}')

    def emergency_stop(self) -> None:
        self._flow = 0.0
        self._queue.clear()
        self._targets = [0.0] * self.n
        if self._tr is not None:
            try:
                self._tr.write_line('M112')
            except Exception as e:  # noqa: BLE001
                self._error = f'M112 failed: {e}'

    # ── periodic ─────────────────────────────────────────────────────────
    def tick(self, now: float) -> None:
        if self._tr is None:
            return
        try:
            for line in self._tr.read_lines():
                self._handle_line(line, now)
        except Exception as e:  # noqa: BLE001
            self._error = f'serial read failed: {e}'
            return
        if self.firmware != 'marlin' and now - self._last_poll >= self.temp_report_s:
            self._last_poll = now
            self._enqueue('M105')
        self._stream_flow(now)
        self._flush_queue()

    def read(self) -> DriverReading:
        if self._error:
            return DriverReading(ok=False, error=self._error)
        stamp = self._last_report if self._last_report else time.monotonic()
        return DriverReading(
            stamp=stamp,
            zone_temperatures=list(self._temps),
            zone_targets=list(self._targets),
            zone_heater_duty=list(self._duty),
            flow_mm3_s=self._flow,
            fan_percent=self._fan,
        )

    def describe(self) -> str:
        return f'{self.firmware} board on {self.port} @ {self.baud}, {self.n} zone(s)'

    # ── internals ────────────────────────────────────────────────────────
    def _stream_flow(self, now: float) -> None:
        if self._flow == 0.0:
            self._queued_until = min(self._queued_until, now)
            return
        if self._queued_until < now:
            self._queued_until = now
        while self._queued_until - now < self.lookahead_s:
            e_mm = self._flow * self.e_mm_per_mm3 * self.chunk_s
            feed = abs(self._flow) * self.e_mm_per_mm3 * 60.0
            self._queue.append(f'G1 E{e_mm:.4f} F{feed:.1f}')
            self._queued_until += self.chunk_s

    def _enqueue(self, cmd: str) -> None:
        self._queue.append(cmd)

    def _flush_queue(self, force: bool = False) -> None:
        while self._queue and (force or self._pending < self.max_pending):
            self._send_now(self._queue.popleft())

    def _send_now(self, cmd: str) -> None:
        try:
            self._tr.write_line(cmd)
            self._pending += 1
        except Exception as e:  # noqa: BLE001
            self._error = f'serial write failed: {e}'

    def _handle_line(self, line: str, now: float) -> None:
        if not line:
            return
        if line.startswith('ok'):
            self._pending = max(0, self._pending - 1)
        if 'T:' in line or 'T0:' in line or 'B:' in line:
            self._parse_temps(line, now)
        low = line.lower()
        if low.startswith(('error', '!!')) or 'halted' in low or 'kill' in low:
            self._error = line
        elif 'resend' in low:
            self._pending = max(0, self._pending - 1)

    def _parse_temps(self, line: str, now: float) -> None:
        temps = {m.group('key'): (float(m.group('temp')), float(m.group('target')))
                 for m in _TEMP_RE.finditer(line)}
        duty = {m.group('key'): int(m.group('pwm')) for m in _DUTY_RE.finditer(line)}
        if not temps:
            return
        for i, h in enumerate(self.zone_heaters):
            if h == 'bed':
                keys, dkeys = ['B'], ['B@']
            else:
                idx = h[1:] or '0'
                keys = [f'T{idx}'] + (['T'] if idx == '0' else [])
                dkeys = [f'@{idx}'] + (['@'] if idx == '0' else [])
            for k in keys:
                if k in temps:
                    self._temps[i] = temps[k][0]
                    break
            for k in dkeys:
                if k in duty:
                    self._duty[i] = duty[k] / 127.0 if duty[k] <= 127 else duty[k] / 255.0
                    break
        self._last_report = now
