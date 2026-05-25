# ROS2 Interfaces

All custom message, service, and action definitions are in the `msg/`, `srv/`, and `action/` directories of the `ur_3d_printer` package.

## Messages

### PrintState.msg

Published by `print_node` on `~/state` at `publish_rate` Hz.

```
std_msgs/Header header
uint8 state
uint8 IDLE=0
uint8 LOADING_GCODE=1
uint8 VALIDATING=2
uint8 HOMING=3
uint8 CALIBRATING=4
uint8 PRINTING=5
uint8 TRAVEL_MOVE=6
uint8 LAYER_CHANGE=7
uint8 COMPLETED=8
uint8 PAUSED=9
uint8 CANCELLING=10
uint8 ERROR=11
string state_name
string error_message
```

| Field | Type | Description |
|-------|------|-------------|
| `header` | `Header` | Timestamp and frame |
| `state` | `uint8` | Numeric state (use constants) |
| `state_name` | `string` | Human-readable state name (e.g., `"PRINTING"`) |
| `error_message` | `string` | Error details when `state == ERROR` |

```bash
# Monitor state
ros2 topic echo /print_node/state

# Check current state once
ros2 topic echo /print_node/state --once
```

### PrintProgress.msg

Published by `print_node` on `~/progress` during printing.

```
std_msgs/Header header
int32 current_layer
int32 total_layers
float32 layer_progress
float32 overall_progress
float64 elapsed_time
float64 estimated_remaining
float64 current_z_height
```

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `current_layer` | `int32` | -- | Current layer number (0-indexed) |
| `total_layers` | `int32` | -- | Total layer count |
| `layer_progress` | `float32` | 0-1 | Progress within current layer |
| `overall_progress` | `float32` | 0-1 | Overall print progress |
| `elapsed_time` | `float64` | s | Time since print started |
| `estimated_remaining` | `float64` | s | Estimated time to completion |
| `current_z_height` | `float64` | m | Current nozzle Z height |

```bash
ros2 topic echo /print_node/progress
```

### ExtruderState.msg

Published by `extruder_controller` on `~/extruder_state` at 50 Hz.

```
std_msgs/Header header
uint8 state
uint8 OFF=0
uint8 EXTRUDING=1
uint8 RETRACTING=2
uint8 PRIMING=3
float64 extrusion_rate
float64 temperature
float64 target_temperature
bool at_temperature
```

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `state` | `uint8` | -- | Current extruder state |
| `extrusion_rate` | `float64` | m^3/s | Current volumetric flow rate |
| `temperature` | `float64` | C | Current hotend temperature |
| `target_temperature` | `float64` | C | Target hotend temperature |
| `at_temperature` | `bool` | -- | True when at target temperature |

```bash
ros2 topic echo /extruder_controller/extruder_state
```

---

## Services

### StartPrint.srv

Start a print job from a G-code file.

```
# Request
string gcode_filepath
geometry_msgs/Point print_origin
bool validate_only
---
# Response
bool success
string message
int32 num_layers
float64 estimated_time
```

| Request Field | Type | Description |
|---------------|------|-------------|
| `gcode_filepath` | `string` | Absolute path to G-code file |
| `print_origin` | `Point` | Optional override for print origin XYZ |
| `validate_only` | `bool` | If true, parse and validate but don't execute |

| Response Field | Type | Description |
|----------------|------|-------------|
| `success` | `bool` | True if print started (or validation passed) |
| `message` | `string` | Status or error message |
| `num_layers` | `int32` | Number of layers in the toolpath |
| `estimated_time` | `float64` | Estimated print time in seconds |

```bash
ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
    "{gcode_filepath: '/path/to/model.gcode'}"
```

### PausePrint.srv

Pause the current print. The robot stops and the extruder retracts.

```
# Request
---
# Response
bool success
string message
```

```bash
ros2 service call /print_node/pause_print ur_3d_printer/srv/PausePrint "{}"
```

### ResumePrint.srv

Resume a paused print. The extruder primes and the trajectory continues.

```
# Request
---
# Response
bool success
string message
```

```bash
ros2 service call /print_node/resume_print ur_3d_printer/srv/ResumePrint "{}"
```

### CancelPrint.srv

Cancel the current print.

```
# Request
bool retract_and_home
---
# Response
bool success
string message
```

| Request Field | Type | Description |
|---------------|------|-------------|
| `retract_and_home` | `bool` | If true, retract extruder and home robot before going idle |

```bash
# Cancel with cleanup
ros2 service call /print_node/cancel_print ur_3d_printer/srv/CancelPrint \
    "{retract_and_home: true}"
```

### CalibrateOrigin.srv

Set the print bed origin frame.

