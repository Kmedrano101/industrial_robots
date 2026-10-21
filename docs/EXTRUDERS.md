# Extruders

The extruder subsystem (`workspace/ur_3d_printer/ur_3d_printer/extruder/`) is
split in three layers so that a new extruder is a YAML file and, only when
its electronics are new, a driver:

```
config/extruders/<model>.yaml   what the extruder IS      (profile)
extruder/core.py                what it is ALLOWED to do  (state machine + interlocks)
extruder/drivers/<type>.py      how to TALK to it         (mock, gcode_serial, topic, ur_io)
extruder_controller.py          ROS 2 node: services + topics around the core
```

## Selecting an extruder

| Where | Setting |
|---|---|
| `.env` | `EXTRUDER_PROFILE=mahor_v5_m12_pro`, `EXTRUDER_DRIVER=mock`, `EXTRUDER_SERIAL_PORT=/dev/ttyACM0` |
| launch | `extruder_profile:=…  extruder_driver:=…  extruder_serial_port:=…` |
| node params | `profile`, `driver`, `serial_port`, `serial_baud`, `publish_rate` |

`EXTRUDER_DRIVER=mock` simulates the heaters and the screw (the default of
the Docker stack, so the UI behaves as with real hardware). For a real board
set `gcode_serial`, map the USB device in `docker-compose.yml`
(`devices:` block of `ur-printer`) and set the port.

## Profiles shipped

| Profile | Kind | Zones | Driver | Notes |
|---|---|---|---|---|
| `mahor_v5_m12_pro` | pellet screw | nozzle, barrel | gcode_serial | Mahor V5 M12 PRO, >115 mm³/s, no retraction (coast + re-prime) |
| `generic_fdm` | filament | hotend | gcode_serial | 1.75 mm hotend, 12 mm³ retract |
| `paste_syringe` | paste | none | ur_io | unheated, UR DO/AO outputs |

A profile declares: `flow` (max/default/min, slew ramp, lag), `thermal`
(zones with max temperature and the board heater they map to, cold-extrusion
minimum, tolerance, heat soak, runaway limits, whether there is feedback),
`fan`, `retraction` (volume/rate, prime volume/rate), `purge`, `motor`
(informative + calibration) and `driver` (type + params). Validation runs at
load: a contradictory profile refuses to start with a message naming the key.

## Interlocks (core)

* **Cold extrusion** — the motor never turns while zone 0 is below
  `min_extrusion_temperature`. A pellet screw turned cold strips its gearbox.
* **Maximum temperature** — targets above a zone's maximum are rejected;
  readings above it latch a fault.
* **Thermal runaway** — a heating zone that does not rise ≥ `runaway_min_rise`
  within `runaway_window_s`, or a zone at target that drifts more than
  `runaway_max_deviation` for that long, latches a fault.
* **Driver watchdog** — a failed or stale reading latches a fault.

A fault cuts the motor and every heater and stays latched until
`~/reset_fault`. Drivers without temperature feedback (`ur_io`, `topic`
without a temperature publisher) run with the thermal interlocks off and the
node logs a warning: keep them on the external temperature controller.

## ROS interface

```
/extruder_controller/set_extruder      SetExtruder             enable / rate (m³/s) / retract / prime   (print_node contract)
/extruder_controller/set_temperature   SetExtruderTemperature  zone (-1 = all), target °C
/extruder_controller/set_fan           SetExtruderFan          percent
/extruder_controller/purge             PurgeExtruder           volume_mm3, rate_mm3_s (0 = profile defaults)
/extruder_controller/reset_fault       std_srvs/Trigger
/extruder_controller/heaters_off       std_srvs/Trigger
/extruder_controller/extruder_state    ExtruderState           50 Hz: state, flow, zones, fan, ready, fault
/extruder_controller/extruder_info     ExtruderInfo            latched: capabilities and limits of the mounted extruder
```

`SetExtruder` semantics: `enable+prime` primes then continues at `rate`
(the previous controller only primed and never extruded); `retract` on a
screw extruder is a coast (stop) reported as success so a print carries on.

## Drivers

* **mock** — first-order thermal model per zone, flow with a time constant;
  test hooks for a dead heater and comms loss.
* **gcode_serial** — Marlin/Klipper/RRF board over USB. Heaters `M104 Tn`
  (or `M140` for a zone mapped to `bed`), temperatures from `M155` auto-report
  (Marlin) or polled `M105`; continuous flow streamed as relative `G1 E…`
  chunks kept `lookahead_s` ahead with ack back-pressure; `M106/M107`;
  `M112`. The board's E axis is calibrated in mm³ (`e_mm_per_mm3`).
* **topic** — Float64 flow command (m³/s, legacy units), Float64MultiArray
  temperature targets and readings, for Arduino/micro-ROS bridges.
* **ur_io** — UR digital/analog outputs through `io_and_status_controller/set_io`
  for externally driven motors; no thermal path.

## 3D model

`workspace/ur_3d_printer/urdf/meshes/mahor_v5_pro.stl` (ROS, RViz and the
`pellet` option of the cell URDF: `EXTRUDER_TYPE=pellet`) and
`workspace/ur_3d_printer_web/frontend/public/meshes/extruders/mahor_v5_pro.stl`
(web viewer) are the vendor's "V5 PRO CAD" STEP converted with FreeCAD and
oriented for the tool frame: motor back face at z = 0 on the flange, nozzle
tip on +Z at 0.179 m, metres, 36k triangles. The viewer picks the mesh from
the `model` reported in `extruder_info` (`EXTRUDER_MESHES` in
`RobotModel.tsx`); the ROS URDF puts `nozzle_tcp` at `tool_length`, which
has to match `tool_offset_xyz` in `print_params.yaml` (add the thickness of
the flange adapter plate to both).

To regenerate from a new STEP (snap FreeCAD cannot read /tmp, hence the
home directory):

```bash
cp model.stp ~/snap/freecad/common/ && freecad.cmd step2stl.py ~/snap/freecad/common/model.stp out.stl
# then orient/scale with trimesh (rotate 180° about X, motor face to z=0, ×0.001)
```

## Adding an extruder

1. Copy the closest profile in `config/extruders/`, change the numbers,
   keep the keys. Load it in a Python shell to validate:
   `from ur_3d_printer.extruder import load_profile; load_profile('/path.yaml')`.
2. If the electronics are new, subclass `ExtruderDriver` (`set_flow`,
   `set_temperature`, `set_fan`, `read`, optionally `tick`) and register it
   in `drivers/__init__.py`.
3. Mind the geometry: tool length in the URDF and `tool_offset_xyz` in
   `print_params.yaml`, `extruder_radius` for the collision checker.

## Tests

```bash
cd workspace/ur_3d_printer && python3 -m pytest test/test_extruder_*.py   # no ROS needed
```
