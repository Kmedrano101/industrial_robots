"""ExtruderCore with the mock driver and a fake clock: state machine,
interlocks, pulses and fault handling, without ROS."""

import pytest

from ur_3d_printer.extruder.core import (
    EXTRUDING, FAULT, HEATING, OFF, PRIMING, PURGING, RETRACTING, ExtruderCore,
)
from ur_3d_printer.extruder.drivers.mock import MockExtruderDriver
from ur_3d_printer.extruder.profile import load_profile


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make(profile='mahor_v5_m12_pro', **drv):
    p = load_profile(profile)
    clock = Clock()
    d = MockExtruderDriver(zones=len(p.thermal.zones), clock=clock,
                           heating_rate_c_s=20.0, **drv)
    core = ExtruderCore(p, d)
    core.connect()
    core.tick(clock.t)
    return core, d, clock


def run(core, clock, seconds, dt=0.05):
    st = None
    n = int(round(seconds / dt))
    for _ in range(n):
        clock.t += dt
        st = core.tick(clock.t)
    return st


def heat(core, clock, target=210.0):
    """Reach the target and sit through the profile's heat soak."""
    core.set_temperature(-1, target)
    st = run(core, clock, 60.0)
    assert st.at_temperature, st
    st = run(core, clock, core.profile.thermal.heatsoak_s + 5.0)
    assert st.ready, st
    return st


# ── thermal ─────────────────────────────────────────────────────────────


def test_starts_off_cold_and_not_ready():
    core, d, clock = make()
    st = core.status()
    assert st.state == OFF and not st.ready and not st.heaters_on
    assert len(st.zone_temperatures) == 2


def test_heating_then_at_temperature_then_heatsoak():
    core, d, clock = make()
    ok, msg = core.set_temperature(-1, 210.0)
    assert ok and 'nozzle, barrel' in msg
    st = run(core, clock, 1.0)
    assert st.state == HEATING and st.heaters_on and not st.ready
    st = run(core, clock, 60.0)
    assert st.at_temperature
    assert not st.ready, 'heat soak (120 s) not elapsed yet'
    assert st.state == HEATING
    st = run(core, clock, 125.0)
    assert st.ready and st.state == OFF


def test_target_above_zone_max_is_rejected():
    core, d, clock = make()
    ok, msg = core.set_temperature(0, 350.0)
    assert not ok and 'above maximum' in msg
    assert core.status().zone_targets == [0.0, 0.0]


def test_single_zone_and_off():
    core, d, clock = make()
    assert core.set_temperature(1, 200.0)[0]
    assert core.status().zone_targets == [0.0, 200.0]
    ok, msg = core.set_temperature(1, 0.0)
    assert ok and 'off' in msg
    assert d.targets == [0.0, 0.0]


def test_zone_out_of_range():
    core, d, clock = make()
    assert not core.set_temperature(2, 100.0)[0]


def test_paste_profile_has_no_heater_control():
    core, d, clock = make('paste_syringe')
    ok, msg = core.set_temperature(0, 100.0)
    assert not ok and 'no controllable heater' in msg
    # No thermal interlock either: the motor may run.
    assert core.set_flow(20.0)[0]
    assert core.status().state == EXTRUDING


# ── cold-extrusion interlock ───────────────────────────────────────────────


def test_cold_extrusion_is_blocked():
    core, d, clock = make()
    ok, msg = core.set_flow(30.0)
    assert not ok and 'cold extrusion blocked' in msg and '170' in msg
    assert d.flow_cmd == 0.0
    assert not core.prime()[0]
    assert not core.purge()[0]


def test_retract_when_cold_stops_and_refuses():
    core, d, clock = make('generic_fdm')
    ok, msg = core.retract()
    assert not ok and 'cold' in msg


def test_extrusion_allowed_once_hot():
    core, d, clock = make()
    heat(core, clock)
    ok, msg = core.set_flow(30.0)
    assert ok and '30.00' in msg
    st = run(core, clock, 2.0)
    assert st.state == EXTRUDING
    assert st.target_flow_mm3_s == 30.0
    assert st.flow_mm3_s == pytest.approx(30.0, abs=0.5)