```
# Request
bool use_current_pose
geometry_msgs/Point origin_xyz
geometry_msgs/Vector3 origin_rpy
---
# Response
bool success
string message
float64[16] print_frame
```

| Request Field | Type | Description |
|---------------|------|-------------|
| `use_current_pose` | `bool` | If true, derive origin from current TCP position |
| `origin_xyz` | `Point` | Manual XYZ origin (used if `use_current_pose` is false) |
| `origin_rpy` | `Vector3` | Manual RPY orientation |

| Response Field | Type | Description |
|----------------|------|-------------|
| `print_frame` | `float64[16]` | Resulting 4x4 print frame (row-major) |

```bash
# From current pose
ros2 service call /print_node/calibrate_origin ur_3d_printer/srv/CalibrateOrigin \
    "{use_current_pose: true}"

# Manual
ros2 service call /print_node/calibrate_origin ur_3d_printer/srv/CalibrateOrigin \
    "{use_current_pose: false, origin_xyz: {x: -0.3, y: 0.0, z: -0.01}}"
```

### SetExtruder.srv

Control the extruder (served by `extruder_controller`).

```
# Request
bool enable
float64 rate
bool retract
bool prime
---
# Response
bool success
string message
```

| Request Field | Type | Unit | Description |
|---------------|------|------|-------------|
| `enable` | `bool` | -- | Enable or disable extrusion |
| `rate` | `float64` | m^3/s | Volumetric extrusion rate |
| `retract` | `bool` | -- | Trigger filament retraction |
| `prime` | `bool` | -- | Trigger filament priming |

```bash
# Enable at rate
ros2 service call /extruder_controller/set_extruder ur_3d_printer/srv/SetExtruder \
    "{enable: true, rate: 0.000005}"

# Retract
ros2 service call /extruder_controller/set_extruder ur_3d_printer/srv/SetExtruder \
    "{retract: true}"
```

---

## Actions

### ExecutePrint.action

Long-running print execution with feedback.

```
# Goal
string gcode_filepath
---
# Result
bool success
string message
int32 layers_completed
float64 total_time
---
# Feedback
ur_3d_printer/PrintProgress progress
```

| Goal Field | Type | Description |
|------------|------|-------------|
| `gcode_filepath` | `string` | Absolute path to G-code file |

| Result Field | Type | Description |
|--------------|------|-------------|
| `success` | `bool` | True if print completed successfully |
| `message` | `string` | Status or error message |
| `layers_completed` | `int32` | Number of layers printed |
| `total_time` | `float64` | Total print time in seconds |

| Feedback Field | Type | Description |
|----------------|------|-------------|
| `progress` | `PrintProgress` | Current progress (same as the topic) |

```bash
# Send goal with feedback
ros2 action send_goal /print_node/execute_print ur_3d_printer/action/ExecutePrint \
    "{gcode_filepath: '/path/to/model.gcode'}" --feedback
```

---

## Topic Summary

| Topic | Type | Publisher | Rate |
|-------|------|-----------|------|
| `/joint_states` | `sensor_msgs/JointState` | UR Driver / MockController | 50-500 Hz |
| `/print_node/state` | `PrintState` | print_node | 10 Hz |
| `/print_node/progress` | `PrintProgress` | print_node | 10 Hz |
| `/print_node/tcp_trail` | `visualization_msgs/MarkerArray` | print_node | On update |
| `/print_node/planned_path` | `visualization_msgs/MarkerArray` | print_node | On update |
| `/extruder_controller/extruder_state` | `ExtruderState` | extruder_controller | 50 Hz |
| `/extruder_controller/extruder_command` | `std_msgs/Float64` | extruder_controller | On change |
| `/toolpath_visualizer/markers` | `visualization_msgs/MarkerArray` | toolpath_visualizer | 2 Hz |
| `/deposition_visualizer/deposition` | `visualization_msgs/MarkerArray` | deposition_visualizer | 30 Hz |

## Service Summary

| Service | Type | Server |
|---------|------|--------|
| `/print_node/start_print` | `StartPrint` | print_node |
| `/print_node/pause_print` | `PausePrint` | print_node |
| `/print_node/resume_print` | `ResumePrint` | print_node |
| `/print_node/cancel_print` | `CancelPrint` | print_node |
| `/print_node/calibrate_origin` | `CalibrateOrigin` | print_node |
| `/extruder_controller/set_extruder` | `SetExtruder` | extruder_controller |

## Action Summary

| Action | Type | Server |
|--------|------|--------|
| `/print_node/execute_print` | `ExecutePrint` | print_node |
| `/{controller}/follow_joint_trajectory` | `FollowJointTrajectory` | UR Driver / MockController |

---

## See Also

- [Architecture](architecture.md) -- Node graph and state machines
- [Modules](modules.md) -- Python API for each node
- [Operations](operations.md) -- CLI examples and workflows
