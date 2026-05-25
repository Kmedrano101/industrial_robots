# Operations Guide

## Prerequisites

- **Docker** and **Docker Compose** installed
- **URSim** running (for simulation) or a real UR robot with **External Control URCap** installed
- ROS2 workspace built: `colcon build --packages-select ur_3d_printer`
- Source the workspace: `source install/setup.bash`

## Launching

### Option 1: Simulation with URSim

Start URSim and the UR driver first:

```bash
# Terminal 1: Start URSim
docker compose --profile sim up

# Terminal 2: Source workspace and launch the 3D printer nodes
source install/setup.bash
ros2 launch ur_3d_printer print_ursim.launch.py
```

**Important:** In the URSim web interface (port 6080), load the External Control URCap program and press Play before starting a print.

### Option 2: Full Driver Launch

Launches the UR driver and all application nodes together:

```bash
ros2 launch ur_3d_printer print_driver.launch.py \
    robot_ip:=172.17.0.2 \
    ur_type:=ur5e \
    launch_rviz:=true \
    gcode_file:=/path/to/model.gcode
```

### Option 3: Real Robot

```bash
ros2 launch ur_3d_printer print_driver.launch.py \
    robot_ip:=<ROBOT_IP> \
    ur_type:=ur5e \
    headless_mode:=false
```

Ensure the robot has the External Control URCap program running.

## RMW Configuration

All ROS2 nodes and containers must use the same DDS middleware:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0
```

This is set automatically in the Docker containers via `docker-compose.yml`.

## Slicing an STL

### Planar Slicing

```bash
python3 workspace/src/ur_3d_printer/resource/stl_slicer.py \
    workspace/src/ur_3d_printer/resource/triangle_prism.stl \
    --layer-height 0.2 \
    --nozzle 0.4 \
    --scale 0.001 \
    --print-speed 1200 \
    -o /tmp/model.gcode
```

### Multi-Axis Slicing

```bash
python3 workspace/src/ur_3d_printer/resource/multiaxis_slicer.py \
    workspace/src/ur_3d_printer/resource/wave_vase.stl \
    --layer-height 1.0 \
    --max-tilt 45 \
    --print-speed 50 \
    --travel-speed 150 \
    --robot ur5e \
    -o /tmp/multiaxis.gcode
```

## Starting a Print

### Via ROS2 Service Call

```bash
# Start a print
ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
    "{gcode_filepath: '/path/to/model.gcode'}"

# Validate only (don't execute)
ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
    "{gcode_filepath: '/path/to/model.gcode', validate_only: true}"

# With custom print origin
ros2 service call /print_node/start_print ur_3d_printer/srv/StartPrint \
    "{gcode_filepath: '/path/to/model.gcode', print_origin: {x: -0.3, y: 0.0, z: 0.0}}"
```

### Via Action (with feedback)

```bash
ros2 action send_goal /print_node/execute_print ur_3d_printer/action/ExecutePrint \
    "{gcode_filepath: '/path/to/model.gcode'}" --feedback
```

## Pausing, Resuming, and Cancelling

```bash
# Pause
ros2 service call /print_node/pause_print ur_3d_printer/srv/PausePrint "{}"

# Resume
ros2 service call /print_node/resume_print ur_3d_printer/srv/ResumePrint "{}"

# Cancel (with retract and home)
ros2 service call /print_node/cancel_print ur_3d_printer/srv/CancelPrint \
    "{retract_and_home: true}"

# Cancel (immediate stop, no homing)
ros2 service call /print_node/cancel_print ur_3d_printer/srv/CancelPrint \
    "{retract_and_home: false}"
```

## Calibrating the Print Origin

Set the print bed origin from the robot's current TCP position or manually:

```bash
# Use current robot pose as print origin
ros2 service call /print_node/calibrate_origin ur_3d_printer/srv/CalibrateOrigin \
    "{use_current_pose: true}"

# Set manually
ros2 service call /print_node/calibrate_origin ur_3d_printer/srv/CalibrateOrigin \
    "{use_current_pose: false, origin_xyz: {x: -0.3, y: 0.0, z: -0.01}, origin_rpy: {x: 0.0, y: 0.0, z: 0.0}}"
