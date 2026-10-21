"""Drivers that run without ROS: the G-code serial driver against a fake
Marlin board, and the factory."""

import pytest

from ur_3d_printer.extruder.drivers import make_driver
from ur_3d_printer.extruder.drivers.gcode_serial import GcodeSerialDriver
from ur_3d_printer.extruder.drivers.mock import MockExtruderDriver
from ur_3d_printer.extruder.profile import load_profile


class FakeMarlin:
    """Enough of Marlin's serial behaviour: acks every line, keeps the
    heater targets, reports temperatures on M105/M155, counts E moves."""

    def __init__(self):
        self.received = []
        self.outbox = ['start', 'echo: Marlin 2.1.2']
        self.targets = {'T0': 0.0, 'T1': 0.0, 'B': 0.0}
        self.temps = {'T0': 23.1, 'T1': 22.8, 'B': 22.0}
        self.e_total = 0.0
        self.fan = 0
        self.closed = False
        self.relative_e = False
        self.fail_writes = False

    def write_line(self, line):
        if self.fail_writes:
            raise OSError('device disconnected')
        self.received.append(line)
        cmd = line.split()[0]
        if cmd == 'M104':
            tool = next((p[1:] for p in line.split() if p.startswith('T')), '0')
            s = float(next(p[1:] for p in line.split() if p.startswith('S')))
            self.targets[f'T{tool}'] = s
        elif cmd == 'M140':
            self.targets['B'] = float(line.split('S')[1])
        elif cmd == 'M106':
            self.fan = int(line.split('S')[1])
        elif cmd == 'M107':
            self.fan = 0
        elif cmd == 'M83':
            self.relative_e = True
        elif cmd == 'G1':
            e = float(next(p[1:] for p in line.split() if p.startswith('E')))
            self.e_total += e
        elif cmd == 'M105':
            self.outbox.append(self.report())
            return
        self.outbox.append('ok')

    def report(self):
        return (f"ok T:{self.temps['T0']:.1f} /{self.targets['T0']:.1f} "
                f"B:{self.temps['B']:.1f} /{self.targets['B']:.1f} "
                f"T0:{self.temps['T0']:.1f} /{self.targets['T0']:.1f} "
                f"T1:{self.temps['T1']:.1f} /{self.targets['T1']:.1f} "
                f"@:64 B@:0 @0:64 @1:0")

    def read_lines(self):
        out, self.outbox = self.outbox, []
        return out

    def close(self):
        self.closed = True


@pytest.fixture
def board():
    return FakeMarlin()


@pytest.fixture
def driver(board):
    d = GcodeSerialDriver(zones=2, zone_heaters=['T0', 'T1'], chunk_s=0.2,
                          lookahead_s=0.6, max_pending=4, transport=board)
    d.connect()
    return d


def test_open_configures_the_board(board, driver):
    assert board.received[:3] == ['M110 N0', 'M83', 'M155 S1']
    assert board.relative_e


def test_heater_commands_map_zones_to_tools(board, driver):
    driver.set_temperature(0, 210.0)
    driver.set_temperature(1, 190.0)
    driver.tick(0.0)
    assert 'M104 T0 S210' in board.received and 'M104 T1 S190' in board.received
    assert board.targets['T0'] == 210.0 and board.targets['T1'] == 190.0


def test_bed_mapped_zone_uses_m140(board):
    d = GcodeSerialDriver(zones=2, zone_heaters=['T0', 'bed'], transport=board)
    d.connect()
    d.set_temperature(1, 60.0)
    d.tick(0.0)
    assert 'M140 S60' in board.received


def test_temperature_report_is_parsed_per_zone(board, driver):
    board.temps['T0'], board.temps['T1'] = 205.5, 180.2
    board.outbox.append(board.report())
    driver.tick(1.0)
    r = driver.read()
    assert r.zone_temperatures == [205.5, 180.2]
    assert r.zone_heater_duty[0] == pytest.approx(64 / 127)
    assert r.stamp == 1.0 and r.ok


def test_flow_streams_relative_e_moves_ahead_of_time(board, driver):
    driver.set_flow(30.0)
    driver.tick(0.0)
    moves = [ln for ln in board.received if ln.startswith('G1 E')]
    assert len(moves) == 3, 'lookahead 0.6 s / chunk 0.2 s'
    assert moves[0] == 'G1 E6.0000 F1800.0'       # 30 mm³/s × 0.2 s, 30 mm/s
    # 0.4 s later two chunks have elapsed → two more are queued.
    driver.tick(0.4)
    moves = [ln for ln in board.received if ln.startswith('G1 E')]
    assert len(moves) == 5
    assert board.e_total == pytest.approx(30.0)