# ── flow envelope ──────────────────────────────────────────────────────────


def test_flow_is_clamped_to_max_and_min():
    core, d, clock = make()
    heat(core, clock)
    core.set_flow(500.0)
    assert core.status().target_flow_mm3_s == 115.0
    core.set_flow(0.5)
    assert core.status().target_flow_mm3_s == 2.0


def test_flow_ramps_with_the_slew_limit():
    core, d, clock = make()           # slew 150 mm³/s²
    heat(core, clock)
    core.set_flow(100.0)
    assert d.flow_cmd == 0.0, 'ramped, not stepped'
    run(core, clock, 0.2)
    assert d.flow_cmd == pytest.approx(30.0, abs=1.0)
    run(core, clock, 1.0)
    assert d.flow_cmd == pytest.approx(100.0)


def test_stop_is_immediate():
    core, d, clock = make()
    heat(core, clock)
    core.set_flow(100.0)
    run(core, clock, 2.0)
    core.stop()
    assert d.flow_cmd == 0.0
    assert core.status().state == OFF


def test_unlimited_slew_steps_immediately():
    core, d, clock = make('paste_syringe')
    core.profile.flow.slew_mm3_s2 = 1e9
    core.set_flow(20.0)
    assert d.flow_cmd == 20.0


# ── pulses ─────────────────────────────────────────────────────────────────


def test_prime_then_continue_at_print_flow():
    """print_node sends enable+prime at the start of every extrusion
    segment; the old controller only primed and never extruded."""
    core, d, clock = make()
    heat(core, clock)
    ok, msg = core.prime(then_flow=40.0)
    assert ok and 'priming 6.0' in msg
    assert core.status().state == PRIMING
    assert d.flow_cmd == 30.0                    # prime rate, no ramp
    run(core, clock, 0.25)                       # 6 mm³ / 30 mm³/s = 0.2 s
    st = core.status()
    assert st.state == EXTRUDING and st.target_flow_mm3_s == 40.0
    assert d.flow_cmd == 40.0


def test_prime_then_off():
    core, d, clock = make()
    heat(core, clock)
    core.prime(then_flow=0.0)
    run(core, clock, 0.3)
    assert core.status().state == OFF and d.flow_cmd == 0.0


def test_screw_extruder_retract_is_a_coast():
    core, d, clock = make()
    heat(core, clock)
    core.set_flow(40.0)
    run(core, clock, 1.0)
    ok, msg = core.retract()
    assert ok and 'coasting' in msg
    assert d.flow_cmd == 0.0 and core.status().state == OFF


def test_filament_extruder_retracts_backwards_then_resumes():
    core, d, clock = make('generic_fdm')
    heat(core, clock, 200.0)
    core.set_flow(5.0)
    run(core, clock, 1.0)
    ok, msg = core.retract(then_flow=5.0)
    assert ok and 'retracting 12.0' in msg
    assert core.status().state == RETRACTING and d.flow_cmd == -60.0
    run(core, clock, 0.25)                       # 12 / 60 = 0.2 s
    st = core.status()
    assert st.state == EXTRUDING and st.target_flow_mm3_s == 5.0
    assert d.flow_cmd > 0.0                      # ramping back up from 0


def test_purge_runs_the_profile_volume_then_stops():
    core, d, clock = make()
    assert not core.purge()[0], 'cold'
    heat(core, clock)
    ok, msg, dur = core.purge()
    assert ok and dur == pytest.approx(400.0 / 30.0)
    assert core.status().state == PURGING and d.flow_cmd == 30.0
    ok2, msg2, _ = core.purge()
    assert not ok2 and 'busy' in msg2
    run(core, clock, dur + 0.1)
    assert core.status().state == OFF and d.flow_cmd == 0.0


