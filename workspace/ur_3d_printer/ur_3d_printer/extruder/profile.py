"""Extruder profile: everything the controller needs to know about the
mounted extruder, loaded from ``config/extruders/<model>.yaml``.

A profile is pure data. It describes the hardware (zones, flow envelope,
motor, nozzle), the policies that follow from the hardware class
(screw extruders do not retract, pellets need a heat soak) and which
driver talks to the electronics. The controller core and the drivers are
written against this description, so adding an extruder is a YAML file
and, if its electronics are new, a driver.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Optional

KINDS = ('pellet_screw', 'filament', 'paste')
DRIVERS = ('mock', 'gcode_serial', 'topic', 'ur_io')


class ProfileError(ValueError):
    """The profile is missing something or contradicts itself."""


@dataclass
class ThermalZone:
    name: str
    max_temperature: float          # °C, hard limit; targets above are rejected
    heater: str = ''                # free text, e.g. "CHC 24V 80W"
    gcode_heater: str = 'T0'        # gcode_serial mapping: T0 | T1 | ... | bed


@dataclass
class Thermal:
    zones: list[ThermalZone] = field(default_factory=list)
    sensor: str = ''
    min_extrusion_temperature: float = 0.0   # cold-extrusion interlock on zone 0
    at_temperature_tolerance: float = 3.0    # °C
    heatsoak_s: float = 0.0                  # extra wait once at temperature
    # Runaway detection: while heating, the zone must rise at least
    # `runaway_min_rise` within `runaway_window_s`; once at target it must
    # not drift more than `runaway_max_deviation` for longer than the window.
    runaway_window_s: float = 60.0
    runaway_min_rise: float = 2.0
    runaway_max_deviation: float = 15.0
    # True when the driver reports real temperatures. False for drivers
    # without feedback (UR I/O with an external temperature controller):
    # the interlocks are then skipped and the state carries no temperature.
    feedback: bool = True

    @property
    def has_heaters(self) -> bool:
        return bool(self.zones)


@dataclass
class Flow:
    max_mm3_s: float
    default_mm3_s: float
    min_mm3_s: float = 0.0
    slew_mm3_s2: float = 1e9        # ramp limit on commanded flow
    lag_s: float = 0.0              # response lag of the melt path (for lead time)


@dataclass
class Motor:
    model: str = ''
    current_a: float = 0.0
    steps_per_rev: int = 200
    gear_ratio: float = 1.0
    microsteps: int = 16
    mm3_per_rev: float = 0.0        # calibrated volume per output-shaft turn; 0 = unknown


@dataclass
class Retraction:
    enabled: bool = True
    volume_mm3: float = 0.0
    rate_mm3_s: float = 0.0
    prime_volume_mm3: float = 0.0
    prime_rate_mm3_s: float = 0.0


@dataclass
class Purge:
    volume_mm3: float = 0.0
    rate_mm3_s: float = 0.0


@dataclass
class Fan:
    present: bool = False
    model: str = ''
    default_percent: float = 0.0
    # Turn the fan on automatically once zone 0 passes this temperature
    # (heat-break cooling); 0 disables the automation.
    auto_on_above: float = 0.0


@dataclass
class ExtruderProfile:
    name: str
    model: str
    kind: str
    nozzle_diameter_mm: float
    flow: Flow
    thermal: Thermal = field(default_factory=Thermal)
    motor: Motor = field(default_factory=Motor)
    retraction: Retraction = field(default_factory=Retraction)
    purge: Purge = field(default_factory=Purge)
    fan: Fan = field(default_factory=Fan)
    driver: str = 'mock'
    driver_params: dict[str, Any] = field(default_factory=dict)
    notes: str = ''
    vendor_url: str = ''

    # ── derived ──────────────────────────────────────────────────────────
    @property
    def has_retract(self) -> bool:
        return self.retraction.enabled and self.retraction.volume_mm3 > 0

    @property
    def has_purge(self) -> bool:
        return self.purge.volume_mm3 > 0

    @property
    def zone_names(self) -> list[str]:
        return [z.name for z in self.thermal.zones]

    def zone_index(self, name_or_index) -> int:
        if isinstance(name_or_index, int):
            if not 0 <= name_or_index < len(self.thermal.zones):
                raise ProfileError(f'zone {name_or_index} out of range')
            return name_or_index
        for i, z in enumerate(self.thermal.zones):
            if z.name == name_or_index:
                return i
        raise ProfileError(f'unknown zone {name_or_index!r}')

    # ── construction ─────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> 'ExtruderProfile':
        d = raw.get('extruder', raw)
        for key in ('name', 'model', 'kind', 'nozzle_diameter_mm', 'flow'):
            if key not in d:
                raise ProfileError(f'profile missing required key {key!r}')
        if d['kind'] not in KINDS:
            raise ProfileError(f'kind must be one of {KINDS}, got {d["kind"]!r}')

        f = d['flow']
        if 'max_mm3_s' not in f:
            raise ProfileError('flow.max_mm3_s is required')
        flow = Flow(
            max_mm3_s=float(f['max_mm3_s']),
            default_mm3_s=float(f.get('default_mm3_s', f['max_mm3_s'])),
            min_mm3_s=float(f.get('min_mm3_s', 0.0)),
            slew_mm3_s2=float(f.get('slew_mm3_s2', 1e9)),
            lag_s=float(f.get('lag_s', 0.0)),
        )
        if flow.max_mm3_s <= 0:
            raise ProfileError('flow.max_mm3_s must be > 0')
        if not 0 < flow.default_mm3_s <= flow.max_mm3_s:
            raise ProfileError('flow.default_mm3_s must be in (0, max_mm3_s]')

        t = d.get('thermal', {}) or {}
        zones = [
            ThermalZone(
                name=str(z['name']),
                max_temperature=float(z['max_temperature']),
                heater=str(z.get('heater', '')),
                gcode_heater=str(z.get('gcode_heater', f'T{i}')),
            )
            for i, z in enumerate(t.get('zones', []) or [])
        ]
        thermal = Thermal(
            zones=zones,
            sensor=str(t.get('sensor', '')),
            min_extrusion_temperature=float(t.get('min_extrusion_temperature', 0.0)),
            at_temperature_tolerance=float(t.get('at_temperature_tolerance', 3.0)),
            heatsoak_s=float(t.get('heatsoak_s', 0.0)),
            runaway_window_s=float(t.get('runaway_window_s', 60.0)),
            runaway_min_rise=float(t.get('runaway_min_rise', 2.0)),
            runaway_max_deviation=float(t.get('runaway_max_deviation', 15.0)),
            feedback=bool(t.get('feedback', True)),
        )
        if thermal.min_extrusion_temperature > 0 and not zones:
            raise ProfileError('min_extrusion_temperature set but no thermal zones')
        for z in zones:
            if thermal.min_extrusion_temperature > z.max_temperature:
                raise ProfileError(
                    f'min_extrusion_temperature above zone {z.name} max_temperature')

        m = d.get('motor', {}) or {}
        motor = Motor(
            model=str(m.get('model', '')),
            current_a=float(m.get('current_a', 0.0)),
            steps_per_rev=int(m.get('steps_per_rev', 200)),
            gear_ratio=float(m.get('gear_ratio', 1.0)),
            microsteps=int(m.get('microsteps', 16)),
            mm3_per_rev=float(m.get('mm3_per_rev', 0.0)),
        )

        r = d.get('retraction', {}) or {}
        retraction = Retraction(
            enabled=bool(r.get('enabled', True)),
            volume_mm3=float(r.get('volume_mm3', 0.0)),
            rate_mm3_s=float(r.get('rate_mm3_s', 0.0)),
            prime_volume_mm3=float(r.get('prime_volume_mm3', 0.0)),
            prime_rate_mm3_s=float(r.get('prime_rate_mm3_s', 0.0)),
        )
        if retraction.enabled and retraction.volume_mm3 > 0 and retraction.rate_mm3_s <= 0:
            raise ProfileError('retraction.rate_mm3_s must be > 0 when retraction is enabled')
        if retraction.prime_volume_mm3 > 0 and retraction.prime_rate_mm3_s <= 0:
            raise ProfileError('retraction.prime_rate_mm3_s must be > 0 when priming')

        p = d.get('purge', {}) or {}
        purge = Purge(
            volume_mm3=float(p.get('volume_mm3', 0.0)),
            rate_mm3_s=float(p.get('rate_mm3_s', 0.0)),
        )
        if purge.volume_mm3 > 0 and purge.rate_mm3_s <= 0:
            raise ProfileError('purge.rate_mm3_s must be > 0 when purge.volume_mm3 is set')

        fn = d.get('fan', {}) or {}
        fan = Fan(
            present=bool(fn.get('present', False)),
            model=str(fn.get('model', '')),
            default_percent=float(fn.get('default_percent', 0.0)),
            auto_on_above=float(fn.get('auto_on_above', 0.0)),
        )

        drv = d.get('driver', {}) or {}
        if isinstance(drv, str):
            drv = {'type': drv}
        driver = str(drv.get('type', 'mock'))
        if driver not in DRIVERS:
            raise ProfileError(f'driver.type must be one of {DRIVERS}, got {driver!r}')
        driver_params = {k: v for k, v in drv.items() if k != 'type'}

        return cls(
            name=str(d['name']),
            model=str(d['model']),
            kind=str(d['kind']),
            nozzle_diameter_mm=float(d['nozzle_diameter_mm']),
            flow=flow,
            thermal=thermal,
            motor=motor,
            retraction=retraction,
            purge=purge,
            fan=fan,
            driver=driver,
            driver_params=driver_params,
            notes=str(d.get('notes', '')),
            vendor_url=str(d.get('vendor_url', '')),
        )

    @classmethod
    def from_yaml(cls, path: str) -> 'ExtruderProfile':
        import yaml

        with open(path, 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f) or {}
        try:
            return cls.from_dict(raw)
        except ProfileError as e:
            raise ProfileError(f'{path}: {e}') from e


def resolve_profile_path(name_or_path: str, search_dirs: list[str]) -> str:
    """Turn ``mahor_v5_m12_pro`` or an explicit path into a file path."""
    if os.path.isfile(name_or_path):
        return name_or_path
    base = name_or_path if name_or_path.endswith(('.yaml', '.yml')) else name_or_path + '.yaml'
    for d in search_dirs:
        candidate = os.path.join(d, base)
        if os.path.isfile(candidate):
            return candidate
    raise ProfileError(
        f'extruder profile {name_or_path!r} not found in {search_dirs}')


def load_profile(name_or_path: str, search_dirs: Optional[list[str]] = None) -> ExtruderProfile:
    dirs = list(search_dirs or [])
    dirs.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'config', 'extruders'))
    return ExtruderProfile.from_yaml(resolve_profile_path(name_or_path, dirs))