def test_backpressure_waits_for_acks(board, driver):
    driver.tick(0.0)             # consume the acks of the set-up commands
    orig = board.write_line

    def silent(line):            # board stops acking
        board.received.append(line)
    board.write_line = silent
    driver.set_flow(30.0)
    driver.tick(0.0)
    driver.tick(1.0)
    driver.tick(2.0)
    moves = [ln for ln in board.received if ln.startswith('G1 E')]
    assert len(moves) == 4, 'max_pending slots, nothing more until an ok'
    board.write_line = orig
    board.outbox.extend(['ok'] * 4)
    driver.tick(2.1)
    moves = [ln for ln in board.received if ln.startswith('G1 E')]
    assert len(moves) > 4


def test_stop_drops_unsent_chunks_and_sends_nothing_more(board, driver):
    driver.set_flow(30.0)
    driver.tick(0.0)
    n = len(board.received)
    driver.set_flow(0.0)
    driver.tick(0.1)
    driver.tick(5.0)
    assert len(board.received) == n


def test_reverse_flow_sends_negative_e(board, driver):
    driver.set_flow(-60.0)
    driver.tick(0.0)
    move = next(ln for ln in board.received if ln.startswith('G1 E'))
    assert move.startswith('G1 E-12.0000 F3600.0')


def test_e_calibration_scales_moves(board):
    d = GcodeSerialDriver(zones=1, e_mm_per_mm3=0.4157, chunk_s=0.5, lookahead_s=0.5,
                          transport=board)
    d.connect()
    d.set_flow(10.0)
    d.tick(0.0)
    move = next(ln for ln in board.received if ln.startswith('G1 E'))
    assert move == 'G1 E2.0785 F249.4'


def test_fan_and_estop(board, driver):
    driver.set_fan(50.0)
    driver.tick(0.0)
    assert 'M106 S128' in board.received and board.fan == 128
    driver.set_fan(0.0)
    driver.tick(0.1)
    assert board.received[-1] == 'M107'
    driver.set_flow(30.0)
    driver.emergency_stop()
    assert board.received[-1] == 'M112'
    driver.tick(1.0)
    assert not any(ln.startswith('G1 E') for ln in board.received[-3:])


def test_board_error_lines_become_driver_faults(board, driver):
    board.outbox.append('Error:Heating failed, system stopped! Heater_ID: 0')
    driver.tick(0.0)
    r = driver.read()
    assert not r.ok and 'Heating failed' in r.error


def test_write_failure_becomes_driver_fault(board, driver):
    board.fail_writes = True
    driver.set_flow(10.0)
    driver.tick(0.0)
    assert not driver.read().ok


def test_close_turns_heaters_and_fan_off(board, driver):
    driver.set_temperature(0, 200.0)
    driver.tick(0.0)
    driver.close()
    assert board.closed
    assert board.targets['T0'] == 0.0 and board.fan == 0


def test_min_extrusion_temperature_is_passed_to_the_board(board):
    d = GcodeSerialDriver(zones=1, min_extrusion_temperature=170.0, transport=board)
    d.connect()
    assert 'M302 S170' in board.received


def test_non_marlin_firmware_polls_m105(board):
    d = GcodeSerialDriver(zones=1, firmware='klipper', temp_report_s=1.0, transport=board)
    d.connect()
    assert 'M155 S1' not in board.received
    d.tick(1.0)
    d.tick(1.5)
    d.tick(2.0)
    assert board.received.count('M105') == 2


# ── factory ────────────────────────────────────────────────────────────────


def test_factory_builds_profile_driver_with_overrides(board):
    p = load_profile('mahor_v5_m12_pro')
    d = make_driver(p, overrides={'transport': board, 'port': '/dev/ttyUSB3', 'baud': ''})
    assert isinstance(d, GcodeSerialDriver)
    assert d.port == '/dev/ttyUSB3' and d.baud == 250000
    assert d.zone_heaters == ['T0', 'T1']
    assert d.min_extrusion_temperature == 170.0


def test_factory_mock_override_and_ros_drivers_need_a_node():
    p = load_profile('mahor_v5_m12_pro')
    assert isinstance(make_driver(p, 'mock'), MockExtruderDriver)
    with pytest.raises(ValueError, match='needs a ROS node'):
        make_driver(p, 'topic')
    with pytest.raises(ValueError, match='unknown extruder driver'):
        make_driver(p, 'canbus')
