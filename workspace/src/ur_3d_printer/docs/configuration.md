# Configuration Reference

All parameters are defined in `config/print_params.yaml` and loaded by their respective ROS2 nodes.

## Print Node Parameters

Namespace: `print_node.ros__parameters`

### Robot Configuration

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `robot_model` | string | `"ur5e"` | -- | Robot model (`ur3e`, `ur5e`, `ur10e`) |
| `home_joints` | float[6] | `[3.1416, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]` | rad | Joint configuration for homing |
| `trajectory_controller` | string | `"scaled_joint_trajectory_controller"` | -- | ROS2 controller name for trajectory execution |

### Print Origin

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `print_origin_xyz` | float[3] | `[-0.3, 0.0, -0.01]` | m | Print bed origin in robot base frame |
| `print_origin_rpy` | float[3] | `[0.0, 0.0, 0.0]` | rad | Print bed orientation (roll, pitch, yaw) |
| `bed_tilt_rx` | float | `0.0` | rad | Bed tilt compensation around X |
| `bed_tilt_ry` | float | `0.0` | rad | Bed tilt compensation around Y |

### Tool Offset

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `tool_offset_xyz` | float[3] | `[0.0, 0.0, 0.105]` | m | Flange-to-nozzle translation. 0.105 for FDM, 0.18 for paste |
| `tool_offset_rpy` | float[3] | `[0.0, 0.0, 0.0]` | rad | Flange-to-nozzle rotation |

### Motion Parameters

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `max_print_velocity` | float | `0.05` | m/s | Maximum Cartesian speed during extrusion (50 mm/s) |
| `max_travel_velocity` | float | `0.15` | m/s | Maximum Cartesian speed during travel (150 mm/s) |
| `max_acceleration` | float | `0.5` | m/s^2 | Maximum Cartesian acceleration |
| `corner_blend_radius` | float | `0.002` | m | Blend radius for velocity profiling at corners |
| `waypoint_density` | float | `0.010` | m | Maximum spacing between waypoints after densification |
| `joint_velocity_limits` | float[6] | `[3.14, 3.14, 3.14, 3.14, 3.14, 3.14]` | rad/s | Per-joint velocity limits |
| `max_joint_jump` | float | `0.5` | rad | Maximum joint angle change between consecutive IK solutions. Larger jumps indicate IK branch switches (elbow/wrist flips) and are rejected |

### Z-Hop

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `z_hop_enabled` | bool | `true` | -- | Insert z-hops at travel move boundaries |
| `z_hop_height` | float | `0.008` | m | Clearance above the highest point (8 mm) |

### Collision Checking

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `enable_collision_check` | bool | `true` | -- | Run self-collision check on planned trajectories |
| `collision_safety_margin` | float | `0.005` | m | Added to capsule radii for conservative checking (5 mm) |
| `extruder_radius` | float | `0.003` | m | Radius of the extruder collision capsule |

### IK Solver

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `ik_method` | string | `"lm"` | -- | IK solver method: `"lm"` (Levenberg-Marquardt), `"newton"`, or `"analytical"` |
| `ik_max_iterations` | int | `100` | -- | Maximum IK solver iterations |
| `ik_tolerance` | float | `1e-6` | -- | IK convergence tolerance |
| `ik_timeout` | float | `5.0` | s | IK solver timeout per waypoint |

### Singularity Handling

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `singularity_threshold` | float | `0.05` | -- | Minimum singular value of Jacobian. Below this, the configuration is considered near-singular |
| `singularity_velocity_scale` | float | `0.3` | -- | Velocity scale factor when near singularity (30% of normal speed) |

### Workspace Limits

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `workspace_min` | float[3] | `[-0.8, -0.8, -0.02]` | m | Bounding box minimum in robot base frame |
| `workspace_max` | float[3] | `[0.8, 0.8, 1.5]` | m | Bounding box maximum in robot base frame |
| `min_reach_radius` | float | `0.17` | m | Minimum radial distance from shoulder (inside = singularity zone) |
| `max_reach_radius` | float | `0.85` | m | Maximum radial reach of the robot |

### Arm Configuration

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `preferred_arm_config` | string | `"elbow_up"` | -- | Preferred IK branch |
| `max_wrist_3_deviation` | float | `3.14` | rad | Maximum wrist 3 deviation from nominal |

### Validation

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `validate_before_print` | bool | `false` | -- | Run workspace validation before printing |
| `validation_sample_rate` | int | `10` | -- | Check every Nth waypoint during validation |

### Filament

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `filament_diameter` | float | `1.75` | mm | Filament diameter for volumetric calculations |
| `nozzle_diameter` | float | `0.4` | mm | Nozzle diameter |

### Publishing

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `publish_rate` | float | `10.0` | Hz | Rate for state and progress publishing |

---

## Extruder Controller Parameters

Namespace: `extruder_controller.ros__parameters`

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `extruder_type` | string | `"fdm"` | -- | `"fdm"` or `"paste"` |
| `control_method` | string | `"topic"` | -- | `"topic"`, `"digital_io"`, or `"analog"` |
| `nozzle_diameter` | float | `0.4` | mm | Nozzle opening diameter |
| `filament_diameter` | float | `1.75` | mm | Filament diameter |
| `max_rate` | float | `0.00001` | m^3/s | Maximum volumetric flow rate |
| `retraction_distance` | float | `0.005` | m | How far to retract filament (5 mm) |
| `retraction_speed` | float | `0.001` | m/s | Retraction speed |
| `prime_distance` | float | `0.005` | m | How far to push filament forward (5 mm) |
| `prime_speed` | float | `0.0005` | m/s | Priming speed |
| `publish_rate` | float | `50.0` | Hz | State publishing rate |
| `transition_time` | float | `0.3` | s | Extrusion rate ramp-up duration |