def test_purge_custom_volume_clamped_to_max_flow():
    core, d, clock = make()
    heat(core, clock)
    ok, msg, dur = core.purge(volume_mm3=230.0, rate_mm3_s=1000.0)
    assert ok and dur == pytest.approx(2.0)      # 230 / 115


# ── fan ────────────────────────────────────────────────────────────────────


def test_fan_auto_on_when_nozzle_warms_up():
    core, d, clock = make()
    assert d.fan == 0.0
    core.set_temperature(0, 100.0)
    run(core, clock, 20.0)
    assert d.fan == 100.0
    core.set_temperature(0, 0.0)
    run(core, clock, 600.0)                      # cools below 40 °C
    assert d.fan == 0.0


def test_manual_fan():
    core, d, clock = make()
    ok, msg = core.set_fan(150.0)
    assert ok and d.fan == 100.0
    core2, d2, _ = make('paste_syringe')
    assert not core2.set_fan(50.0)[0]


# ── faults ─────────────────────────────────────────────────────────────────


def test_thermal_runaway_dead_heater():
    core, d, clock = make()
    d.heater_broken[1] = True
    core.set_temperature(-1, 210.0)
    st = run(core, clock, 65.0)
    assert st.state == FAULT
    assert 'thermal runaway on barrel' in st.fault
    assert d.targets == [0.0, 0.0], 'heaters cut'
    assert d.commands[-1][0] in ('temp', 'estop')


def test_runaway_deviation_once_at_temperature():
    core, d, clock = make()
    heat(core, clock)
    d.heater_broken[0] = True                    # nozzle heater dies at temp
    st = run(core, clock, 200.0)
    assert st.state == FAULT and 'nozzle' in st.fault


def test_fault_blocks_commands_until_reset():
    core, d, clock = make()
    d.comms_ok = False
    st = run(core, clock, 0.2)
    assert st.state == FAULT and 'driver error' in st.fault
    assert not core.set_flow(10.0)[0]
    assert not core.set_temperature(0, 200.0)[0]
    d.comms_ok = True
    ok, _ = core.reset_fault()
    assert ok
    st = run(core, clock, 0.2)
    assert st.state == OFF and st.fault == ''
    assert core.set_temperature(0, 200.0)[0]


def test_over_temperature_latches_fault():
    core, d, clock = make()
    d.temps[0] = 320.0
    st = run(core, clock, 0.1)
    assert st.state == FAULT and 'over temperature' in st.fault


def test_emergency_stop_kills_motor_and_heaters():
    core, d, clock = make()
    heat(core, clock)
    core.set_flow(40.0)
    run(core, clock, 1.0)
    fired = []
    core.on_fault = fired.append
    core.emergency_stop()
    assert d.flow_cmd == 0.0 and d.targets == [0.0, 0.0]
    assert core.status().state == FAULT and fired == ['emergency stop']


def test_stale_reading_trips_watchdog():
    core, d, clock = make()
    run(core, clock, 1.0)
    d.clock = lambda: clock.t - 5.0              # driver reports old stamps
    st = run(core, clock, 0.2)
    assert st.state == FAULT and 'no data' in st.fault


def test_close_turns_everything_off():
    core, d, clock = make()
    heat(core, clock)
    core.set_flow(40.0)
    run(core, clock, 1.0)
    core.close()
    assert d.flow_cmd == 0.0 and d.targets == [0.0, 0.0]


def test_motor_stops_if_the_nozzle_cools_while_extruding():
    """Heaters switched off (or dead) mid-print: the screw must not keep
    turning into a solidifying melt."""
    core, d, clock = make()
    heat(core, clock)
    core.set_flow(40.0)
    run(core, clock, 1.0)
    core.heaters_off()
    st = run(core, clock, 1.0)
    assert st.state == EXTRUDING, 'still above the minimum'
    d.temps[0] = 150.0                           # below 170 - 10 hysteresis
    st = run(core, clock, 0.1)
    assert st.state == FAULT and 'cooled' in st.fault
    assert d.flow_cmd == 0.0