```

## Monitoring

### Print State

```bash
ros2 topic echo /print_node/state
```

Fields: `state` (uint8), `state_name` (string), `error_message` (string)

### Print Progress

```bash
ros2 topic echo /print_node/progress
```

Fields: `current_layer`, `total_layers`, `layer_progress`, `overall_progress`, `elapsed_time`, `estimated_remaining`, `current_z_height`

### Extruder State

```bash
ros2 topic echo /extruder_controller/extruder_state
```

### Manual Extruder Control

```bash
# Enable extrusion
ros2 service call /extruder_controller/set_extruder ur_3d_printer/srv/SetExtruder \
    "{enable: true, rate: 0.000005}"

# Retract
ros2 service call /extruder_controller/set_extruder ur_3d_printer/srv/SetExtruder \
    "{retract: true}"

# Prime
ros2 service call /extruder_controller/set_extruder ur_3d_printer/srv/SetExtruder \
    "{prime: true}"

# Disable
ros2 service call /extruder_controller/set_extruder ur_3d_printer/srv/SetExtruder \
    "{enable: false}"
```

## RViz Configuration

The saved RViz config is at `config/printer_3d.rviz`. It includes:

- **TF display** -- Robot link frames
- **RobotModel** -- Robot visualization from URDF
- **MarkerArray displays:**
  - `/toolpath_visualizer/markers` -- Toolpath lines
  - `/deposition_visualizer/deposition` -- 3D deposited material
  - `/print_node/tcp_trail` -- Nozzle trail
  - `/print_node/planned_path` -- Planned trajectory

To launch RViz separately:

```bash
rviz2 -d workspace/src/ur_3d_printer/config/printer_3d.rviz
```

## Troubleshooting

### RMW Mismatch

**Symptom:** Nodes can't discover each other. Topics show no publishers/subscribers.

**Fix:** Ensure all terminals and containers use the same `RMW_IMPLEMENTATION`:
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

### Protective Stop

**Symptom:** Robot enters protective stop during printing. Error message: "Protective stop triggered."

**Causes:**
- Joint velocity or acceleration limits exceeded
- Unexpected contact or force

**Fix:**
1. Release the protective stop in the UR teach pendant or URSim dashboard
2. Reduce `max_print_velocity` and `max_acceleration`
3. Check `joint_velocity_limits` are within UR specifications

### IK Failures

**Symptom:** "IK failed for waypoint N" or many waypoints rejected during planning.

**Causes:**
- Print origin places the toolpath outside the robot's reachable workspace
- Waypoints too close to the robot base (shoulder singularity)
- Waypoints too far from the robot base (beyond reach)

**Fix:**
1. Adjust `print_origin_xyz` to move the print bed into the robot's workspace
2. Enable validation: set `validate_before_print: true` to check before executing
3. Check `workspace_min`/`workspace_max` and `min_reach_radius`/`max_reach_radius`
4. Scale the model down if it's too large

### Collision False Positives

**Symptom:** Valid configurations rejected as colliding.

**Causes:**
- `collision_safety_margin` too large
- `extruder_radius` larger than the physical extruder

**Fix:**
1. Reduce `collision_safety_margin` (default 0.005 m)
2. Set `extruder_radius` to match the actual extruder dimensions
3. Set `enable_collision_check: false` to disable (use with caution)

### Joint Jump Rejections

**Symptom:** "Joint jump detected at waypoint N" -- trajectory planning fails or skips waypoints.

**Causes:**
- IK solver switching between elbow-up/elbow-down configurations
- Wrist singularity causing 180-degree wrist flips

**Fix:**
1. Increase `max_joint_jump` from 0.5 to 1.0 (allows more joint motion per step)
2. Move the print origin to avoid singular configurations
3. Reduce `waypoint_density` for denser waypoint spacing (smoother IK seed chaining)

### URSim Connection Issues

**Symptom:** Cannot connect to URSim from the UR driver container.

**Fix:**
1. Verify URSim is running: `docker compose ps`
2. Check the robot IP matches: `robot_ip:=172.20.0.2` (Docker bridge) or `172.17.0.2` (default)
3. Ensure the External Control URCap program is loaded and running in URSim
4. Check Docker network: `docker network inspect ur-network`

### Trajectory Controller Not Found

**Symptom:** "Action server not available" for `follow_joint_trajectory`.

**Fix:**
1. Verify the controller is running: `ros2 control list_controllers`
2. Check the controller name matches `trajectory_controller` parameter
3. Default is `scaled_joint_trajectory_controller` -- for mock testing, use `joint_trajectory_controller`

## See Also

- [Architecture](architecture.md) -- System design and state machines
- [Configuration](configuration.md) -- Full parameter reference
- [Interfaces](interfaces.md) -- ROS2 service/topic/action details