### Extruder Presets

**FDM preset** (`config/extruder_fdm.yaml`): Standard FDM with 1.75mm filament, 0.4mm nozzle, topic-based control.

**Paste preset** (`config/extruder_paste.yaml`): Paste/syringe extruder with larger nozzle, analog control, slower retraction.

---

## Toolpath Visualizer Parameters

Namespace: `toolpath_visualizer.ros__parameters`

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `publish_rate` | float | `2.0` | Hz | Marker publishing rate |
| `frame_id` | string | `"world"` | -- | TF reference frame |
| `line_width` | float | `0.001` | m | Line marker width |
| `show_travel` | bool | `true` | -- | Display travel moves |
| `show_bounding_box` | bool | `true` | -- | Display bounding box wireframe |
| `gcode_file` | string | `""` | -- | Auto-load G-code on startup |
| `print_origin_xyz` | float[3] | `[-0.3, 0, -0.01]` | m | Print origin |
| `print_origin_rpy` | float[3] | `[0, 0, 0]` | rad | Print orientation |
| `filament_diameter` | float | `1.75` | mm | For extrusion calculations |

---

## Deposition Visualizer Parameters

Namespace: `deposition_visualizer` (loaded via launch file)

| Parameter | Type | Default | Unit | Description |
|-----------|------|---------|------|-------------|
| `gcode_file` | string | `""` | -- | G-code file to visualize |
| `frame_id` | string | `"world"` | -- | TF reference frame |
| `print_origin_xyz` | float[3] | `[-0.3, 0, -0.01]` | m | Print origin |
| `tube_sides` | int | `8` | -- | Cross-section polygon resolution |
| `tube_radius_scale` | float | `1.0` | -- | Scale factor for tube rendering |
| `color_scheme` | string | `"pla"` | -- | `"pla"` (white) or `"gradient"` (rainbow) |
| `demo_mode` | bool | `true` | -- | Auto-animate (`true`) or live tracking (`false`) |
| `speed_scale` | float | `5.0` | -- | Demo animation speed multiplier |
| `publish_rate` | float | `30.0` | Hz | Frame rate for visualization |
| `nozzle_diameter` | float | `0.0004` | m | For tube radius computation |

---

## Launch File Arguments

### `print_driver.launch.py` (Full deployment)

| Argument | Default | Description |
|----------|---------|-------------|
| `ur_type` | `"ur5e"` | Robot model |
| `robot_ip` | `"172.17.0.2"` | Robot/URSim IP address |
| `headless_mode` | `"true"` | UR driver headless mode |
| `launch_rviz` | `"true"` | Start RViz |
| `extruder_type` | `"fdm"` | Extruder type (`"fdm"` or `"paste"`) |
| `gcode_file` | `""` | G-code file to auto-load |

### `print_ursim.launch.py` (App-only, UR driver already running)

| Argument | Default | Description |
|----------|---------|-------------|
| `launch_rviz` | `"true"` | Start RViz |
| `use_sim_time` | `"false"` | Use simulation clock |
| `robot_model` | `"ur5e"` | Robot model |
| `gcode_file` | `""` | G-code file to auto-load |
| `trajectory_controller` | `"scaled_joint_trajectory_controller"` | Controller name |

### `print_demo.launch.py` (Complete demo with robot description)

| Argument | Default | Description |
|----------|---------|-------------|
| `ur_type` | `"ur5e"` | Robot model |
| `robot_ip` | -- | Robot IP (required) |
| `launch_rviz` | `"true"` | Start RViz |
| `extruder_type` | `"fdm"` | Extruder type |

---

## Docker / Environment Variables

Defined in `docker-compose.yml`:

| Variable | Value | Description |
|----------|-------|-------------|
| `ROS_DOMAIN_ID` | `0` | ROS2 domain for network isolation |
| `RMW_IMPLEMENTATION` | `rmw_cyclonedds_cpp` | DDS middleware. Must match between all containers |
| `ROBOT_MODEL` | `ur5e` | Passed to URSim container |
| `ROBOT_IP` | `172.20.0.2` | URSim IP on Docker bridge network |
| `UR_TYPE` | `ur5e` | Passed to UR driver |

**Docker network:** `ur-network` bridge, subnet `172.20.0.0/16`

**Container IPs:**
- URSim: `172.20.0.2`
- UR Driver: `172.20.0.3`

---

## Key Tuning Parameters

Parameters that most commonly need adjustment:

| Parameter | Effect of Increasing | Effect of Decreasing |
|-----------|---------------------|---------------------|
| `max_print_velocity` | Faster prints, may reduce quality | Slower, more precise deposition |
| `z_hop_height` | More clearance, less collision risk, more travel time | Less clearance, faster travel |
| `collision_safety_margin` | More conservative, may reject valid paths | Less margin, risk of actual collision |
| `max_joint_jump` | Allows larger joint movements (may accept branch switches) | Stricter continuity, may reject more waypoints |
| `singularity_threshold` | Earlier singularity detection, more restricted workspace | More aggressive, may cause jerky motion near singularity |
| `corner_blend_radius` | Smoother corners, less precise | Sharper corners, may cause vibration |
| `waypoint_density` | Sparser path (faster planning) | Denser path (smoother motion, slower planning) |
| `validation_sample_rate` | Faster validation, less thorough | More thorough, slower validation |

## See Also

- [Architecture](architecture.md) -- System design
- [Modules](modules.md) -- Module API details
- [Operations](operations.md) -- How to run and tune
