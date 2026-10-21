# Cell settings

Operator-editable configuration of the printer cell, shared by every device,
persisted in the `ur-web-data` volume and applied to the ROS stack without
rebuilding images.

```
/data/settings.yaml      the document (+ change history)        written by the web backend
/data/ros_params.yaml    ROS 2 parameter overlay generated from it, loaded by ur-printer at launch
/data/restart.request    touched by POST /api/settings/restart; ur-printer relaunches its stack
```

## Groups

| Group | Keys | Applies to |
|---|---|---|
| `extruder` | `profile` (a file in `config/extruders/`), `driver` (`mock`/`gcode_serial`/`topic`/`ur_io`, `""` = profile's), `serial_port`, `serial_baud` | `extruder_controller` params |
| `bed` | `print_origin_xyz/rpy`, `bed_tilt_rx/ry`, `z_hop_enabled`, `z_hop_height`, `size_mm` (UI only) | `print_node` params |
| `robot` | `home_joints`, `tool_offset_xyz/rpy`, `bed_points` (`p1..p4`, `center`, joint poses) | `print_node` params; `/robot/home_pose`, `/robot/bed_points` |
| `motion` | `max_print_velocity`, `max_travel_velocity`, `max_acceleration`, `corner_blend_radius`, `singularity_velocity_scale` | `print_node` params |

Every value is range-checked (`backend/cell_settings.py`); a rejected patch
changes nothing and the error names the key. The factory defaults are the
package's `print_params.yaml`, the `EXTRUDER_*` variables of `.env` and the
poses measured on the ur7e cell. Once `settings.yaml` exists it wins over
`.env` for the extruder selection.

## Precedence at launch

```
print_params.yaml (image)  <  launch args (.env via compose)  <  /data/ros_params.yaml (operator)
```

The overlay is regenerated from `settings.yaml` every time the backend
starts, so a change in its shape (new fixed keys) reaches ur-printer on the
next relaunch without anyone saving. It always pins
`preferred_arm_config: none`: otherwise print_node replaces `home_joints`
with a built-in preset at start-up and the configured home is ignored.

## Live apply vs restart

| Group | Applied | How |
|---|---|---|
| `motion`, `bed`, `robot` | on save, while the printer is idle | `SetParametersAtomically` on `print_node`; its callback (`runtime_params.py`) validates and rebuilds the print frame, tool offset, home pose, velocity profile and z-hop |
| `extruder` | on restart | the driver/profile is chosen when `extruder_controller` starts |

`PUT /api/settings` (and reset / capture / calibrate) push only the
parameters whose running value differs and return `applied` and
`apply_error`. While a print runs, print_node refuses (`print in progress`):
the values stay saved and listed in `pending` until the next save or a
restart. `restart_required` compares the overlay with the parameters read
back from the running nodes, so it only stays true for what really needs a
relaunch. `POST /api/settings/restart` relaunches the stack (~25 s, drops
the robot connection; refused by the UI during a print).

## API

```
GET  /api/settings                      settings, defaults, extruder_profiles, effective (per node, null if unreachable),
                                        restart_required (null = unknown), pending, history, updated_at
PUT  /api/settings  {patch, source?}    partial document, deep-merged; 422 with the offending key on error
POST /api/settings/reset {group?}       factory defaults for one group or all
POST /api/settings/capture {target}     robot.home_joints | robot.bed_points.<name> from the live joint states
POST /api/settings/restart              relaunch the ROS stack with the current overlay
```

`POST /api/calibrate` (print origin from the current pose) also stores the
new origin in `bed.print_origin_xyz`, so it survives a restart.

## Tests

`cd workspace/ur_3d_printer_web && pytest backend/tests/test_cell_settings.py`
